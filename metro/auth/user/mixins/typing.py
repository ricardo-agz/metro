from typing import ClassVar, Optional, Protocol, TypeVar


class UserProtocol(Protocol):
    """Protocol defining the required interface for the base user class"""

    objects: ClassVar[any]  # For MongoEngine's objects manager
    __mro__: ClassVar[tuple]  # For super() calls

    @classmethod
    def authenticate(
        cls, identifier: str, password: str
    ) -> Optional["UserProtocol"]: ...

    def save(self) -> None: ...


T = TypeVar("T", bound=UserProtocol)
