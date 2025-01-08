import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets
from enum import Enum
from threading import Lock
from typing import Optional, Protocol, TypedDict, NotRequired, Type

from bcrypt import hashpw, gensalt, checkpw
from bson import ObjectId

from metro.auth.api_key.rate_limiting import (
    RateLimitStrategy,
    RateLimiter,
    RateLimits,
    RateLimitInfo,
)
from metro.models import (
    BaseModel,
    StringField,
    DateTimeField,
    ReferenceField,
    ListField,
    DictField,
    IntField,
)


class InvalidAPIKeyError(Exception):
    pass


class RateLimitExceededError(Exception):
    pass


class InvalidScopeError(Exception):
    pass


@dataclass
class APIKeyConfig:
    """Configuration for API key behavior"""

    prefix: str = "app"
    default_expiry_days: Optional[int] = None
    allowed_scopes: Optional[set[str]] = None
    default_scopes: Optional[list[str]] = None

    def __post_init__(self):
        if self.default_scopes and not self.allowed_scopes:
            raise ValueError("Default scopes provided but no allowed scopes provided")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior"""

    enabled: bool = False
    strategy: Optional[RateLimitStrategy] = None
    limiter: Optional[RateLimiter] = None
    default_limits: Optional[RateLimits] = None
    default_priority: int = 100

    def __post_init__(self):
        if self.enabled and not self.strategy:
            raise ValueError("Rate limiting enabled but no strategy provided")

        if self.enabled and not self.limiter:
            raise ValueError("Rate limiting enabled but no limiter provided")

        if self.enabled and not self.default_limits:
            raise ValueError("Rate limiting enabled but no default limits provided")


class APIKeyBase(BaseModel):
    """
    Abstract Base Class for API Key Authentication.

    Quick Start:
        class SimpleAPIKey(APIKeyBase):
            owner_model = User
            KEY_PREFIX = "myapp"

    Features:

    - Secure key generation and storage
    - Optional rate limiting
    - Optional scoping
    - Optional expiration
    - Key revocation
    """

    meta = {
        "abstract": True,
        "indexes": ["owner", "expires_at", "revoked", "last_used_at"],
    }

    # Required configuration
    owner_model: Optional[Type[BaseModel]] = None
    key_config: APIKeyConfig = APIKeyConfig()
    rate_limit_config: RateLimitConfig = RateLimitConfig()

    name = StringField()
    secret_hashed = StringField(required=True)
    key_preview = StringField(required=True)  # Stores masked version like app-ab...g4
    expires_at = DateTimeField()  # None means key never expires
    revoked = DateTimeField()
    owner = ReferenceField(owner_model, required=True)
    last_used_at = DateTimeField()
    scopes = ListField(StringField())
    rate_limits: RateLimits = DictField()

    def get_effective_rate_limits(self) -> dict[str, int]:
        """Get effective rate limits considering both key and owner limits"""
        owner_limits = self.owner.get_rate_limits()

        if not self.rate_limits:
            return owner_limits.limits

        if self.rate_limits.get("priority", 0) > owner_limits.priority:
            return self.rate_limits

        return owner_limits.limits

    @classmethod
    def generate_key(
        cls,
        owner_id: str | ObjectId,
        expires_in_days: Optional[int] = None,
        scopes: Optional[list[str]] = None,
        rate_limits: Optional[RateLimits] = None,
    ) -> dict:
        """
        Generate a new API key.

        Args:
            owner_id: ID of the key owner
            expires_in_days: Number of days until key expires. None means key never expires
            scopes: List of scopes for the key
            rate_limits: Optional per-key rate limits
        """
        if not cls.owner_model:
            raise NotImplementedError("owner_model must be defined in the subclass.")

        if not isinstance(owner_id, ObjectId) and not ObjectId.is_valid(owner_id):
            raise ValueError("Invalid owner ID")

        owner_id = ObjectId(owner_id) if isinstance(owner_id, str) else owner_id
        expires_in_days = expires_in_days or cls.key_config.default_expiry_days
        scopes = scopes or cls.key_config.default_scopes
        rate_limits = rate_limits or cls.rate_limit_config.default_limits

        if not scopes and cls.key_config.allowed_scopes:
            raise ValueError(
                "Key scopes are required. Either provide scopes or set default_scopes in the key_config."
            )

        if scopes and cls.key_config.allowed_scopes:
            invalid_scopes = set(scopes) - cls.key_config.allowed_scopes
            if invalid_scopes:
                raise InvalidScopeError(f"Invalid scopes: {invalid_scopes}")

        owner_instance = cls.owner_model.objects(id=owner_id).first()
        if not owner_instance:
            raise ValueError("Owner model instance not found.")

        # Generate a new ObjectId for this key
        key_id = str(ObjectId())
        secret_part = secrets.token_urlsafe(16)
        api_key = f"{cls.key_config.prefix}-{key_id}.{secret_part}"

        # Create preview version with masked secret
        key_preview = f"{cls.key_config.prefix}-{key_id[:4]}...{key_id[-4:]}"

        secret_hashed = hashpw(secret_part.encode(), gensalt()).decode()

        # Calculate expires_at based on expires_in_days
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        instance = cls(
            id=key_id,  # Use the same ID in the key string
            key_preview=key_preview,
            secret_hashed=secret_hashed,
            expires_at=expires_at,
            owner=owner_instance,
            scopes=scopes,
            rate_limits=rate_limits,
        )
        instance.save()

        return {
            "api_key": api_key,
            "key_preview": key_preview,
            "expires_at": expires_at,
            "scopes": instance.scopes,
        }

    @classmethod
    def validate_key(
        cls,
        api_key: str,
        required_scopes: Optional[list[str]] = None,
    ) -> BaseModel:
        """
        Validate an API key.

        The API key format is: {prefix}-{key_id}.{secret}
        Example: app-507f1f77bcf86cd799439011.supersecretkey

        Args:
            api_key: The API key to validate
            required_scopes: List of scopes required for the key

        Returns:
            The owner associated with the API key

        Raises:
            ValueError: If the key is invalid, expired, or revoked
        """
        key_id, secret_part = cls._validate_key_format(api_key)

        # Query for active keys using the key_id (which is now the document _id)
        key_record = (
            cls.objects(id=key_id, revoked=None)
            .filter(
                __raw__={
                    "$or": [
                        {"expires_at": None},  # Never expires
                        {"expires_at": {"$gt": datetime.utcnow()}},  # Not expired
                    ]
                }
            )
            .first()
        )

        # Apply rate limiting if configured
        if cls.rate_limit_config.enabled and cls.rate_limit_config.limiter:
            limiter = cls.rate_limit_config.limiter
            strategy = cls.rate_limit_config.strategy

            rate_limit_key = strategy.get_rate_limit_key(
                str(key_record.id), str(key_record.owner.id)
            )
            limits = strategy.get_limits(key_record)

            allowed, limit_info = limiter.check_rate_limit(rate_limit_key, limits)

            if not allowed:
                raise RateLimitExceededError(f"Rate limit exceeded: {limit_info}")

        if not key_record:
            # dummy verify for timing attack resistance
            checkpw(secret_part.encode(), b"dummy")
            raise InvalidAPIKeyError("Invalid API key")

        if not checkpw(secret_part.encode(), key_record.secret_hashed.encode()):
            raise InvalidAPIKeyError("Invalid API key")

        if required_scopes:
            missing_scopes = set(required_scopes) - set(key_record.scopes)
            if missing_scopes:
                raise InvalidScopeError(f"Missing required scopes: {missing_scopes}")

        key_record.update(set__last_used_at=datetime.utcnow())

        return key_record.owner

    def revoke(self):
        """
        Revoke the API key.
        """
        self.update(set__revoked=datetime.utcnow())

    @classmethod
    def list_active_keys(cls, owner_id: str) -> list["APIKeyBase"]:
        """List all active keys for an owner."""
        return (
            cls.objects(owner=owner_id, revoked=None)
            .filter(
                __raw__={
                    "$or": [
                        {"expires_at": None},  # Never expires
                        {"expires_at": {"$gt": datetime.utcnow()}},  # Not expired
                    ]
                }
            )
            .order_by("-created_at")
        )

    @classmethod
    def _validate_key_format(cls, api_key: str) -> tuple[str, str]:
        try:
            prefix, rest = api_key.split("-", 1)
            key_id, secret_part = rest.split(".", 1)

            if prefix != cls.key_config.prefix:
                raise InvalidAPIKeyError("Invalid API key")

            return key_id, secret_part
        except ValueError:
            raise InvalidAPIKeyError("Malformed API key format")

    @staticmethod
    def get_rate_limit_headers(limit_info: RateLimitInfo) -> dict[str, str]:
        """Generate standard rate limit headers."""
        return {
            "X-RateLimit-Limit": str(limit_info["limit"]),
            "X-RateLimit-Remaining": str(limit_info["remaining"]),
            "X-RateLimit-Reset": limit_info["reset"],
        }
