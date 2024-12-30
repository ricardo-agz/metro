import httpx
from pyrails.communications.providers import SMSProvider, ProviderNotConfiguredError
from pyrails.logger import logger
from pyrails.config import config


class VonageProvider(SMSProvider):
    def __init__(self, api_key: str = None, api_secret: str = None):
        vonage_configured = hasattr(config, "VONAGE_API_KEY") and hasattr(
            config, "VONAGE_API_SECRET"
        )
        if not vonage_configured and not (api_key and api_secret):
            raise ProviderNotConfiguredError(
                "VonageProvider requires api_key and api_secret arguments or VONAGE_API_KEY and VONAGE_API_SECRET in config."
            )

        self.api_key = api_key or config.VONAGE_API_KEY
        self.api_secret = api_secret or config.VONAGE_API_SECRET

    def send_sms(self, source: str, recipients: list[str], message: str) -> None:
        for recipient in recipients:
            try:
                response = httpx.post(
                    "https://rest.nexmo.com/sms/json",
                    data={
                        "to": recipient,
                        "from": source,
                        "text": message,
                        "api_key": self.api_key,
                        "api_secret": self.api_secret,
                    },
                )

                response_data = response.json()
                if (
                    response.status_code == 200
                    and response_data["messages"][0]["status"] == "0"
                ):
                    logger.info(
                        f"SMS sent via Vonage to {recipient}. "
                        f"Message ID: {response_data['messages'][0]['message-id']}"
                    )
                else:
                    error_text = response_data["messages"][0].get(
                        "error-text", "Unknown error"
                    )
                    raise Exception(f"Vonage API error: {error_text}")

            except Exception as e:
                logger.error(f"Vonage error sending to {recipient}: {e}")
                raise

    async def send_sms_async(
        self, source: str, recipients: list[str], message: str
    ) -> None:
        async with httpx.AsyncClient() as client:
            for recipient in recipients:
                try:
                    response = await client.post(
                        "https://rest.nexmo.com/sms/json",
                        data={
                            "to": recipient,
                            "from": source,
                            "text": message,
                            "api_key": self.api_key,
                            "api_secret": self.api_secret,
                        },
                    )

                    response_data = response.json()
                    if (
                        response.status_code == 200
                        and response_data["messages"][0]["status"] == "0"
                    ):
                        logger.info(
                            f"SMS sent via Vonage (async) to {recipient}. "
                            f"Message ID: {response_data['messages'][0]['message-id']}"
                        )
                    else:
                        error_text = response_data["messages"][0].get(
                            "error-text", "Unknown error"
                        )
                        raise Exception(f"Vonage API error: {error_text}")

                except Exception as e:
                    logger.error(f"Vonage async error sending to {recipient}: {e}")
                    raise
