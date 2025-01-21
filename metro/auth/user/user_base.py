import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt
from mongoengine import Q

from metro.models import (
    BaseModel,
    StringField,
    BooleanField,
    EmailField,
    DateTimeField,
    HashedField,
    EmbeddedDocument,
    EmbeddedDocumentField,
)
from metro.config import config


class PasswordResetToken(EmbeddedDocument):
    token = StringField()
    expires_at = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)


class UserBase(BaseModel):
    """
    Abstract base class for User models providing core authentication functionality.
    Inherits from BaseModel for common model operations.
    """

    auth_fields = ["username", "email"]

    username = StringField(required=True, unique=True, max_length=150)
    email = EmailField(required=True, unique=True)
    password_hash = HashedField(required=True)
    is_staff = BooleanField(default=False)  # Can access admin site
    is_superuser = BooleanField(default=False)  # Has all permissions
    last_login = DateTimeField()

    password_reset = EmbeddedDocumentField(PasswordResetToken)

    meta = {
        "abstract": True,
        "indexes": [
            "username",
            "email",
            {"fields": ["username"], "unique": True},
            {"fields": ["email"], "unique": True},
            "password_reset.token",
        ],
    }

    @classmethod
    def find_by_username(cls, username: str) -> Optional["UserBase"]:
        """Find a user by username"""
        return cls.objects(username=username).first()

    @classmethod
    def find_by_email(cls, email: str) -> Optional["UserBase"]:
        """Find a user by email"""
        return cls.objects(email=email).first()

    @classmethod
    def find_by_auth_identifier(cls, identifier: str) -> Optional["UserBase"]:
        """Find a user by username or email"""
        query = Q()
        for field_name in cls.auth_fields:
            query = query | Q(**{field_name: identifier})

        return cls.objects(query).first()

    @classmethod
    def authenticate(cls, identifier: str, password: str) -> Optional["UserBase"]:
        """Authenticate a user by username or email and password"""
        query = Q()
        for field_name in cls.auth_fields:
            query = query | Q(**{field_name: identifier})

        user = cls.objects(query).first()
        if not user:
            cls.password_hash.dummy_verify()
            return None

        if user.password_hash.verify(password):
            return user

        return None

    def generate_auth_token(
        self, expires_in: int = 3600, secret_key: str = None
    ) -> str:
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
            return cls.find_by_id(payload["user_id"])

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def generate_password_reset_token(self) -> str:
        """Generate a secure password reset token"""
        token = secrets.token_urlsafe()
        self.password_reset = PasswordResetToken(
            token=token, expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        self.save()
        return token

    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using reset token"""
        if (
            not self.password_reset
            or self.password_reset.token != token
            or self.password_reset.expires_at < datetime.utcnow()
        ):
            return False

        self.password_hash = new_password
        self.password_reset = None  # Clear token after use
        self.save()
        return True

    @classmethod
    def find_by_password_reset_token(cls, token: str) -> Optional["UserBase"]:
        """Find a user by their password reset token if it's still valid"""
        return cls.objects(
            password_reset__token=token,
            password_reset__expires_at__gt=datetime.utcnow(),
        ).first()
