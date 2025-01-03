import base64
import hashlib
import hmac
import time
from abc import abstractmethod, ABC
from dataclasses import dataclass, fields
from enum import Enum
import secrets
from datetime import datetime, timedelta
from typing import Optional, TypedDict, Union
from urllib.parse import quote

from pyrails.communications import SMSSender, SMSProvider, EmailSender, EmailProvider
from pyrails.models import (
    BaseModel,
    BooleanField,
    IntField,
    ListField,
    StringField,
    DateTimeField,
    DictField,
)
from pyrails.logger import logger
from pyrails.utils.generate_qr_code import generate_qr_code_b64


class TooManyAttemptsError(Exception):
    pass


@dataclass
class TOTPConfig:
    """TOTP-specific configuration"""

    digits: int = 6
    interval: int = 30  # seconds
    algorithm: str = "sha1"  # Most TOTP apps use SHA1
    secret_length: int = 32  # bytes
    tolerance: int = 1  # Number of intervals to check before/after current time
    issuer: str = "MetroApp"
    account_name_attr: str = "email"


@dataclass
class TFATemplateConfig:
    """Configuration for TFA message templates"""

    # Email template configuration
    email_template_name: Optional[str] = None
    email_subject: str = "Two-Factor Authentication Code"
    email_context: dict = None

    # SMS template configuration
    sms_template: str = "Your verification code is: {code}"
    sms_context: dict = None

    def __post_init__(self):
        if self.email_context is None:
            self.email_context = {}
        if self.sms_context is None:
            self.sms_context = {}


@dataclass
class TFASettings:
    code_length: int = 6
    code_expiry_minutes: int = 5
    max_verification_attempts: int = 3
    attempt_window_minutes: int = 5
    lockout_duration_minutes: int = 5
    max_lockouts_before_admin: int = 3
    backup_codes_count: int = 8
    hash_algorithm: str = "sha256"
    templates: TFATemplateConfig = None
    totp: TOTPConfig = None

    def __post_init__(self):
        if self.code_length < 4:
            raise ValueError("code_length must be at least 4")
        if self.max_verification_attempts < 1:
            raise ValueError("max_verification_attempts must be positive")
        if self.attempt_window_minutes < 1:
            raise ValueError("attempt_window_minutes must be positive")
        if self.lockout_duration_minutes < 1:
            raise ValueError("lockout_duration_minutes must be positive")
        if self.max_lockouts_before_admin < 1:
            raise ValueError("max_lockouts_before_admin must be positive")
        if self.code_expiry_minutes < 1:
            raise ValueError("code_expiry_minutes must be positive")
        if self.backup_codes_count < 1:
            raise ValueError("backup_codes_count must be positive")
        if not self.hash_algorithm:
            raise ValueError("hash_algorithm must be specified")
        if self.templates is None:
            self.templates = TFATemplateConfig()
        if self.totp is None:
            self.totp = TOTPConfig()

    @classmethod
    def from_dict(cls, settings=None):
        if settings is None:
            return cls()

        # Handle nested template configuration
        if "templates" in settings:
            settings["templates"] = TFATemplateConfig(**settings["templates"])

        return cls(**{k: v for k, v in settings.items() if k in cls.__annotations__})


class TwoFactorMethod(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    TOTP = "totp"
    BACKUP_CODES = "backup_codes"


class TwoFactorProviderBase(ABC):
    @abstractmethod
    def send_code(self, destination: str, code: str) -> None:
        pass

    @abstractmethod
    def validate_destination(self, destination: str) -> bool:
        pass


class SMSTwoFactorProvider(TwoFactorProviderBase):
    def __init__(self, sms_sender: SMSSender = None, sms_provider: SMSProvider = None):
        if sms_sender:
            self.sms_sender = sms_sender
        else:
            self.sms_sender = SMSSender(provider=sms_provider)

    def send_code(
        self, destination: str, code: str, settings: TFASettings = None
    ) -> None:
        if not settings:
            settings = TFASettings()

        template = settings.templates.sms_template
        context = {
            **settings.templates.sms_context,
            "code": code,
            "expiry_minutes": settings.code_expiry_minutes,
        }

        # Format the message with the context
        try:
            message = template.format(**context)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            # Fallback to basic template
            message = f"Your verification code is: {code}"

        self.sms_sender.send_sms([destination], message)

    def validate_destination(self, destination: str) -> bool:
        return bool(destination and len(destination) >= 10)


class EmailTwoFactorProvider(TwoFactorProviderBase):
    def __init__(
        self,
        source: str,
        email_sender: EmailSender = None,
        email_provider: EmailProvider = None,
    ):
        self.source = source
        if email_sender:
            self.email_sender = email_sender
        else:
            self.email_sender = EmailSender(provider=email_provider)

    def send_code(
        self, destination: str, code: str, settings: TFASettings = None
    ) -> None:
        if not settings:
            settings = TFASettings()

        # If a template is specified, use it with the provided context
        if settings.templates.email_template_name:
            context = {
                **settings.templates.email_context,
                "code": code,
                "expiry_minutes": settings.code_expiry_minutes,
            }

            self.email_sender.send_email(
                source=self.source,
                recipients=[destination],
                subject=settings.templates.email_subject,
                template_name=settings.templates.email_template_name,
                context=context,
            )
        else:
            # Fallback to basic email
            body = f"Your verification code is: {code}"
            self.email_sender.send_email(
                source=self.source,
                recipients=[destination],
                subject=settings.templates.email_subject,
                body=body,
            )

    def validate_destination(self, destination: str) -> bool:
        return bool(destination and "@" in destination and "." in destination)


class TOTPTwoFactorProvider(TwoFactorProviderBase):
    """
    TOTP (Time-based One-Time Password) provider implementation.
    Compatible with Google Authenticator, Authy, and other TOTP apps.
    """

    def send_code(self, destination: str, code: str) -> None:
        """
        TOTP doesn't send codes - they're generated by the app.
        This method exists to satisfy the interface but does nothing.
        """
        pass

    def validate_destination(self, destination: str) -> bool:
        """
        For TOTP, the destination is the secret key.
        Validate it's in the correct base32 format.
        """
        try:
            # Check if it's a valid base32 string
            base64.b32decode(destination.upper())
            return True
        except Exception:
            return False

    def get_totp_uri(
        self, entity: "BaseModel", secret: str, settings: TFASettings
    ) -> str:
        """
        Generate the otpauth URI using configured settings.
        """
        totp_config = settings.totp
        account_name = getattr(entity, totp_config.account_name_attr, str(entity.id))

        encoded_issuer = quote(totp_config.issuer)
        encoded_account = quote(account_name)

        return (
            f"otpauth://totp/{encoded_issuer}:{encoded_account}?"
            f"secret={secret}&issuer={encoded_issuer}"
            f"&algorithm={totp_config.algorithm.upper()}"
            f"&digits={totp_config.digits}"
            f"&period={totp_config.interval}"
        )

    def verify_code(self, secret: str, code: str, settings: TFASettings) -> bool:
        """
        Verify a TOTP code using configured settings.
        """
        if not code or not secret:
            return False

        try:
            code_int = int(code)
            now = time.time()

            # Use settings for verification
            totp_config = settings.totp

            # Check codes within tolerance
            for i in range(-totp_config.tolerance, totp_config.tolerance + 1):
                if (
                    self._generate_code(
                        secret, now + i * totp_config.interval, totp_config
                    )
                    == code_int
                ):
                    return True

            return False
        except (ValueError, TypeError):
            return False

    def _generate_code(self, secret: str, timestamp: float, config: TOTPConfig) -> int:
        """Generate TOTP code using configured settings."""
        # Calculate counter
        counter = int(timestamp // config.interval)

        # Decode secret
        key = base64.b32decode(secret.upper())

        # Create counter bytes
        counter_bytes = counter.to_bytes(8, byteorder="big")

        # Calculate HMAC
        hmac_obj = hmac.new(key, counter_bytes, config.algorithm)
        hmac_result = hmac_obj.digest()

        # Get offset
        offset = hmac_result[-1] & 0xF

        # Generate code
        code_bytes = hmac_result[offset : offset + 4]
        code_int = int.from_bytes(code_bytes, byteorder="big")

        # Apply modulus to get desired number of digits
        code = code_int & 0x7FFFFFFF
        code = code % (10**config.digits)

        return code

    def setup_totp(self, entity: "BaseModel", settings: TFASettings) -> dict:
        """
        Set up TOTP for a user.
        Returns the secret and URI for QR code generation.
        """
        secret = base64.b32encode(
            secrets.token_bytes(settings.totp.secret_length)
        ).decode()
        uri = self.get_totp_uri(entity, secret, settings)
        qr_code = generate_qr_code_b64(uri)

        return {"secret": secret, "uri": uri, "qr_code": qr_code}


@dataclass
class TFAProviders:
    sms: SMSTwoFactorProvider = None
    email: EmailTwoFactorProvider = None
    totp: TOTPTwoFactorProvider = None

    def __post_init__(self):
        if not self.sms and not self.email and not self.totp:
            raise ValueError("At least one 2FA provider must be specified")

    @classmethod
    def from_dict(cls, providers: dict) -> "TFAProviders":
        filtered_providers = {
            k: v for k, v in providers.items() if k in cls.__annotations__
        }
        return cls(**filtered_providers)


class MethodConfig(TypedDict):
    enabled: bool
    destination: str


class VerificationState(TypedDict):
    code_hash: str
    expires_at: datetime
    method: str


class TwoFactorAuthMixin:
    tfa_methods: dict[str, MethodConfig] = DictField(default=dict)
    tfa_verification: VerificationState | None = DictField()
    tfa_attempts: int = IntField(default=0)
    tfa_last_attempt: datetime | None = DateTimeField()
    tfa_lockout_until: datetime | None = DateTimeField()
    tfa_lockout_count: int = IntField(
        default=0
    )  # Track number of times account has been locked out
    tfa_backup_codes: list[str] = ListField(StringField(), default=list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tfa_settings: TFASettings = TFASettings()
        self.tfa_providers: TFAProviders

        # Check for either style of config
        config = None
        if hasattr(self, "TFAConfig"):
            config = self.TFAConfig
        elif hasattr(self, "tfa_config"):
            config = type("TFAConfig", (), self.tfa_config)

        # Apply config if found
        if config:
            if hasattr(config, "providers"):
                # Use from_dict for both dict and TFAProviders instances
                providers_data = (
                    config.providers.__dict__
                    if not isinstance(config.providers, dict)
                    else config.providers
                )
                self.tfa_providers = TFAProviders.from_dict(providers_data)

            if hasattr(config, "settings"):
                # Use from_dict for both dict and TFASettings instances
                settings_data = (
                    config.settings.__dict__
                    if not isinstance(config.settings, dict)
                    else config.settings
                )
                self.tfa_settings = TFASettings.from_dict(settings_data)

        if not self.tfa_providers:
            raise ValueError("No 2FA providers configured")

    def check_verification_allowed(self) -> tuple[bool, Optional[str]]:
        """
        Check if verification attempts are allowed.
        Returns (allowed, reason_if_not_allowed)
        """
        now = datetime.utcnow()

        # Check if currently in lockout period
        if self.tfa_lockout_until and now < self.tfa_lockout_until:
            minutes_remaining = int((self.tfa_lockout_until - now).total_seconds() / 60)
            return (
                False,
                f"Account is temporarily locked. Try again in {minutes_remaining} minutes.",
            )

        # Check if requiring admin intervention
        if self.tfa_lockout_count >= self.tfa_settings.max_lockouts_before_admin:
            return (
                False,
                "Account is locked due to too many failed attempts. Please contact support.",
            )

        # Reset attempts if outside attempt window
        if self.tfa_last_attempt and now - self.tfa_last_attempt > timedelta(
            minutes=self.tfa_settings.attempt_window_minutes
        ):
            self.tfa_attempts = 0

        return True, None

    def record_verification_attempt(self, success: bool):
        """
        Record a verification attempt and handle lockouts
        """
        now = datetime.utcnow()
        self.tfa_last_attempt = now

        if success:
            # Reset attempts and lockout count on successful verification
            self.tfa_attempts = 0
            self.tfa_lockout_until = None
            self.tfa_lockout_count = 0
        else:
            self.tfa_attempts += 1

            # Check if we need to trigger a lockout
            if self.tfa_attempts >= self.tfa_settings.max_verification_attempts:
                self.tfa_lockout_count += 1
                self.tfa_lockout_until = now + timedelta(
                    minutes=self.tfa_settings.lockout_duration_minutes
                )
                self.tfa_attempts = 0

        self.save()

    def admin_reset_lockout(self):
        """Allow admins to reset lockout state"""
        self.tfa_attempts = 0
        self.tfa_lockout_until = None
        self.tfa_lockout_count = 0
        self.save()

    def _hash_code(self, code: str) -> str:
        """Hash a verification code using SHA-256."""
        return hashlib.sha256(code.encode()).hexdigest()

    def get_provider(self, method: TwoFactorMethod) -> Optional[TwoFactorProviderBase]:
        return self.tfa_providers.__dict__.get(method.value)

    def enable_method(
        self, method: TwoFactorMethod, destination: str
    ) -> Optional[list[str]]:
        """
        Enable a specific 2FA method for the user.
        Returns backup codes if this is the first enabled method.
        """
        provider = self.get_provider(method)
        if not provider or not provider.validate_destination(destination):
            return None

        self.tfa_methods[method.value] = {
            "enabled": True,
            "destination": destination,
        }

        # Generate backup codes if this is the first enabled method
        backup_codes = None
        if len(self.tfa_methods) == 1:
            backup_codes = self._generate_backup_codes()
            self.backup_code_hashes = [self._hash_code(code) for code in backup_codes]

        self.save()
        return backup_codes

    def disable_method(self, method: TwoFactorMethod) -> None:
        """Disable a specific 2FA method."""
        if method.value in self.tfa_methods:
            del self.tfa_methods[method.value]
            if not self.tfa_methods:
                self.backup_code_hashes = []
            self.save()

    def get_enabled_methods(self) -> list[TwoFactorMethod]:
        """Get list of enabled 2FA methods."""
        return [TwoFactorMethod(method) for method in self.tfa_methods.keys()]

    def generate_verification_code(self, method: TwoFactorMethod) -> Optional[str]:
        """Generate a new verification code for the specified method."""
        if (
            method.value not in self.tfa_methods
            or not self.tfa_methods[method.value]["enabled"]
        ):
            return None

        if self.tfa_attempts >= self.tfa_settings.max_verification_attempts:
            raise TooManyAttemptsError("Too many verification attempts")

        code = "".join(
            secrets.choice("0123456789") for _ in range(self.tfa_settings.code_length)
        )

        self.tfa_verification = {
            "code_hash": self._hash_code(code),
            "expires_at": datetime.utcnow()
            + timedelta(minutes=self.tfa_settings.code_expiry_minutes),
            "method": method.value,
        }

        self.save()
        return code

    def send_verification_code(self, method: TwoFactorMethod) -> bool:
        """Send a verification code using the specified method."""
        if (
            method.value not in self.tfa_methods
            or not self.tfa_methods[method.value]["enabled"]
        ):
            return False

        provider = self.get_provider(method)
        if not provider:
            return False

        destination = self.tfa_methods[method.value]["destination"]
        code = self.generate_verification_code(method)

        if not code:
            return False

        try:
            provider.send_code(destination, code)
            return True
        except Exception as e:
            logger.error(f"Failed to send verification code: {e}")
            return False

    async def send_verification_code_async(self, method: TwoFactorMethod) -> bool:
        if not self._validate_method(method):
            return False

        provider = self.get_provider(method)
        if not provider:
            return False

        destination = self.tfa_methods[method.value]["destination"]
        code = self.generate_verification_code(method)

        try:
            provider.send_code(destination, code)
            return True
        except Exception as e:
            logger.error(f"Failed to send verification code: {e}")
            return False

    def verify_code(self, code: str, method: Optional[TwoFactorMethod] = None) -> bool:
        """
        Verify the provided code. If method is specified, only verify against that method.
        """
        allowed, reason = self.check_verification_allowed()
        if not allowed:
            raise TooManyAttemptsError(reason)

        if method == TwoFactorMethod.TOTP:
            provider: TOTPTwoFactorProvider = self.tfa_providers.totp
            if not provider or not self._validate_method(method):
                return False

            secret = self.tfa_methods[method.value]["destination"]
            return provider.verify_code(secret, code, self.tfa_settings)

        if not self.tfa_verification:
            self.record_verification_attempt(False)
            return False

        if datetime.utcnow() > self.tfa_verification["expires_at"]:
            self.record_verification_attempt(False)
            return False

        if method and method.value != self.tfa_verification["method"]:
            self.record_verification_attempt(False)
            return False

        if self._hash_code(code) != self.tfa_verification["code_hash"]:
            self.record_verification_attempt(False)
            return False

        # Success path
        self.tfa_verification = None
        self.record_verification_attempt(True)
        return True

    def verify_backup_code(self, code: str) -> bool:
        """Verify and consume a backup code."""
        code_hash = self._hash_code(code)
        if code_hash in self.backup_code_hashes:
            self.backup_code_hashes.remove(code_hash)
            self.save()
            return True
        return False

    def _generate_backup_codes(self) -> list[str]:
        """Generate new backup codes."""
        return [
            secrets.token_hex(4) for _ in range(self.tfa_settings.backup_codes_count)
        ]

    def requires_two_factor(self) -> bool:
        """Check if the user has any 2FA methods enabled."""
        return bool(self.tfa_methods)

    def _validate_method(self, method: TwoFactorMethod) -> bool:
        return (
            method.value in self.tfa_methods
            and self.tfa_methods[method.value]["enabled"]
        )

    def refresh_backup_codes(self) -> list[str]:
        """Generate a new set of backup codes, invalidating old ones."""
        new_codes = self._generate_backup_codes()
        self.backup_code_hashes = [self._hash_code(code) for code in new_codes]
        self.save()
        return new_codes

    def enable_totp(self) -> dict:
        """
        Enable TOTP for the user.
        Returns the TOTP secret and URI for QR code generation.
        """
        provider: TOTPTwoFactorProvider = self.tfa_providers.totp
        if not provider:
            raise ValueError("TOTP provider not configured")

        # Generate secret and URI
        totp_data = provider.setup_totp(self, self.tfa_settings)

        # Store the secret as the destination
        self.tfa_methods[TwoFactorMethod.TOTP.value] = {
            "enabled": True,
            "destination": totp_data["secret"],
        }

        # Generate backup codes if this is the first enabled method
        backup_codes = None
        if len(self.tfa_methods) == 1:
            backup_codes = self._generate_backup_codes()
            self.backup_code_hashes = [self._hash_code(code) for code in backup_codes]

        self.save()

        result = {
            "secret": totp_data["secret"],
            "uri": totp_data["uri"],
            "qr_code": totp_data["qr_code"],
        }
        if backup_codes:
            result["backup_codes"] = backup_codes

        return result
