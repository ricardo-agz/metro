import abc


class ProviderNotConfiguredError(Exception):
    pass


class EmailProvider(abc.ABC):
    @abc.abstractmethod
    def send_email(self, source: str, recipients: list[str], subject: str, body: str):
        """
        Synchronously send an email.
        """
        pass

    @abc.abstractmethod
    async def send_email_async(
        self, source: str, recipients: list[str], subject: str, body: str
    ):
        """
        Asynchronously send an email.
        """
        pass


class SMSProvider(abc.ABC):
    @abc.abstractmethod
    def send_sms(self, source: str, recipients: list[str], message: str) -> None:
        """
        Synchronously send an SMS.
        """
        pass

    @abc.abstractmethod
    async def send_sms_async(
        self, source: str, recipients: list[str], message: str
    ) -> None:
        """
        Asynchronously send an SMS.
        """
        pass
