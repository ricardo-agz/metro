import os
import uuid
import logging
from collections import defaultdict
from typing import Optional, BinaryIO

from bson import ObjectId
from mongoengine.fields import BaseField
from pyrails.storage import StorageBackend, storage_backend


logger = logging.getLogger(__name__)


class FileInfo:
    """
    Represents file metadata and state.
    (No versioning support anymore, so we omit 'versions'.)
    """

    def __init__(
        self,
        filename: str,
        content_type: str,
        size: int,
    ):
        self.filename = filename
        self.content_type = content_type
        self.size = size

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileInfo":
        return cls(
            filename=data["filename"],
            content_type=data["content_type"],
            size=data["size"],
        )


class StorageOperation:
    """Represents a pending storage operation."""

    def __init__(
        self,
        field_name: str,
        file_obj: BinaryIO,
        original_filename: str,
        content_type: str,
        size: int,
    ):
        self.field_name = field_name
        self.file_obj = file_obj
        self.original_filename = original_filename
        self.content_type = content_type
        self.size = size
        self.storage: Optional[StorageBackend] = None
        self._stored_filename: Optional[str] = None

    @property
    def stored_filename(self) -> Optional[str]:
        return self._stored_filename

    @stored_filename.setter
    def stored_filename(self, value: str):
        self._stored_filename = value


class FileHandler:
    """Manages file operations and state for a document instance."""

    def __init__(self):
        # Key: field_name -> list of StorageOperation
        self.pending_uploads: dict[str, list[StorageOperation]] = defaultdict(list)
        self.pending_deletions: set[tuple[str, str, StorageBackend]] = set()
        # placeholder_id -> (field_name, StorageOperation)
        self.placeholders: dict[str, tuple[str, StorageOperation]] = {}
        self._committed = False

    def stage_upload(self, field_name: str, operation: StorageOperation, storage: StorageBackend, placeholder_id: str):
        """Stage a file for upload and track it by placeholder_id."""
        operation.storage = storage
        self.pending_uploads[field_name].append(operation)
        # Track the placeholder so we can cancel if overwritten
        self.placeholders[placeholder_id] = (field_name, operation)

    def cancel_upload(self, placeholder_id: str):
        """
        Remove a previously staged upload if it hasn't been committed yet.
        """
        if placeholder_id not in self.placeholders or self._committed:
            return

        field_name, op = self.placeholders.pop(placeholder_id)
        if field_name in self.pending_uploads:
            if op in self.pending_uploads[field_name]:
                self.pending_uploads[field_name].remove(op)

    def stage_deletion(self, field_name: str, filename: str, storage: StorageBackend):
        """Stage a file for deletion."""
        self.pending_deletions.add((field_name, filename, storage))

    def process_files(self, document_id: str) -> dict[str, list[FileInfo]]:
        """
        Upload all staged files. Return { field_name: [FileInfo, ...] }.
        """
        if self._committed:
            raise RuntimeError("FileHandler has already been committed")

        results: dict[str, list[FileInfo]] = {}
        uploaded_files: list[tuple[StorageBackend, str]] = []

        try:
            # Upload new files
            for field_name, operations in self.pending_uploads.items():
                new_file_infos = []
                for op in operations:
                    new_filename = f"{document_id}_{uuid.uuid4().hex}_{op.original_filename}"
                    op.storage.save(new_filename, op.file_obj)
                    op.stored_filename = new_filename
                    uploaded_files.append((op.storage, new_filename))

                    file_info = FileInfo(
                        filename=new_filename,
                        content_type=op.content_type,
                        size=op.size,
                    )
                    new_file_infos.append(file_info)

                if new_file_infos:
                    results[field_name] = new_file_infos

            self._committed = True
            return results

        except Exception as exc:
            # Roll back any successfully uploaded files
            for storage, filename in uploaded_files:
                try:
                    storage.delete(filename)
                except Exception:
                    pass
            raise exc

    def cleanup(self):
        """Delete any files staged for deletion."""
        if not self._committed:
            return

        for _, filename, storage in self.pending_deletions:
            try:
                storage.delete(filename)
            except Exception as ex:
                logger.error(f"FileHandler cleanup deletion error for '{filename}': {ex}")


class FileProxy:
    """
    Provides access to a stored file.
    """

    def __init__(self, file_info: FileInfo, storage: StorageBackend):
        self.file_info = file_info
        self.storage = storage

    @property
    def filename(self) -> str:
        return self.file_info.filename

    @property
    def content_type(self) -> str:
        return self.file_info.content_type

    @property
    def size(self) -> int:
        return self.file_info.size

    @property
    def url(self) -> str:
        return self.storage.url(self.file_info.filename)

    def open(self) -> BinaryIO:
        return self.storage.open(self.file_info.filename)

    def __repr__(self):
        return f"<FileProxy: {self.file_info.filename}>"

    def __str__(self):
        return self.storage.url(self.file_info.filename)


class FileListProxy:
    """
    A list-like proxy object for multi-file handling.
    Always replaces or removes existing files; no versioning logic.
    """

    def __init__(self, instance, field_name, field, initial_value=None):
        self.instance = instance
        self.field_name = field_name
        self.field = field
        self._files = initial_value or []

        if not hasattr(self.instance, "_file_handler"):
            self.instance._file_handler = FileHandler()

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            sliced = self._files[idx]
            return [
                FileProxy(FileInfo.from_dict(item), self.field.storage)
                for item in sliced
                if item and "filename" in item
            ]
        else:
            item = self._files[idx]
            if item and "filename" in item:
                return FileProxy(FileInfo.from_dict(item), self.field.storage)
            return None

    def __setitem__(self, idx, value):
        if isinstance(idx, slice):
            if not isinstance(value, list):
                value = [value]
            self._replace_slice(idx, value)
        else:
            self._replace_item(idx, value)
        self._update_document_data()

    def __delitem__(self, idx):
        if isinstance(idx, slice):
            items_to_remove = self._files[idx]
            for file_dict in items_to_remove:
                self._stage_delete(file_dict)
            del self._files[idx]
        else:
            file_dict = self._files[idx]
            self._stage_delete(file_dict)
            del self._files[idx]
        self._update_document_data()

    def __len__(self):
        return len(self._files)

    def insert(self, index: int, value):
        """
        Insert a new file (UploadFile), dict, or FileProxy at a specific index.
        """
        if hasattr(value, "file"):
            placeholder_dict = self._stage_upload(value)
            self._files.insert(index, placeholder_dict)
        elif isinstance(value, dict):
            self._files.insert(index, value)
        else:
            if hasattr(value, "file_info"):
                self._files.insert(index, value.file_info.to_dict())
            else:
                raise ValueError("Invalid value type for file insertion")
        self._update_document_data()

    def append(self, value):
        self.insert(len(self._files), value)

    def extend(self, iterable):
        for item in iterable:
            self.append(item)

    def pop(self, index: int = -1):
        if not self._files:
            raise IndexError("pop from empty FileList")
        file_dict = self._files.pop(index)
        self._stage_delete(file_dict)
        self._update_document_data()
        return file_dict

    def clear(self):
        for file_dict in self._files:
            self._stage_delete(file_dict)
        self._files = []
        self._update_document_data()

    def remove_by_filename(self, filename: str):
        """
        Remove a single file by filename
        """
        for i, file_dict in enumerate(self._files):
            if (file_dict and isinstance(file_dict, dict) and
                    "filename" in file_dict and
                    file_dict["filename"] == filename):
                self._stage_delete(file_dict)
                del self._files[i]
                self._update_document_data()
                break

    def _stage_upload(self, upload_obj):
        """
        Validate and stage a file, returning a unique placeholder dict.
        """
        size = self.field.validate_file(upload_obj.file, upload_obj.filename)

        operation = StorageOperation(
            field_name=self.field_name,
            file_obj=upload_obj.file,
            original_filename=upload_obj.filename,
            content_type=getattr(upload_obj, "content_type", "application/octet-stream"),
            size=size,
        )

        placeholder_id = uuid.uuid4().hex
        self.instance._file_handler.stage_upload(
            field_name=self.field_name,
            operation=operation,
            storage=self.field.storage,
            placeholder_id=placeholder_id,
        )
        # Return a placeholder indicating it's not yet committed
        return {"__placeholder_id": placeholder_id}

    def _maybe_cancel_pending_upload(self, file_dict):
        """
        If file_dict is a placeholder, remove its upload operation from the queue.
        """
        if file_dict and isinstance(file_dict, dict) and "__placeholder_id" in file_dict:
            placeholder_id = file_dict["__placeholder_id"]
            self.instance._file_handler.cancel_upload(placeholder_id)

    def _stage_delete(self, file_dict):
        """
        Stage an existing file for deletion if it has a 'filename',
        or cancel if it's still just a placeholder.
        """
        if not file_dict or not isinstance(file_dict, dict):
            return

        if "__placeholder_id" in file_dict:
            self._maybe_cancel_pending_upload(file_dict)
        elif "filename" in file_dict:
            filename = file_dict["filename"]
            self.instance._file_handler.stage_deletion(
                self.field_name, filename, self.field.storage
            )

    def _replace_item(self, idx, value):
        if 0 <= idx < len(self._files):
            old_item = self._files[idx]
            self._stage_delete(old_item)

        if hasattr(value, "file"):
            self._files[idx] = self._stage_upload(value)
        elif hasattr(value, "file_info"):
            self._files[idx] = value.file_info.to_dict()
        elif isinstance(value, dict):
            self._files[idx] = value
        else:
            raise ValueError("Unsupported file type for assignment")

    def _replace_slice(self, slice_idx, new_values):
        start, stop, step = slice_idx.indices(len(self._files))
        indices_to_replace = range(start, stop, step)

        # Get the set of existing filenames that will be kept
        new_filenames = set()
        for value in new_values:
            if hasattr(value, "file_info"):
                new_filenames.add(value.file_info.filename)
            elif isinstance(value, dict) and "filename" in value:
                new_filenames.add(value["filename"])

        # Only stage deletions for files that won't be in the new set
        for i in indices_to_replace:
            if i < len(self._files):
                old_item = self._files[i]
                if (old_item and isinstance(old_item, dict) and
                        "filename" in old_item and
                        old_item["filename"] not in new_filenames):
                    self._stage_delete(old_item)

        # Now replace the slice with new values
        new_files = []
        for value in new_values:
            if hasattr(value, "file"):
                new_files.append(self._stage_upload(value))
            elif hasattr(value, "file_info"):
                new_files.append(value.file_info.to_dict())
            elif isinstance(value, dict):
                new_files.append(value)
            else:
                raise ValueError("Unsupported file type for slice assignment")

        self._files[slice_idx] = new_files

    def _update_document_data(self):
        """
        Synchronize the underlying document _data with our internal list.
        """
        self.instance._data[self.field_name] = self._files
        # Mark the field as modified to ensure mongoengine saves it
        self.instance._mark_as_changed(self.field_name)


class FileListField(BaseField):
    """
    A specialized field that stores multiple files in a list-like structure.
    Always 'replace' semantics for updates.
    """

    def __init__(
        self,
        storage: StorageBackend = None,
        allowed_extensions: list[str] = None,
        max_size: int = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.storage = storage or storage_backend
        self.allowed_extensions = {ext.lower() for ext in (allowed_extensions or [])}
        self.max_size = max_size

    def __get__(self, instance, owner):
        if instance is None:
            return self

        value = instance._data.get(self.name)
        if value is None:
            value = []
            instance._data[self.name] = value

        return FileListProxy(
            instance=instance,
            field_name=self.name,
            field=self,
            initial_value=value
        )

    def __set__(self, instance, value):
        """
        Replacing the entire field with a new list triggers:
         1) clear() the proxy
         2) extend(...) with new items
        """
        proxy = self.__get__(instance, type(instance))
        proxy.clear()

        if value:
            if not isinstance(value, list):
                raise ValueError("FileListField must be assigned a list")
            proxy.extend(value)

    def to_mongo(self, value):
        """
        Convert the internal proxy list (or plain list) to what gets stored in Mongo.
        """
        if not value:
            return []
        if isinstance(value, FileListProxy):
            value = value._files

        results = []
        for item in value:
            if not item:
                results.append(None)
                continue

            # If it's a placeholder, store None until committed
            if "__placeholder_id" in item:
                results.append(None)
                continue

            if isinstance(item, dict) and "filename" in item:
                file_info = FileInfo.from_dict(item)
                item_with_url = item.copy()
                item_with_url["url"] = self.storage.url(file_info.filename)
                results.append(item_with_url)
            else:
                # Possibly a FileProxy or something that has .file_info
                if hasattr(item, "file_info"):
                    file_info = item.file_info
                    item_dict = file_info.to_dict()
                    item_dict["url"] = self.storage.url(file_info.filename)
                    results.append(item_dict)
                else:
                    results.append(item)
        return results

    def to_python(self, value):
        """
        Convert from Mongo to Python. Usually we store dicts with "filename", etc.
        """
        if not value:
            return []

        # Handle FastAPI UploadFile objects
        if hasattr(value, 'file'):
            return [value]  # Wrap single UploadFile in a list

        # Handle list of UploadFiles from form-data
        if isinstance(value, (list, tuple)):
            python_list = []
            for item in value:
                if hasattr(item, 'file'):  # Handle UploadFile
                    python_list.append(item)
                elif isinstance(item, dict):  # Handle file info dict
                    python_list.append(item)
                elif item is None:
                    python_list.append(None)
                else:
                    raise ValueError(f"Unexpected item type in file list: {type(item)}")
            return python_list

        # If it's a single item that's not a list/tuple/UploadFile, wrap it
        return [value]

    def validate_file(self, file_obj: BinaryIO, filename: str) -> int:
        """
        Validate the incoming file. Return size. Raise ValueError if invalid.
        """
        if self.allowed_extensions:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in self.allowed_extensions:
                raise ValueError(f"File extension '{ext}' not allowed")

        pos = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(pos)

        if self.max_size and size > self.max_size:
            raise ValueError(f"File size exceeds maximum of {self.max_size} bytes")

        return size


class FileField(BaseField):
    """
    Field for handling single-file attachments.
    Always 'replace': setting a new file deletes the old one.
    """

    def __init__(
        self,
        storage: StorageBackend = None,
        allowed_extensions: list[str] = None,
        max_size: int = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.storage = storage or storage_backend
        self.allowed_extensions = {ext.lower() for ext in (allowed_extensions or [])}
        self.max_size = max_size

    def validate_file(self, file_obj: BinaryIO, filename: str) -> int:
        """
        Validate file and return size. Raise ValueError if invalid.
        """
        if self.allowed_extensions:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in self.allowed_extensions:
                raise ValueError(f"File extension '{ext}' not allowed")

        pos = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(pos)

        if self.max_size and size > self.max_size:
            raise ValueError(f"File size exceeds maximum of {self.max_size} bytes")

        return size

    def __set__(self, instance, value):
        if not hasattr(instance, "_file_handler"):
            instance._file_handler = FileHandler()

        # If setting to None => delete old file
        if value is None:
            current = instance._data.get(self.name)
            if current and isinstance(current, dict) and "filename" in current:
                file_info = FileInfo.from_dict(current)
                instance._file_handler.stage_deletion(
                    self.name, file_info.filename, self.storage
                )
            instance._data[self.name] = None
            return

        # If it's a dict from the DB or from the code
        if isinstance(value, dict):
            instance._data[self.name] = value
            return

        # If it's an UploadFile
        if hasattr(value, "file"):
            size = self.validate_file(value.file, value.filename)
            current = instance._data.get(self.name)
            if current and isinstance(current, dict) and "filename" in current:
                old_info = FileInfo.from_dict(current)
                instance._file_handler.stage_deletion(self.name, old_info.filename, self.storage)

            operation = StorageOperation(
                field_name=self.name,
                file_obj=value.file,
                original_filename=value.filename,
                content_type=getattr(value, "content_type", "application/octet-stream"),
                size=size,
            )
            placeholder_id = uuid.uuid4().hex
            instance._file_handler.stage_upload(
                self.name, operation, self.storage, placeholder_id
            )
            instance._data[self.name] = {"__placeholder_id": placeholder_id}

        else:
            raise ValueError("Unsupported value for file assignment")

    def __get__(self, instance, owner):
        if instance is None:
            return self

        value = instance._data.get(self.name)
        if not value or "__placeholder_id" in value:
            return None
        return FileProxy(FileInfo.from_dict(value), self.storage)

    def to_mongo(self, value):
        """
        Convert the file (proxy or dict) into what’s stored in Mongo.
        """
        if not value:
            return None
        if "__placeholder_id" in value:
            return None
        if isinstance(value, dict) and "filename" in value:
            file_info = FileInfo.from_dict(value)
            result = value.copy()
            result["url"] = self.storage.url(file_info.filename)
            return result

        if hasattr(value, "file_info"):
            file_info = value.file_info
            result = file_info.to_dict()
            result["url"] = self.storage.url(file_info.filename)
            return result

        return value

    def to_python(self, value):
        """
        Convert from Mongo to a Python dict with the final file info.
        """
        if not value:
            return None

        # Handle UploadFile objects
        if hasattr(value, 'file'):
            return value

        # Handle placeholder dicts
        if isinstance(value, dict) and "__placeholder_id" in value:
            return None

        file_info = FileInfo.from_dict(value)
        proxy = FileProxy(file_info, self.storage)
        return {
            "filename": proxy.filename,
            "content_type": proxy.content_type,
            "size": proxy.size,
            "url": proxy.url,
        }


class FileHandlingMixin:
    """
    Mixin for document classes that handle file uploads.
    Always replaces files; no version logic.
    """

    meta = {"abstract": True}

    def save(self, *args, **kwargs):
        """
        Override save() to process all staged uploads/deletions before
        performing the actual DB save.
        """
        created_files: list[tuple[StorageBackend, str]] = []

        try:
            if not self.id:
                self.id = ObjectId()  # Ensure we have an ID for naming

            # Process any pending uploads
            if hasattr(self, "_file_handler"):
                file_results = self._file_handler.process_files(str(self.id))

                # Instead of directly updating _data, we now fix the proxy so that
                # the correct file info is actually saved to Mongo.
                for field_name, list_of_file_infos in file_results.items():
                    field_obj = self._fields[field_name]

                    if isinstance(field_obj, FileListField):
                        # 1) Fetch the proxy
                        proxy = getattr(self, field_name)

                        # 2) The existing real data in _data (minus placeholders)
                        old_data = self._data.get(field_name) or []
                        old_data = [d for d in old_data if d and "filename" in d]

                        # 3) Clear the proxy, re-append old data, then new
                        proxy.clear()
                        for item in old_data:
                            proxy.append(item)
                        for fi in list_of_file_infos:
                            proxy.append(fi.to_dict())

                        # Mark for potential rollback
                        for fi in list_of_file_infos:
                            created_files.append((field_obj.storage, fi.filename))

                    elif isinstance(field_obj, FileField):
                        # Single-file field: keep only the last staged file
                        fi = list_of_file_infos[-1]

                        # We can directly set the field with a dict => triggers the
                        # normal setter logic (which in this case is just a direct assign).
                        setattr(self, field_name, fi.to_dict())

                        created_files.append((field_obj.storage, fi.filename))

            # Now call super() to actually save the doc in Mongo
            result = super().save(*args, **kwargs)

            # Cleanup any staged deletions
            if hasattr(self, "_file_handler"):
                self._file_handler.cleanup()
                delattr(self, "_file_handler")

            return result

        except Exception as exc:
            # If something failed, delete newly created files
            for storage, filename in created_files:
                try:
                    storage.delete(filename)
                except Exception as cleanup_err:
                    logger.error(f"Failed to delete '{filename}': {cleanup_err}")

            if hasattr(self, "_file_handler"):
                delattr(self, "_file_handler")

            raise exc

    def delete(self, *args, **kwargs):
        """
        Also remove any actual files from storage when the doc is deleted.
        """
        files_to_delete = []

        for field_name, field in self._fields.items():
            if isinstance(field, FileField):
                file_data = self._data.get(field_name)
                if file_data and "filename" in file_data:
                    file_info = FileInfo.from_dict(file_data)
                    files_to_delete.append((field.storage, file_info.filename))

            elif isinstance(field, FileListField):
                file_list = self._data.get(field_name) or []
                for file_dict in file_list:
                    if file_dict and "filename" in file_dict:
                        files_to_delete.append((field.storage, file_dict["filename"]))

        result = super().delete(*args, **kwargs)

        for storage, filename in files_to_delete:
            try:
                storage.delete(filename)
            except Exception as ex:
                logger.error(f"Error deleting file '{filename}': {ex}")

        return result
