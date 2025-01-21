import types
from typing import Optional, TypeVar, Type, Union, List, Protocol, cast
from bson.decimal128 import Decimal128
from bson.binary import Binary
from mongoengine import (
    Document,
    DateTimeField,
    DoesNotExist,
    MultipleObjectsReturned,
    EmbeddedDocument,
    DynamicDocument,
    Q,
    StringField,
    IntField,
    FloatField,
    BooleanField,
    EmbeddedDocumentField,
    ListField,
    ReferenceField,
    DictField,
    DecimalField,
    ObjectIdField,
    EmbeddedDocumentListField,
    MapField,
    BinaryField,
    URLField,
    EmailField,
    GeoPointField,
    PointField,
    PolygonField,
    LineStringField,
    SequenceField,
    UUIDField,
    LazyReferenceField,
    ReferenceField,
    GenericReferenceField,
)
from mongoengine.base.metaclasses import TopLevelDocumentMetaclass
from datetime import datetime
from bson.objectid import ObjectId
from operator import or_, and_
from functools import reduce, wraps
from .mongo_protocol import MongoDocumentProtocol


T = TypeVar("T", bound=Union[Document, DynamicDocument])


FIELD_TYPE_MAP = {
    StringField: str,
    IntField: int,
    FloatField: float,
    BooleanField: bool,
    DateTimeField: datetime,
    DecimalField: Decimal128,
    BinaryField: Binary,
    URLField: str,
    EmailField: str,
    GeoPointField: dict,
    PointField: dict,
    PolygonField: dict,
    LineStringField: dict,
    SequenceField: int,
    UUIDField: str,
    LazyReferenceField: Document,
    ReferenceField: Document,
    GenericReferenceField: Document,
    ObjectIdField: ObjectId,
    EmbeddedDocumentField: EmbeddedDocument,
    ListField: list,
    EmbeddedDocumentListField: list,
    DictField: dict,
    MapField: dict,
}


def get_python_type(field_instance) -> type | None:
    for field_cls, py_type in FIELD_TYPE_MAP.items():
        if isinstance(field_instance, field_cls):
            return py_type
    # If we can’t match, either return `None` or raise an error
    return None


def type_checked_finder(finder_func):
    """Decorator for runtime type checking on dynamic finders."""
    from functools import wraps

    @wraps(finder_func)
    def wrapper(cls, *args, **kwargs):
        field_types = {}
        for field_name, field_instance in cls._fields.items():
            field_types[field_name] = get_python_type(field_instance)

        if kwargs:
            # Check types for keyword arguments
            for field_name, value in kwargs.items():
                expected_type = field_types.get(field_name)
                if expected_type and not isinstance(value, expected_type):
                    raise TypeError(
                        f"Argument '{field_name}' must be of type {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )
        else:
            # Handling for positional arguments
            method_name = finder_func.__name__
            field_names = []

            if method_name.startswith("find_all_by_"):
                conditions = method_name[12:]
            else:
                conditions = method_name[8:]

            for or_group in conditions.split("_or_"):
                for field in or_group.split("_and_"):
                    field_names.append(field)

            for field_name, arg in zip(field_names, args):
                expected_type = field_types.get(field_name)
                if expected_type and not isinstance(arg, expected_type):
                    raise TypeError(
                        f"Argument for '{field_name}' must be of type {expected_type.__name__}, "
                        f"got {type(arg).__name__}"
                    )

        return finder_func(cls, *args, **kwargs)

    return wrapper


class DynamicFinderMetaclass(TopLevelDocumentMetaclass):
    def __getattr__(cls, name: str):
        # Check for patterns like 'find_by_' or 'find_all_by_'
        if name.startswith("find_by_") or name.startswith("find_all_by_"):
            # Parse out the fields and validate them before creating the method
            conditions_str = name[12:] if name.startswith("find_all_by_") else name[8:]

            # Get all fields from the method name
            fields = []
            for group in conditions_str.split("_or_"):
                fields.extend(f for f in group.split("_and_") if f)

            # Check if any fields don't exist
            invalid_fields = [field for field in fields if not hasattr(cls, field)]
            if invalid_fields:
                available_fields = ", ".join(f"'{f}'" for f in cls._fields.keys())
                raise AttributeError(
                    f"Cannot create dynamic finder {cls.__name__}.{name}()\n"
                    f"Invalid field(s): {', '.join(invalid_fields)}\n"
                    f"Available fields are: {available_fields}"
                )

            @type_checked_finder
            def dynamic_finder(cls, *args, **kwargs):
                """
                Dynamic finder method that supports both positional and keyword arguments.
                Allows for complex queries with AND/OR conditions.

                Examples:
                    # Using positional args
                    User.find_by_name_and_age("John", 25)
                    User.find_by_email_or_username("john@example.com", "john")

                    # Using kwargs - can use fields from any OR group
                    User.find_by_email_or_name(email="john@example.com")  # Just email
                    User.find_by_email_or_name(name="john")              # Just name
                    User.find_by_email_or_name(email="john@example.com", name="john")  # Both
                """
                is_find_all = name.startswith("find_all_by_")
                conditions_str = name[12:] if is_find_all else name[8:]

                # Helper function to parse field names from method name
                def parse_field_names(condition_str: str) -> list[set[str]]:
                    # Split by '_or_' first to get groups of AND conditions
                    or_groups = condition_str.split("_or_")
                    result = []

                    for group in or_groups:
                        # Get the raw fields in this AND group
                        fields_in_group = [f for f in group.split("_and_") if f]

                        # Check for duplicate fields within this AND group
                        field_counts = {}
                        for field in fields_in_group:
                            field_counts[field] = field_counts.get(field, 0) + 1
                            if field_counts[field] > 1:
                                raise ValueError(
                                    f"Invalid dynamic finder {cls.__name__}.{name}()\n"
                                    f"Field '{field}' cannot be used multiple times with AND (e.g., find_by_name_and_name)\n"
                                    f"If you want to match multiple values, use OR instead (e.g., find_by_name_or_name)"
                                )

                        # Add the unique fields as a set
                        and_fields = set(fields_in_group)
                        if and_fields:  # Only add non-empty sets
                            result.append(and_fields)

                    return result

                field_groups = parse_field_names(conditions_str)
                queries = []

                # Handle keyword arguments
                if kwargs:
                    if args:
                        raise ValueError(
                            f"Invalid arguments for dynamic finder {cls.__name__}.{name}(): Cannot mix positional and keyword arguments"
                        )

                    # Build queries from kwargs based on the method name pattern
                    provided_fields = set(kwargs.keys())

                    valid_fields = set().union(
                        *field_groups
                    )  # Combine all field groups
                    invalid_fields = (
                        provided_fields - valid_fields
                    )  # Find any fields not in any group
                    if invalid_fields:
                        valid_fields_str = " OR ".join(
                            f"({' AND '.join(sorted(group))})" for group in field_groups
                        )
                        raise ValueError(
                            f"Invalid arguments for {cls.__name__}.{name}()\n"
                            f"Field(s) {', '.join(invalid_fields)} not allowed in this finder method\n"
                            f"Valid fields are: {valid_fields_str}"
                        )

                    # Group the provided fields by which OR group they belong to
                    for field_group in field_groups:
                        matching_fields = provided_fields.intersection(field_group)
                        if matching_fields:
                            # Build AND query for the matching fields in this group
                            and_queries = [
                                Q(**{field: kwargs[field]}) for field in matching_fields
                            ]
                            if and_queries:
                                queries.append(reduce(and_, and_queries))

                    if not queries:
                        valid_fields = " OR ".join(
                            f"({' AND '.join(sorted(group))})" for group in field_groups
                        )
                        valid_fields = valid_fields.replace(" OR ", "\n  - ")
                        raise ValueError(
                            f"Invalid field combination for {cls.__name__}.{name}()\n"
                            f"Valid combinations are:\n"
                            f"  - {valid_fields}"
                        )

                # Handle positional arguments
                else:
                    # Flatten field groups to get total number of expected arguments
                    all_fields = []
                    for group in field_groups:
                        all_fields.extend(group)

                    if len(args) != len(all_fields):
                        raise ValueError(
                            f"{cls.__name__}.{name}() requires {len(all_fields)} arguments\n"
                            f"Expected: {name}({', '.join(all_fields)})\n"
                            f"Got: {len(args)} arguments"
                        )

                    arg_index = 0
                    for field_group in field_groups:
                        if len(field_group) > 1:
                            and_queries = []
                            for field in sorted(
                                field_group
                            ):  # Sort for consistent ordering
                                and_queries.append(Q(**{field: args[arg_index]}))
                                arg_index += 1
                            queries.append(reduce(and_, and_queries))
                        else:
                            field = next(iter(field_group))
                            queries.append(Q(**{field: args[arg_index]}))
                            arg_index += 1

                # Execute query - with OR between groups
                final_query = reduce(or_, queries) if queries else Q()
                result = cls.objects(final_query)
                return result if is_find_all else result.first()

            # Return a bound method so that `cls` is actually the class
            return types.MethodType(dynamic_finder, cls)

        # Fallback to normal behavior
        raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")


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
                k: _handle_value(v) for k, v in d.items() if k not in exclude_fields
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
    def find(cls, include_deleted: bool = False, **kwargs) -> Optional[T]:
        """Find a single document, excluding soft-deleted by default"""
        if not include_deleted:
            kwargs["deleted_at"] = None

        return cls._execute_query(cls.objects(**kwargs).first)

    @classmethod
    def find_all(
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
    def find_all_deleted(
        cls, page: int = None, per_page: int = None, **kwargs
    ) -> List[T]:
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
    def find_by_id_and_update(cls, id: str | ObjectId, **updates) -> Optional[T]:
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

    @classmethod
    def get_fields(cls) -> list[tuple[str, type]]:
        """Get the fields of the document"""
        return [(k, type(v)) for k, v in cls._fields.items()]
