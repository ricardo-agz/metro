import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Optional, Type
from pydantic import (
    BaseModel as PydanticBaseModel,
    Field,
    model_validator,
)

from pyrails.models import BaseModel, StringField, FloatField

try:
    from redis import Redis

    REDIS_AVAILABLE = True
except ImportError:
    Redis = None
    REDIS_AVAILABLE = False


class RateLimitPeriod(str, Enum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"

    @property
    def seconds(self) -> int:
        return {
            self.SECOND: 1,
            self.MINUTE: 60,
            self.HOUR: 3600,
            self.DAY: 86400,
            self.MONTH: 2592000,
        }[self]


class RateLimits(PydanticBaseModel):
    per_second: Optional[float] = Field(default=None, ge=0)
    per_minute: Optional[float] = Field(default=None, ge=0)
    per_hour: Optional[float] = Field(default=None, ge=0)
    per_day: Optional[float] = Field(default=None, ge=0)
    priority: int = Field(default=0)

    @model_validator(mode="after")
    def validate_limits(self) -> "RateLimits":
        if not any([self.per_second, self.per_minute, self.per_hour, self.per_day]):
            raise ValueError(
                "At least one rate limit (per_second, per_minute, per_hour, per_day) must be set"
            )
        return self

    @property
    def min_limit(self) -> Optional[float]:
        """Returns the smallest non-None rate limit value."""
        limits = [
            limit
            for limit in [self.per_second, self.per_minute, self.per_hour, self.per_day]
            if limit is not None
        ]
        return min(limits) if limits else None

    @property
    def min_period(self) -> Optional[RateLimitPeriod]:
        """Returns the rate limit period with smallest time duration that has a limit set."""
        period_map = {
            self.per_second: RateLimitPeriod.SECOND,
            self.per_minute: RateLimitPeriod.MINUTE,
            self.per_hour: RateLimitPeriod.HOUR,
            self.per_day: RateLimitPeriod.DAY,
        }

        # Get periods that have non-None limits
        valid_periods = [
            period_map[limit]
            for limit in [self.per_second, self.per_minute, self.per_hour, self.per_day]
            if limit is not None
        ]

        # Return period with minimum seconds duration
        return min(valid_periods, key=lambda x: x.seconds) if valid_periods else None

    def get_period_limit(self, period: RateLimitPeriod) -> Optional[float]:
        """Get the rate limit for a specific period."""
        period_map = {
            RateLimitPeriod.SECOND: self.per_second,
            RateLimitPeriod.MINUTE: self.per_minute,
            RateLimitPeriod.HOUR: self.per_hour,
            RateLimitPeriod.DAY: self.per_day,
        }
        return period_map.get(period)

    def get_limits_dict(self) -> dict[RateLimitPeriod, float]:
        """Returns a dictionary of all non-None rate limits."""
        limits = {
            RateLimitPeriod.SECOND: self.per_second,
            RateLimitPeriod.MINUTE: self.per_minute,
            RateLimitPeriod.HOUR: self.per_hour,
            RateLimitPeriod.DAY: self.per_day,
        }
        return {k: v for k, v in limits.items() if v is not None}

    def get_most_constrained_period(
        self, current_counts: dict[RateLimitPeriod, float]
    ) -> RateLimitPeriod:
        usage_percentages = {
            period: current_counts.get(period, 0) / limit
            for period, limit in self.get_limits_dict().items()
        }
        return max(usage_percentages.items(), key=lambda x: x[1])[0]

    def get_min_remaining(self, current_counts: dict[RateLimitPeriod, float]) -> int:
        return min(
            self.get_period_limit(period) - current_counts.get(period, 0)
            for period in self.get_limits_dict()
        )


class RateLimitResponse(PydanticBaseModel):
    limit: float = Field(ge=0)
    remaining: float = Field(ge=0)
    reset: str  # ISO format timestamp
    period: RateLimitPeriod


class RateLimiterBackend(ABC):
    @abstractmethod
    def check_rate_limit(
        self, identifier: str, limits: RateLimits, cost: float = 1.0
    ) -> tuple[bool, RateLimitResponse]:
        """Check if request is within rate limit"""
        pass

    @staticmethod
    def get_reset_time(period: RateLimitPeriod) -> datetime:
        """Calculate next reset time for a period"""
        now = datetime.utcnow()
        window = period.seconds
        return now + timedelta(seconds=window - (now.timestamp() % window))


class NoOpRateLimiterBackend(RateLimiterBackend):
    """Rate limiter that doesn't actually limit anything"""

    def __init__(self, *args, **kwargs):
        pass

    def check_rate_limit(
        self, identifier: str, limits: RateLimits, cost: float = 1
    ) -> tuple[bool, RateLimitResponse]:
        return True, RateLimitResponse(
            limit=limits.min_limit,
            remaining=limits.min_limit,  # Always return full limit since it's a no-op
            reset=datetime.utcnow().isoformat(),
            period=limits.min_period,
        )


class InMemoryRateLimiterBackend(RateLimiterBackend):
    """Simple in-memory rate limiter using sliding windows"""

    def __init__(self, *args, **kwargs):
        self.requests = defaultdict(lambda: defaultdict(list))
        self.costs = defaultdict(lambda: defaultdict(list))
        self.lock = Lock()

    def check_rate_limit(
        self, identifier: str, limits: RateLimits, cost: float = 1
    ) -> tuple[bool, RateLimitResponse]:
        with self.lock:
            now = time.time()
            key_requests = self.requests[identifier]
            key_costs = self.costs[identifier]

            # Check ALL period constraints first
            current_counts = {}
            for period, limit in limits.get_limits_dict().items():
                window = period.seconds
                cutoff = now - window

                # Calculate current usage within window
                valid_costs = [
                    cost
                    for t, cost in zip(key_requests[period], key_costs[period])
                    if t > cutoff
                ]
                current_cost = sum(valid_costs)
                current_counts[period] = current_cost

                # Check if adding new cost would exceed limit
                if current_cost + cost > limit:
                    reset_time = self.get_reset_time(period)
                    return False, RateLimitResponse(
                        limit=limit,
                        remaining=max(0, limit - current_cost),
                        reset=reset_time.isoformat(),
                        period=period,
                    )

            # If we get here, request passes all constraints
            # Now we can record the new request
            for period in limits.get_limits_dict().keys():
                key_requests[period].append(now)
                key_costs[period].append(cost)

            most_constrained = limits.get_most_constrained_period(current_counts)
            min_remaining = limits.get_min_remaining(current_counts)

            return True, RateLimitResponse(
                limit=limits.get_period_limit(most_constrained),
                remaining=max(0, min_remaining),
                reset=self.get_reset_time(most_constrained).isoformat(),
                period=most_constrained,
            )


class RedisRateLimiterBackend(RateLimiterBackend):
    """Redis-based rate limiter for production use"""

    def __init__(
        self,
        redis_client: Redis = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = None,
        name: str = "ratelimit",
    ):
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis library is required for RedisRateLimiter. Please install it."
            )

        if redis_client is None:
            redis_client = Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
            )

        try:
            redis_client.ping()
        except Exception as e:
            raise ValueError(f"RedisRateLimiterBackend failed to connect to Redis: {e}")

        self.redis = redis_client
        self.name = name

    def check_rate_limit(
        self, identifier: str, limits: RateLimits, cost: float = 1.0
    ) -> tuple[bool, RateLimitResponse]:
        pipe = self.redis.pipeline()
        current_timestamp = int(time.time() * 1000)
        counts = {}
        request_id = f"{cost}:{current_timestamp}"

        # First pass: check all constraints BEFORE recording anything
        for period, limit_value in limits.get_limits_dict().items():
            window_ms = period.seconds * 1000
            redis_key = f"{self.name}:{identifier}:{period}"
            score_cutoff = current_timestamp - window_ms

            # Just clean up old entries and get current entries
            pipe.zremrangebyscore(redis_key, 0, score_cutoff)
            pipe.zrange(redis_key, 0, -1, withscores=True)

        # Execute first batch of commands
        results = pipe.execute()

        # Check all constraints
        for i, (period, limit_value) in enumerate(limits.get_limits_dict().items()):
            entries = results[i * 2 + 1]  # Get zrange results
            current_cost = sum(float(member.split(":")[0]) for member, _ in entries)
            total_usage = current_cost + cost
            counts[period] = total_usage

            if total_usage > limit_value:
                reset_time = self.get_reset_time(period)
                return False, RateLimitResponse(
                    limit=limit_value,
                    remaining=max(0, limit_value - current_cost),
                    reset=reset_time.isoformat(),
                    period=period,
                )

        # If we get here, all constraints passed
        # Second pass: record the request in all windows
        pipe = self.redis.pipeline()
        for period, limit_value in limits.get_limits_dict().items():
            redis_key = f"{self.name}:{identifier}:{period}"
            pipe.zadd(redis_key, {request_id: current_timestamp})
            pipe.expire(redis_key, period.seconds)
        pipe.execute()

        most_constrained = limits.get_most_constrained_period(counts)
        min_remaining = limits.get_min_remaining(counts)

        return True, RateLimitResponse(
            limit=limits.min_limit,
            remaining=max(0, min_remaining),
            reset=self.get_reset_time(most_constrained).isoformat(),
            period=most_constrained,
        )


class MongoRateLimiterLogBase(BaseModel):
    """Base model for tracking rate limit usage"""

    meta = {
        "abstract": True,
        "indexes": [
            ("identifier", "created_at"),  # For rate limit queries
            {"fields": ["created_at"], "expireAfterSeconds": 2592000},  # 30 day TTL
        ],
    }

    identifier = StringField(required=True)
    cost = FloatField(required=True, default=1.0)

    @classmethod
    def sum_costs(cls, identifier: str, since: datetime) -> float:
        """Sum costs for a key since given timestamp"""
        pipeline = [
            {"$match": {"identifier": identifier, "created_at": {"$gte": since}}},
            {"$group": {"_id": None, "total_cost": {"$sum": "$cost"}}},
        ]
        result = cls.objects.aggregate(pipeline)
        try:
            return next(result)["total_cost"]
        except (StopIteration, KeyError):
            return 0.0

    @classmethod
    def record_request(
        cls, identifier: str, cost: float = 1.0, **kwargs
    ) -> "MongoRateLimiterLogBase":
        """Record a new request with its cost"""
        return cls(identifier=identifier, cost=cost, **kwargs).save()


class MongoRateLimiterLog(MongoRateLimiterLogBase):
    """Default implementation of rate limiter usage logging"""

    meta = {
        "collection": "rate_limiter_log",
    }


class MongoRateLimiterBackend(RateLimiterBackend):
    """MongoDB-based rate limiter using existing infrastructure"""

    def __init__(self, usage_log_cls: Optional[Type[MongoRateLimiterLogBase]] = None):
        self.usage_log = usage_log_cls or MongoRateLimiterLog

    def check_rate_limit(
        self, identifier: str, limits: RateLimits, cost: float = 1.0
    ) -> tuple[bool, RateLimitResponse]:
        now = datetime.utcnow()
        costs = {}

        # First pass: check ALL constraints before recording anything
        for period, limit in limits.get_limits_dict().items():
            window = period.seconds
            cutoff = now - timedelta(seconds=window)

            # Get sum of costs for this period
            current_cost = self.usage_log.sum_costs(identifier, cutoff)
            costs[period] = current_cost

            # Check if adding new cost would exceed limit
            if current_cost + cost > limit:
                reset_time = self.get_reset_time(period)
                return False, RateLimitResponse(
                    limit=limit,
                    remaining=max(0, limit - current_cost),
                    reset=reset_time.isoformat(),
                    period=period,
                )

        # If we get here, all constraints passed
        # Now we can safely record the request
        self.usage_log.record_request(identifier, cost=cost)

        # Add the new cost to all period totals for the response
        costs = {period: cost_sum + cost for period, cost_sum in costs.items()}

        most_constrained = limits.get_most_constrained_period(costs)
        min_remaining = limits.get_min_remaining(costs)

        return True, RateLimitResponse(
            limit=limits.min_limit,
            remaining=max(0, min_remaining),
            reset=self.get_reset_time(most_constrained).isoformat(),
            period=most_constrained,
        )


## Inteded Use:
"""
# with controllers

class CoreFunctionalityController(Controller):
    throttle = Throttler(
        name="core-limiter",
        backend=InMemoryBackend(),
    )

    def get_rate_limit_key(self, request: Request):
        return request.client.host

    def get_rate_limits(self, request: Request):
        organization = request.user.organization
        tier = organization.tier
        if tier == "free":
            return RateLimits(
                per_minute=60,
            )
        elif tier == "pro":
            return RateLimits(
                per_minute=120,
            )
        elif tier == "enterprise":
            return RateLimits(
                per_minute=300,
            )

    @get(f"/my-endpoint")
    @throttle(
        key=get_rate_limit_key,
        limits=get_rate_limits,
    )
    async def my_endpoint():
        pass


# with routes
router = APIRouter()

def get_rate_limit_key(request: Request):
    return request.client.host

def get_rate_limits(request: Request):
    organization = request.user.organization
    tier = organization.tier
    if tier == "free":
        return RateLimits(
            per_minute=60,
        )
    elif tier == "pro":
        return RateLimits(
            per_minute=120,
        )
    elif tier == "enterprise":
        return RateLimits(
            per_minute=300,
        )

@router.get("/my-endpoint")
@throttle(
    key=get_rate_limit_key,
    limits=get_rate_limits,
    cost=get_video_cost,
    backend=RedisBackend(),
)
async def my_endpoint():
    pass


# as a method:
@get(...)
def my_endpoint():
    throttle_limit, limit_info = throttle.check(org.id, org.rate_limits)
    if throttle_limit:
        raise TooManyRequestsError


def get_video_limits(request: Request) -> RateLimits:
    user = get_user_from_request(request)
    if user.is_pro:
        return RateLimits(
            per_minute=200,
            per_hour=1000,
        )
    return RateLimits(
        per_minute=10,
        per_hour=50,
    )


@router.post("/process-video")
@throttle(
    key=lambda req: req.client.host,
    limits=get_video_limits,
    cost=get_video_cost,
    backend=RedisBackend()
)
async def process_video(request: Request):
    # by the time we get here, usage is incremented
    body = await request.json()
    minutes = body.get("video_minutes", 1)
    return {"message": f"Processing {minutes} minute(s) of video..."}
"""
