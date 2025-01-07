import os
from typing import BinaryIO

from metro.storage.storage_backends.base_backend import StorageBackend


class FileSystemStorage(StorageBackend):
    def __init__(self, location="uploads", base_url="/uploads/"):
        self.location = location
        self.base_url = base_url

    def save(self, name, content):
        os.makedirs(self.location, exist_ok=True)

        file_path = os.path.join(self.location, name)
        with open(file_path, "wb") as f:
            f.write(content.read())
        return name

    def url(self, name):
        return f"{self.base_url}{name}"

    def delete(self, name):
        file_path = os.path.join(self.location, name)
        if os.path.exists(file_path):
            os.remove(file_path)

    def open(self) -> BinaryIO:
        pass
