import os
from pathlib import Path
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from metro.communications.providers import (
    EmailProvider,
    MailgunProvider,
)
from metro.communications.providers.aws import AWSESProvider
from metro.communications.providers.base import ProviderNotConfiguredError
from metro.logger import logger
from metro.config import config


class EmailSender:
    DEFAULT_TEMPLATES_SUBDIR = "templates/email"

    def __init__(
        self,
        provider: Optional[EmailProvider] = None,
        templates_dir: Optional[str] = None,
    ):
        """
        Initialize the EmailSender.

        :param provider: An instance of EmailProvider. If None, defaults to Mailgun or AWS SES based on environment variables.
        :param templates_dir: Optional path to the templates directory. If None, searches for 'templates/emails' in the application root.
        :raises ValueError: If no provider is configured or templates directory is not found.
        """
        self.provider = self._initialize_provider(provider)
        self.templates_dir = self._determine_templates_dir(templates_dir)
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))

    @staticmethod
    def _initialize_provider(provider: Optional[EmailProvider]) -> EmailProvider:
        if provider:
            logger.debug("Using provided EmailProvider.")
            return provider

        mailgun_configured = (
            hasattr(config, "MAILGUN_DOMAIN")
            and config.MAILGUN_DOMAIN
            and hasattr(config, "MAILGUN_API_KEY")
            and config.MAILGUN_API_KEY
        )
        aws_configured = (
            hasattr(config, "AWS_ACCESS_KEY_ID")
            and config.AWS_ACCESS_KEY_ID
            and hasattr(config, "AWS_SECRET_ACCESS_KEY")
            and config.AWS_SECRET_ACCESS_KEY
        )

        if mailgun_configured:
            mailgun_domain = config.MAILGUN_DOMAIN
            mailgun_api_key = config.MAILGUN_API_KEY
            logger.info("Configuring MailgunProvider based on config.")
            return MailgunProvider(domain=mailgun_domain, api_key=mailgun_api_key)
        elif aws_configured:
            aws_access_key = config.AWS_ACCESS_KEY_ID
            aws_secret_key = config.AWS_SECRET_ACCESS_KEY
            logger.info("Configuring AWSESProvider based on config.")
            return AWSESProvider()
        else:
            logger.error(
                "No email provider configured. Please set Mailgun or AWS SES environment variables."
            )
            raise ProviderNotConfiguredError(
                "No email provider configured. Please set Mailgun or AWS SES environment variables."
            )

    def _determine_templates_dir(self, templates_dir: Optional[str]) -> str:
        """
        Determine the templates directory using Path.cwd().
        """
        if templates_dir:
            resolved_dir = Path(templates_dir).resolve()
            if not resolved_dir.is_dir():
                logger.error(
                    f"The specified templates directory does not exist: {resolved_dir}"
                )
                raise FileNotFoundError(
                    f"The specified templates directory does not exist: {resolved_dir}"
                )
            logger.info(f"Using custom templates directory: {resolved_dir}")
            return str(resolved_dir)

        # Use the current working directory as the application root
        app_root = Path.cwd()
        default_templates_dir = app_root / self.DEFAULT_TEMPLATES_SUBDIR

        if default_templates_dir.is_dir():
            logger.info(f"Using default templates directory: {default_templates_dir}")
            return str(default_templates_dir)
        else:
            logger.error(
                f"Default templates directory '{default_templates_dir}' not found. "
                "Please ensure 'templates/email' exists in your application or specify a 'templates_dir'."
            )
            raise FileNotFoundError(
                f"Default templates directory '{default_templates_dir}' not found. "
                "Please ensure 'templates/email' exists in your application or specify a 'templates_dir'."
            )

    def send_email(
        self,
        source: str,
        recipients: list[str],
        subject: str,
        template_name: Optional[str] = None,
        context: Optional[dict[str, any]] = None,
        body: Optional[str] = None,
    ):
        """
        Synchronously send an email.

        :param source: Sender's email address.
        :param recipients: List of recipient email addresses.
        :param subject: Subject of the email.
        :param template_name: Name of the Jinja2 template to render.
        :param context: Context dictionary for template rendering.
        :param body: Raw HTML body of the email. Overrides template if provided.
        :raises ValueError: If neither template_name nor body is provided.
        """
        if not template_name and not body:
            raise ValueError("Either a template_name or a body must be provided")

        if template_name:
            try:
                body = self._render_template(template_name, context or {})
            except TemplateNotFound:
                logger.error(
                    f"Template '{template_name}' not found in '{self.templates_dir}'."
                )
                raise
            except Exception as e:
                logger.error(f"Error rendering template '{template_name}': {e}")
                raise

        self.provider.send_email(source, recipients, subject, body)

    async def send_email_async(
        self,
        source: str,
        recipients: List[str],
        subject: str,
        template_name: Optional[str] = None,
        context: Optional[dict[str, any]] = None,
        body: Optional[str] = None,
    ):
        """
        Asynchronously send an email.

        :param source: Sender's email address.
        :param recipients: List of recipient email addresses.
        :param subject: Subject of the email.
        :param template_name: Name of the Jinja2 template to render.
        :param context: Context dictionary for template rendering.
        :param body: Raw HTML body of the email. Overrides template if provided.
        :raises ValueError: If neither template_name nor body is provided.
        """
        if not template_name and not body:
            raise ValueError("Either a template_name or a body must be provided")

        if template_name:
            try:
                body = self._render_template(template_name, context or {})
            except TemplateNotFound:
                logger.error(
                    f"Template '{template_name}' not found in '{self.templates_dir}'."
                )
                raise
            except Exception as e:
                logger.error(f"Error rendering template '{template_name}': {e}")
                raise

        await self.provider.send_email_async(source, recipients, subject, body)

    def _render_template(self, template_name: str, context: dict[str, any]) -> str:
        """
        Render a Jinja2 template with the given context.

        :param template_name: Name of the template file.
        :param context: Context dictionary for rendering.
        :return: Rendered HTML as a string.
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(context)
        except TemplateNotFound:
            logger.error(
                f"Template '{template_name}' not found in '{self.templates_dir}'."
            )
            raise
        except Exception as e:
            logger.error(f"Error rendering template '{template_name}': {e}")
            raise


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

    from dotenv import load_dotenv

    load_dotenv()

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
