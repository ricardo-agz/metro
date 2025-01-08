import httpx
from metro.communications.providers import SMSProvider, ProviderNotConfiguredError
from metro.logger import logger
from metro.config import config


class TwilioProvider(SMSProvider):
    def __init__(self, account_sid: str = None, auth_token: str = None):
        twilio_configured = hasattr(config, "TWILIO_ACCOUNT_SID") and hasattr(
            config, "TWILIO_AUTH_TOKEN"
        )
        if not twilio_configured and not (account_sid and auth_token):
            raise ProviderNotConfiguredError(
                "TwilioProvider requires account_sid and auth_token arguments or TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in config."
            )

        self.account_sid = account_sid or config.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or config.TWILIO_AUTH_TOKEN
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

    def send_sms(self, source: str, recipients: list[str], message: str) -> None:
        with httpx.Client() as client:
            for recipient in recipients:
                kwargs = {"To": recipient, "Body": message}
                if source:
                    kwargs["From"] = source
                try:
                    response = client.post(
                        self.base_url,
                        auth=(self.account_sid, self.auth_token),
                        data=kwargs,
                    )
                    if response.status_code not in (200, 201):
                        raise Exception(
                            f"Twilio API error: {response.status_code} - {response.text}"
                        )
                    response_data = response.json()
                    logger.info(
                        f"SMS sent via Twilio to {recipient}. Message SID: {response_data['sid']}"
                    )
                except Exception as e:
                    logger.error(f"Twilio error sending to {recipient}: {e}")
                    raise

    async def send_sms_async(
        self, source: str, recipients: list[str], message: str
    ) -> None:
        async with httpx.AsyncClient() as client:
            for recipient in recipients:
                kwargs = {"To": recipient, "Body": message}
                if source:
                    kwargs["From"] = source
                try:
                    response = await client.post(
                        self.base_url,
                        auth=(self.account_sid, self.auth_token),
                        data=kwargs,
                    )
                    if response.status_code not in (200, 201):
                        raise Exception(
                            f"Twilio API error: {response.status_code} - {response.text}"
                        )
                    response_data = response.json()
                    logger.info(
                        f"SMS sent via Twilio (async) to {recipient}. Message SID: {response_data['sid']}"
                    )
                except Exception as e:
                    logger.error(f"Twilio async error sending to {recipient}: {e}")
                    raise
