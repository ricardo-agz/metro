from metro.models.fields import *


mongoengine_type_mapping = {
    "str": "StringField()",
    "text": "StringField()",
    "email": "EmailField()",
    "int": "IntField()",
    "bool": "BooleanField()",
    "float": "FloatField()",
    "datetime": "DateTimeField()",
    "date": "DateTimeField()",
    "time": "DateTimeField()",
    "uuid": "UUIDField()",
    "json": "DictField()",
    "decimal": "DecimalField()",
    "objectid": "ObjectIdField()",
    "list": "ListField()",
    "list[str]": "ListField(StringField())",
    "list[int]": "ListField(IntField())",
    "list[bool]": "ListField(BooleanField())",
    "list[float]": "ListField(FloatField())",
    "list[datetime]": "ListField(DateTimeField())",
    "list[file]": "FileListField()",
    "file": "FileField()",
}

pydantic_type_mapping = {
    "str": "str",
    "text": "str",
    "email": "str",
    "int": "int",
    "bool": "bool",
    "float": "float",
    "datetime": "datetime",
    "date": "datetime",
    "time": "datetime",
    "uuid": "str",
    "json": "dict",
    "decimal": "float",
    "list": "list",
    "objectid": "str",
    "list[str]": "list[str]",
    "list[int]": "list[int]",
    "list[bool]": "list[bool]",
    "list[float]": "list[float]",
    "list[datetime]": "list[datetime]",
}

MONGO_DB_FIELD_TO_FIELD_TYPE = {
    StringField: "str",
    IntField: "int",
    FloatField: "float",
    BooleanField: "bool",
    DateTimeField: "datetime",
    DecimalField: "decimal",
    EmailField: "str",
    URLField: "str",
    UUIDField: "str",
    DictField: "dict",
    ReferenceField: lambda field: f"ref:{field.document_type.__name__}",
    ListField: lambda field: f"list:{get_inner_field_type(field.field)}",
    EmbeddedDocumentField: lambda field: f"embedded:{field.document_type.__name__}",
    # Special fields
    HashedField: "hashed_str",
    FileField: "file",
    FileListField: "list:file",
}


def get_inner_field_type(field: any) -> str:
    """Get the type string for a field, handling nested structures."""
    field_class = field.__class__

    if field_class in MONGO_DB_FIELD_TO_FIELD_TYPE:
        type_def = MONGO_DB_FIELD_TO_FIELD_TYPE[field_class]
        if callable(type_def):
            return type_def(field)
        return type_def

    return "str"  # fallback
