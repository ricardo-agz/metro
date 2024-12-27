from typing import Optional, TypeVar, Type, Union, List, Protocol
from bson.decimal128 import Decimal128
from bson.binary import Binary
from mongoengine import (
    Document,
    DateTimeField,
    DoesNotExist,
    MultipleObjectsReturned,
    EmbeddedDocument,
    DynamicDocument,
)
from datetime import datetime
from bson.objectid import ObjectId
from .mongo_protocol import MongoDocumentProtocol


T = TypeVar("T", bound=Union[Document, DynamicDocument])


class BaseModelLogic:
    meta = {
        "abstract": True,
        "indexes": [
            "created_at",
            "updated_at",
            "deleted_at",
        ],
    }

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    deleted_at = DateTimeField(default=None)

    def clean(self) -> None:
        """
        Add custom validation logic here. Called before save.
        """
        pass

    def pre_save(self) -> None:
        """
        Hook for logic that should run before saving
        """
        pass

    def post_save(self) -> None:
        """
        Hook for logic that should run after successful save
        """
        pass

    def handle_save_error(self, error: Exception):
        """Override this method to handle specific save errors"""
        pass

    def to_dict(self, exclude_fields: set = None) -> dict:
        """
        Convert the document to a Python dictionary.

        Args:
            exclude_fields: Set of field names to exclude from the output

        Returns:
            dict: The document as a regular Python dictionary
        """
        exclude_fields = exclude_fields or {"_cls"}

        def _handle_value(val):
            if isinstance(val, ObjectId):
                return str(val)
            elif isinstance(val, datetime):
                return val.isoformat()
            elif isinstance(val, Decimal128):
                return float(val.to_decimal())
            elif isinstance(val, Binary):
                return str(val)
            elif isinstance(val, (dict, Document, EmbeddedDocument)):
                return _dictify(val)
            elif isinstance(val, list):
                return [_handle_value(v) for v in val]
            else:
                return val

        def _dictify(d):
            if isinstance(d, (Document, EmbeddedDocument)):
                d = d.to_mongo().to_dict()
            return {
                k: _handle_value(v)
                for k, v in d.items()
                if k not in exclude_fields
            }

        try:
            return _dictify(self.to_mongo().to_dict())
        except Exception as e:
            raise ValueError(f"Error converting document to dict: {str(e)}") from e

    @classmethod
    def _execute_query(cls, operation, *args, **kwargs) -> Optional[T]:
        try:
            return operation(*args, **kwargs)
        except (DoesNotExist, MultipleObjectsReturned):
            return None

    @classmethod
    def find_by_id(
        cls, id: str | ObjectId, include_deleted: bool = False
    ) -> Optional[T]:
        """Find document by ID, excluding soft-deleted by default"""
        cls._raise_if_invalid_id(id)

        kwargs = {"id": id}
        if not include_deleted:
            kwargs["deleted_at"] = None

        return cls._execute_query(cls.objects(**kwargs).first)

    @classmethod
    def find_one(cls, include_deleted: bool = False, **kwargs) -> Optional[T]:
        """Find a single document, excluding soft-deleted by default"""
        if not include_deleted:
            kwargs["deleted_at"] = None

        return cls._execute_query(cls.objects(**kwargs).first)

    @classmethod
    def find(
        cls,
        include_deleted: bool = False,
        page: int = None,
        per_page: int = None,
        **kwargs,
    ) -> List[T]:
        """Find documents, excluding soft-deleted by default"""
        if not include_deleted:
            kwargs["deleted_at"] = None

        if page is not None and per_page is not None:
            start = (page - 1) * per_page
            return cls._execute_query(cls.objects(**kwargs).skip(start).limit(per_page))
        else:
            return cls._execute_query(cls.objects(**kwargs))

    @classmethod
    def find_deleted(cls, page: int = None, per_page: int = None, **kwargs) -> List[T]:
        """
        Find only soft-deleted documents

        Args:
            page: Page number (starting from 1)
            per_page: Number of items per page
            **kwargs: Additional query filters

        Returns:
            List of soft-deleted documents
        """
        kwargs["deleted_at__ne"] = None
        return cls.find(include_deleted=True, page=page, per_page=per_page, **kwargs)

    @classmethod
    def find_by_id_and_update(
        cls, id: str | ObjectId, **updates
    ) -> Optional[T]:
        """
        Atomically updates a document by ID and returns the updated document.

        Can be used in two ways:

        * Simple field updates: find_by_id_and_update(id, name="John", age=25)

        * MongoDB operators: find_by_id_and_update(id, **{"$set": {...}, "$push": {...}})

        Args:
            id: The document ID
            **updates: Keyword arguments for field updates or MongoDB operators

        Returns:
            The updated document or None if not found/invalid ID
        """
        cls._raise_if_invalid_id(id)

        doc = cls.find_by_id(id)
        if not doc:
            return None

        for key, value in updates.items():
            setattr(doc, key, value)

        doc.save()
        return doc

    @classmethod
    def find_by_id_and_delete(cls, id: str | ObjectId) -> Optional[T]:
        """
        Find a document by ID and delete it.

        Args:
            id: The document ID

        Returns:
            The deleted document or None if not found/invalid ID
        """
        cls._raise_if_invalid_id(id)

        doc = cls.find_by_id(id)
        if doc:
            doc.delete()
            return doc

        return None

    def soft_delete(self) -> None:
        """Mark the document as deleted without removing it from the database"""
        self.deleted_at = datetime.utcnow()
        self.save()

    def restore(self) -> None:
        """Restore a soft-deleted document"""
        self.deleted_at = None
        self.save()

    @property
    def is_deleted(self) -> bool:
        """Check if document is soft-deleted"""
        return self.deleted_at is not None

    @classmethod
    def count(cls, include_deleted: bool = False, **kwargs) -> int:
        """Count documents, excluding soft-deleted by default"""
        if not include_deleted:
            kwargs["deleted_at"] = None

        return cls.objects(**kwargs).count()

    @staticmethod
    def _raise_if_invalid_id(id: str | ObjectId):
        if not isinstance(id, ObjectId) and not ObjectId.is_valid(id):
            raise ValueError("Invalid document ID")
