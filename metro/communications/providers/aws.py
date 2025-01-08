from typing import List
from metro.logger import logger
from metro.communications.providers.base import EmailProvider


try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    import aioboto3

    AIOBOTO3_AVAILABLE = True
except ImportError:
    AIOBOTO3_AVAILABLE = False


class AWSESProvider(EmailProvider):
    def __init__(self, region_name: str = "us-west-2"):
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for AWSESProvider but is not installed."
            )
        self.region_name = region_name
        self.client = boto3.client("ses", region_name=region_name)

    def send_email(self, source: str, recipients: List[str], subject: str, body: str):
        try:
            response = self.client.send_email(
                Source=source,
                Destination={"ToAddresses": recipients},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": body}},
                },
            )
            logger.info(
                f"Email sent via AWS SES to {recipients} with subject '{subject}'. Message ID: {response['MessageId']}"
            )
        except Exception as e:
            logger.error(f"AWS SES error: {e}")
            raise

    async def send_email_async(
        self, source: str, recipients: List[str], subject: str, body: str
    ):
        if not AIOBOTO3_AVAILABLE:
            raise ImportError(
                "aioboto3 is required for async AWSESProvider but is not installed."
            )
        session = aioboto3.Session()
        async with session.client("ses", region_name=self.region_name) as client:
            try:
                response = await client.send_email(
                    Source=source,
                    Destination={"ToAddresses": recipients},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {"Html": {"Data": body}},
                    },
                )
                logger.info(
                    f"Email sent via AWS SES (async) to {recipients} with subject '{subject}'. Message ID: {response['MessageId']}"
                )
            except Exception as e:
                logger.error(f"AWS SES async error: {e}")
                raise
