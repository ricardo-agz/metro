from datetime import datetime, timedelta
import secrets
from typing import Optional, ClassVar, Protocol, TypeVar, Type

from metro.models import (
    BaseModel,
    BooleanField,
    DateTimeField,
    EmbeddedDocument,
    EmbeddedDocumentField,
    StringField,
)
from metro.exceptions import UnauthorizedError
from metro.auth.user.mixins.typing import T


class EmailVerificationToken(EmbeddedDocument):
    """Embedded document for email verification token data"""

    token = StringField()
    expires_at = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)


class EmailVerificationMixin:
    """Mixin to add email verification functionality"""

    email_verified = BooleanField(default=False)
    email_verification = EmbeddedDocumentField(EmailVerificationToken)

    meta = {"abstract": True, "indexes": ["email_verification.token"]}

    def generate_verification_token(self: T) -> str:
        """Generate a secure email verification token"""
        token = secrets.token_urlsafe()
        self.email_verification = EmailVerificationToken(
            token=token, expires_at=datetime.utcnow() + timedelta(days=1)
        )
        self.save()
        return token

    def verify_email(self: T, token: str) -> bool:
        """Verify email with token"""
        if (
            not self.email_verification
            or self.email_verification.token != token
            or self.email_verification.expires_at < datetime.utcnow()
        ):
            return False

        self.email_verified = True
        self.email_verification = None  # Clear token after use
        self.save()
        return True

    @classmethod
    def find_by_email_verification_token(
        cls: Type[T], token: str
    ) -> Optional["BaseModel"]:
        """Find a user by their email verification token if it's still valid"""
        return cls.objects(
            email_verification__token=token,
            email_verification__expires_at__gt=datetime.utcnow(),
        ).first()

    # Override authenticate to enforce email verification
    @classmethod
    def authenticate(
        cls: Type[T], identifier: str, password: str
    ) -> Optional["BaseModel"]:
        """Authenticate a user and verify their email is verified"""
        user = super(EmailVerificationMixin, cls).authenticate(identifier, password)
        if user and not user.email_verified:
            raise UnauthorizedError(
                "Email not verified. Please verify your email before logging in."
            )
        return user
