from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol, Optional, Type

from metro.models import BaseModel, StringField, BooleanField, DateTimeField


class RateLimitPeriod(str, Enum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"

    @staticmethod
    def get_seconds(period: str) -> int:
        return {
            RateLimitPeriod.SECOND: 1,
            RateLimitPeriod.MINUTE: 60,
            RateLimitPeriod.HOUR: 3600,
            RateLimitPeriod.DAY: 86400,
        }[period]


@dataclass
class AuthLimitConfig:
    """Configuration for authentication rate limiting"""

    enabled: bool = False
    max_attempts: int = 5
    period: RateLimitPeriod = RateLimitPeriod.MINUTE
    lockout_duration: int = 300  # 5 minutes in seconds


class AuthLimiterProtocol(Protocol):
    """Protocol for auth rate limiting implementations"""

    def check_login_allowed(
        self, identifier: str, config: AuthLimitConfig
    ) -> tuple[bool, Optional[datetime]]:
        """
        Check if login is allowed for the identifier
        Returns: (allowed, unlock_time)
        """
        ...

    def record_attempt(
        self, identifier: str, success: bool, config: AuthLimitConfig
    ) -> None:
        """Record a login attempt"""
        ...


class AuthAttemptLogBase(BaseModel):
    """Model for tracking auth attempts"""

    meta = {
        "abstract": True,
        "collection": "auth_attempt_log",
        "indexes": [
            ("identifier", "created_at"),
            {"fields": ["created_at"], "expireAfterSeconds": 86400},  # 24hr TTL
        ],
    }

    identifier = StringField(required=True)
    success = BooleanField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)


class AuthAttemptLog(AuthAttemptLogBase):
    pass


class MongoAuthLimiter(AuthLimiterProtocol):
    def __init__(self, log_cls: Optional[Type[AuthAttemptLogBase]] = None):
        self.attempt_log = log_cls or AuthAttemptLog

    def check_login_allowed(
        self, identifier: str, config
    ) -> tuple[bool, Optional[datetime]]:
        now = datetime.utcnow()
        window_start = now - timedelta(
            seconds=RateLimitPeriod.get_seconds(self.config.period)
        )

        # Count recent failed attempts
        failed_attempts = self.attempt_log.objects(
            identifier=identifier, success=False, created_at__gte=window_start
        ).count()

        if failed_attempts >= self.config.max_attempts:
            # Find most recent attempt to calculate unlock time
            last_attempt = (
                self.AuthAttempt.objects(identifier=identifier, success=False)
                .order_by("-created_at")
                .first()
            )

            if last_attempt:
                unlock_time = self.get_unlock_time(last_attempt.created_at)
                if now < unlock_time:
                    return False, unlock_time

        return True, None

    def record_attempt(self, identifier: str, success: bool) -> None:
        self.AuthAttempt(identifier=identifier, success=success).save()
