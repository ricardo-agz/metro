import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Optional, Protocol, TypedDict, Type, Annotated
from pydantic import BaseModel as PydanticBaseModel, AfterValidator

from pyrails.models import BaseModel, StringField


class RateLimitPeriod(str, Enum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"
    MIXED = "mixed"

    @property
    def seconds(self) -> int:
        if self == self.MIXED:
            raise ValueError("Cannot get seconds for mixed period")

        return {
            self.SECOND: 1,
            self.MINUTE: 60,
            self.HOUR: 3600,
            self.DAY: 86400,
            self.MONTH: 2592000,
        }[self]


def validate_rate_limits(v):
    if not all(v > 0 for v in v.values()):
        raise ValueError("Rate limits must be positive integers")
    return


class RateLimits(PydanticBaseModel):
    limits: Annotated[dict[RateLimitPeriod, int], AfterValidator(validate_rate_limits)]
    priority: int = 0


class RateLimitInfo(TypedDict):
    limit: int
    remaining: int
    reset: str  # ISO format timestamp
    period: RateLimitPeriod


class RateLimitStrategy(Protocol):
    """Protocol for rate limit strategies"""

    def get_rate_limit_key(self, key_id: str, owner_id: str) -> str:
        """Get the key to use for rate limiting"""
        ...

    @staticmethod
    def get_limits(key: "APIKeyBase") -> RateLimits:
        """Get the rate limits to apply"""
        return key.get_effective_rate_limits()


class PerKeyStrategy(RateLimitStrategy):
    def get_rate_limit_key(self, key_id: str, owner_id: str) -> str:
        return f"key:{key_id}"


class PerOwnerStrategy(RateLimitStrategy):
    def get_rate_limit_key(self, key_id: str, owner_id: str) -> str:
        return f"owner:{owner_id}"


class RateLimiter(ABC):
    @abstractmethod
    def check_rate_limit(
        self, key_id: str, limits: RateLimits
    ) -> tuple[bool, RateLimitInfo]:
        """Check if request is within rate limit"""
        pass

    @staticmethod
    def get_reset_time(period: RateLimitPeriod) -> datetime:
        """Calculate next reset time for a period"""
        now = datetime.utcnow()
        window = period.seconds
        return now + timedelta(seconds=window - (now.timestamp() % window))


class NoOpRateLimiter(RateLimiter):
    """Rate limiter that doesn't actually limit anything"""

    def check_rate_limit(
        self, key_id: str, limits: RateLimits
    ) -> tuple[bool, RateLimitInfo]:
        return True, RateLimitInfo(
            limit=0,
            remaining=0,
            reset=datetime.utcnow().isoformat(),
            period=RateLimitPeriod.SECOND,
        )


class InMemoryRateLimiter(RateLimiter):
    """Simple in-memory rate limiter using sliding windows"""

    def __init__(self):
        self.requests = defaultdict(lambda: defaultdict(list))
        self.lock = Lock()

    def check_rate_limit(
        self, key_id: str, limits: RateLimits
    ) -> tuple[bool, RateLimitInfo]:
        with self.lock:
            now = time.time()
            key_requests = self.requests[key_id]

            # Check each period's limits
            for period, limit in limits["limits"].items():
                window = period.seconds
                cutoff = now - window

                # Clean old requests
                key_requests[period] = [t for t in key_requests[period] if t > cutoff]

                # Check if over limit
                if len(key_requests[period]) >= limit:
                    reset_time = self.get_reset_time(period)
                    return False, RateLimitInfo(
                        limit=limit,
                        remaining=0,
                        reset=reset_time.isoformat(),
                        period=period,
                    )

                # Record request
                key_requests[period].append(now)

            # All limits passed
            min_remaining = min(
                limits["limits"][period] - len(reqs)
                for period, reqs in key_requests.items()
            )
            return True, RateLimitInfo(
                limit=min(limits["limits"].values()),
                remaining=min_remaining,
                reset=self.get_reset_time(
                    min(limits["limits"].keys(), key=lambda p: p.seconds)
                ).isoformat(),
                period=RateLimitPeriod.MIXED,
            )


class RedisRateLimiter(RateLimiter):
    """Redis-based rate limiter for production use"""

    def __init__(self, redis_client):
        self.redis = redis_client

    def check_rate_limit(
        self, key_id: str, limits: RateLimits
    ) -> tuple[bool, RateLimitInfo]:
        pipe = self.redis.pipeline()
        now = time.time()

        # Check each period's limits
        for period, limit in limits["limits"].items():
            window = period.seconds
            redis_key = f"ratelimit:{key_id}:{period}"

            pipe.zremrangebyscore(redis_key, 0, now - window)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window)

        results = pipe.execute()

        # Process results
        for i, (period, limit) in enumerate(limits["limits"].items()):
            count = results[i * 4 + 1]  # Get count from results
            if count > limit:
                reset_time = self.get_reset_time(period)
                return False, RateLimitInfo(
                    limit=limit,
                    remaining=0,
                    reset=reset_time.isoformat(),
                    period=period,
                )

        # All limits passed
        min_remaining = min(
            limit - results[i * 4 + 1]
            for i, (_, limit) in enumerate(limits["limits"].items())
        )
        return True, RateLimitInfo(
            limit=min(limits["limits"].values()),
            remaining=max(0, min_remaining),
            reset=self.get_reset_time(
                min(limits["limits"].keys(), key=lambda p: p.seconds)
            ).isoformat(),
            period=RateLimitPeriod.MIXED,
        )


class KeyUsageLogBase(BaseModel):
    """Base model for tracking API key usage"""

    meta = {
        "abstract": True,
        "indexes": [
            ("key_id", "created_at"),  # For rate limit queries
            {"fields": ["created_at"], "expireAfterSeconds": 2592000},  # 30 day TTL
        ],
    }

    key_id = StringField(required=True)

    @classmethod
    def count_usage(cls, key_id: str, since: datetime) -> int:
        """Count requests for a key since given timestamp"""
        return cls.objects(key_id=key_id, created_at__gte=since).count()

    @classmethod
    def record_request(cls, key_id: str, **kwargs) -> "KeyUsageLogBase":
        """Record a new request"""
        return cls(key_id=key_id, **kwargs).save()


class APIKeyUsageLog(KeyUsageLogBase):
    """Default implementation of API key usage logging"""

    meta = {
        "collection": "api_key_usage_logs",
    }


class MongoRateLimiter(RateLimiter):
    """MongoDB-based rate limiter using existing infrastructure"""

    def __init__(self, usage_log_cls: Optional[Type[KeyUsageLogBase]] = None):
        self.usage_log = usage_log_cls or APIKeyUsageLog

    def check_rate_limit(
        self, key_id: str, limits: RateLimits
    ) -> tuple[bool, RateLimitInfo]:
        now = datetime.utcnow()

        # Check each period's limits
        for period, limit in limits["limits"].items():
            window = period.seconds
            cutoff = now - timedelta(seconds=window)

            count = self.usage_log.count_usage(key_id, cutoff)

            if count >= limit:
                reset_time = self.get_reset_time(period)
                return False, RateLimitInfo(
                    limit=limit,
                    remaining=0,
                    reset=reset_time.isoformat(),
                    period=period,
                )

        # Record this request
        self.usage_log.record_request(key_id)

        return True, RateLimitInfo(
            limit=min(limits["limits"].values()),
            remaining=min(limit - 1 for limit in limits["limits"].values()),
            reset=self.get_reset_time(
                min(limits["limits"].keys(), key=lambda p: p.seconds)
            ).isoformat(),
            period=RateLimitPeriod.MIXED,
        )
