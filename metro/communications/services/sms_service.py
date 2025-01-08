from typing import Optional

from metro.communications.providers import SMSProvider, TwilioProvider, VonageProvider
from metro.communications.providers.base import ProviderNotConfiguredError
from metro.logger import logger
from metro.config import config


class SMSSender:
    def __init__(
        self,
        provider: Optional[SMSProvider] = None,
    ):
        """
        Initialize the EmailSender.

        :param provider: An instance of SMSProvider. If None, defaults to Twilio or Vonage based on environment variables.
        :raises ValueError: If no provider is configured or templates directory is not found.
        """
        self.provider = self._initialize_provider(provider)

    @staticmethod
    def _initialize_provider(provider: Optional[SMSProvider]) -> SMSProvider:
        if provider:
            logger.debug("Using provided EmailProvider.")
            return provider

        twilio_configured = hasattr(config, "TWILIO_ACCOUNT_SID") and hasattr(
            config, "TWILIO_AUTH_TOKEN"
        )
        vonage_configured = hasattr(config, "VONAGE_API_KEY") and hasattr(
            config, "VONAGE_API_SECRET"
        )

        if twilio_configured:
            twilio_account_sid = config.TWILIO_ACCOUNT_SID
            twilio_auth_token = config.TWILIO_AUTH_TOKEN
            logger.info("Configuring TwilioProvider based on config.")
            return TwilioProvider(
                account_sid=twilio_account_sid, auth_token=twilio_auth_token
            )
        else:
            logger.error(
                "No sms provider configured. Please set Twilio or Vonage environment variables."
            )
            raise ProviderNotConfiguredError(
                "No sms provider configured. Please set Twilio or Vonage environment variables."
            )

    def send_sms(self, recipients: list[str], message: str, source: str = None) -> None:
        """
        Send an SMS message.

        :param source: Sender's phone number or identifier
        :param recipients: List of recipient phone numbers
        :param message: Message content
        """
        self.provider.send_sms(recipients=recipients, message=message, source=source)

    async def send_sms_async(
        self, recipients: list[str], message: str, source: str = None
    ) -> None:
        """
        Asynchronously send an SMS message.
        """
        await self.provider.send_sms_async(
            recipients=recipients, message=message, source=source
        )


# Usage example:
if __name__ == "__main__":
    # For Mailgun
    # mailgun_provider = MailgunProvider(
    #     domain=os.getenv("MAILGUN_DOMAIN"), api_key=os.getenv("MAILGUN_API_KEY")
    # )
    # mailgun_sender = EmailSender(provider=mailgun_provider)

    # For AWS SES
    # ses_provider = AWSESProvider(region_name="us-west-2")
    # ses_sender = EmailSender(provider=ses_provider)

    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Twilio
    twilio_provider = TwilioProvider(
        account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
    )
    twilio_sender = SMSSender(provider=twilio_provider)

    # Vonage
    vonage_provider = VonageProvider(
        api_key=os.getenv("VONAGE_API_KEY"), api_secret=os.getenv("VONAGE_API_SECRET")
    )
    vonage_sender = SMSSender(provider=vonage_provider)

    vonage_sender.send_sms(
        source="13132706395",
        recipients=["+12103314099"],
        message="Hello from Vonage!",
    )
    # send email w twilio

    # # Using Mailgun
    # mailgun_sender.send_email(
    #     source="sender@example.com",
    #     recipients=["recipient@example.com"],
    #     subject="Test Email",
    #     body="This is a test email sent using Mailgun.",
    # )
    #
    # # Using AWS SES
    # ses_sender.send_email(
    #     source="sender@example.com",
    #     recipients=["recipient@example.com"],
    #     subject="Test Email",
    #     body="This is a test email sent using AWS SES.",
    # )
