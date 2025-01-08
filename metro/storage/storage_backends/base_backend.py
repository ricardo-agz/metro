from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    @abstractmethod
    def save(self, name, content):
        pass

    @abstractmethod
    def url(self, name):
        pass

    @abstractmethod
    def delete(self, name):
        pass

    @abstractmethod
    def open(self) -> BinaryIO:
        pass
