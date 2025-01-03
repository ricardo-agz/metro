from datetime import datetime, timedelta
from typing import Optional
import jwt
from mongoengine import Q

from pyrails.models import (
    BaseModel,
    StringField,
    BooleanField,
    EmailField,
    DateTimeField,
    HashedField,
)
from pyrails.config import config


class UserBase(BaseModel):
    """
    Abstract base class for User models providing core authentication functionality.
    Inherits from BaseModel for common model operations.
    """

    AUTH_FIELDS = ["username", "email"]

    username = StringField(required=True, unique=True, max_length=150)
    email = EmailField(required=True, unique=True)
    password_hash = HashedField(required=True)
    is_staff = BooleanField(default=False)  # Can access admin site
    is_superuser = BooleanField(default=False)  # Has all permissions
    last_login = DateTimeField()

    meta = {
        "abstract": True,
        "indexes": [
            "username",
            "email",
            {"fields": ["username"], "unique": True},
            {"fields": ["email"], "unique": True},
        ],
    }

    @classmethod
    def find_by_username(cls, username: str) -> Optional["UserBase"]:
        """Find a user by username"""
        return cls.objects(username=username).first()

    @classmethod
    def authenticate(cls, identifier: str, password: str) -> Optional["UserBase"]:
        """Authenticate a user by username or email and password"""
        query = Q()
        for field_name in cls.AUTH_FIELDS:
            query = query | Q(**{field_name: identifier})

        user = cls.objects(query).first()
        if not user:
            cls.password_hash.dummy_verify()
            return None

        if user.verify_password(password):
            return user

        return None

    def verify_password(self, password: str) -> bool:
        """Verify if the provided password matches the stored hash"""
        return self.password_hash.verify(password)

    def get_auth_token(self, expires_in: int = 3600, secret_key: str = None) -> str:
        """
        Generate a JWT token for the user

        Args:
            expires_in: Token expiration time in seconds (default: 1 hour)
            secret_key: The secret key to sign the token (default: config.JWT_SECRET_KEY)
        """
        if not secret_key:
            secret_key = config.JWT_SECRET_KEY
        expiration = datetime.utcnow() + timedelta(seconds=expires_in)
        payload = {"user_id": str(self.id), "exp": expiration}
        return jwt.encode(payload, secret_key, algorithm="HS256")

    @classmethod
    def verify_auth_token(
        cls, token: str, secret_key: str = None
    ) -> Optional["UserBase"]:
        """
        Verify a JWT token and return the corresponding user

        Args:
            token: The JWT token to verify
            secret_key: The secret key used to sign the token

        Returns:
            The user object if token is valid, None otherwise
        """
        if not secret_key:
            secret_key = config.JWT_SECRET_KEY
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            user = cls.find_by_id(payload["user_id"])
            if user:
                return user
            return None
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    class Meta:
        abstract = True