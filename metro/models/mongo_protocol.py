from typing import TypeVar, Union, Protocol
from mongoengine import Document, DynamicDocument


T = TypeVar("T", bound=Union[Document, DynamicDocument])


class MongoDocumentProtocol(Protocol):
    id: str
    _fields: dict
    _data: dict

    def save(self, *args, **kwargs) -> T: ...
    def validate(self, *args, **kwargs) -> None: ...
    def delete(self, *args, **kwargs) -> None: ...
    def to_mongo(self, *args, **kwargs) -> dict: ...
    @classmethod
    def objects(cls, *args, **kwargs) -> T: ...
