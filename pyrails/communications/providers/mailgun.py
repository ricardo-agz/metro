import os
import requests
from typing import List

from pyrails.communications.providers import EmailProvider
from pyrails.logger import logger
import httpx
from pyrails.config import config


class MailgunProvider(EmailProvider):
    def __init__(self, domain: str = None, api_key: str = None):
        mailgun_configured = hasattr(config, "MAILGUN_DOMAIN") and hasattr(
            config, "MAILGUN_API_KEY"
        )
        if not mailgun_configured and not (domain and api_key):
            raise ValueError(
                "MailgunProvider requires domain and api_key arguments or MAILGUN_DOMAIN and MAILGUN_API_KEY in config."
            )

        self.domain = domain or config.MAILGUN_DOMAIN
        self.api_key = api_key or os.getenv("MAILGUN_API_KEY")

    def send_email(self, source: str, recipients: list[str], subject: str, body: str):
        response = requests.post(
            f"https://api.mailgun.net/v3/{self.domain}/messages",
            auth=("api", self.api_key),
            data={
                "from": source,
                "to": recipients,
                "subject": subject,
                "html": body,
            },
        )
        if response.status_code != 200:
            logger.error(f"Mailgun API error: {response.status_code} - {response.text}")
            response.raise_for_status()
        logger.info(f"Email sent via Mailgun to {recipients} with subject '{subject}'.")

    async def send_email_async(
        self, source: str, recipients: List[str], subject: str, body: str
    ):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.mailgun.net/v3/{self.domain}/messages",
                auth=("api", self.api_key),
                data={
                    "from": source,
                    "to": recipients,
                    "subject": subject,
                    "html": body,
                },
            )
            if response.status_code != 200:
                logger.error(
                    f"Mailgun API async error: {response.status_code} - {response.text}"
                )
                response.raise_for_status()
            logger.info(
                f"Email sent via Mailgun (async) to {recipients} with subject '{subject}'."
            )
