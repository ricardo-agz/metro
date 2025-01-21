import importlib.util
import inspect
import os
import re

import click
from pydantic import BaseModel

from metro.models import BaseModel as DBBaseModel
from metro.config import config
from metro.utils import (
    mongoengine_type_mapping,
    pydantic_type_mapping,
    to_snake_case,
    get_inner_field_type,
)

CORE_MODEL_MAPPINGS = {
    "UserBase": "metro.auth.user.user_base.UserBase",
    "APIKeyBase": "metro.auth.api_key.api_key_base.APIKeyBase",
}


def process_inheritance(model_inherits: str) -> tuple[str, list[str]]:
    """
    Process model inheritance specification and generate import statements.

    Args:
        model_inherits: Comma-separated string of base classes

    Returns:
        Tuple of (base_classes, additional_imports)
    """
    additional_imports = []
    base_classes = "BaseModel"

    if model_inherits:
        inheritance_list = [i.strip() for i in model_inherits.split(",")]
        base_classes = ", ".join(inheritance_list)

        built_in_auth_imports = [
            b for b in inheritance_list if b in ["UserBase", "APIKeyBase"]
        ]
        non_built_in_imports = [
            b for b in inheritance_list if b not in ["UserBase", "APIKeyBase"]
        ]

        if built_in_auth_imports:
            auth_imports = f"from metro.auth import {', '.join(built_in_auth_imports)}"
            additional_imports.append(auth_imports)

        if non_built_in_imports:
            for i in non_built_in_imports:
                import_path = f"from app.models.{to_snake_case(i)} import {i}"
                additional_imports.append(import_path)

    return base_classes, additional_imports


def process_controller_inheritance(
    controller_inherits: str | None,
) -> tuple[str, list[str]]:
    """Process controller inheritance and generate imports."""
    base_controllers = "Controller"  # default
    additional_imports = []

    if controller_inherits:
        inherits_list = [c.strip() for c in controller_inherits.split(",")]
        non_built_in_imports = [b for b in inherits_list if b not in ["Controller"]]
        base_controllers = ", ".join(inherits_list)

        for i in non_built_in_imports:
            import_path = f"from app.controllers.{to_snake_case(i)} import {i}"
            additional_imports.append(import_path)

    return base_controllers, additional_imports


class ProcessFieldsOutput(BaseModel):
    fields_code: str
    pydantic_code: str
    additional_imports: list[str]
    meta_indexes: list[dict] = []  # For compound and regular indexes


def process_fields(fields: list[str], indexes: tuple[str, ...]) -> ProcessFieldsOutput:
    """
    Process field definitions and generate model fields and Pydantic schemas.

    Args:
        fields: Tuple of field definitions in format "name:type"

    Returns:
        Tuple of (fields_code, pydantic_code)
    """
    fields_code = ""
    pydantic_code = ""
    has_choices = False
    additional_imports = []

    meta_indexes = []
    for index_str in indexes:
        try:
            index_spec = process_index_option(index_str)
            meta_indexes.append(index_spec)
        except Exception as e:
            raise click.BadParameter(f"Error processing index {index_str}: {str(e)}")

    for field in fields:
        if not field or not field.strip():
            continue

        if ":" not in field:
            raise click.BadParameter(
                f"Invalid field format: {field}. Expected format: name:type"
            )

        try:
            name, type_ = field.split(":", 1)
            name = name.strip()
            type_ = type_.strip()

            if ":choices[" in type_:
                has_choices = True

            if not name or not type_:
                raise click.BadParameter(
                    f"Invalid field format: {field}. Name and type cannot be empty"
                )

            unique = name.endswith("^")
            optional = name.endswith("?")
            indexed = False
            field_code, pydantic = process_field(name, type_, optional, unique, indexed)
            fields_code += field_code
            pydantic_code += pydantic

        except ValueError as e:
            raise click.BadParameter(f"Error processing field {field}: {str(e)}")

    has_datetime = any("datetime" in f for f in fields)
    if has_datetime:
        additional_imports.append("from datetime import datetime")
    if has_choices:
        additional_imports.append("from typing import Literal")

    return ProcessFieldsOutput(
        fields_code=fields_code,
        pydantic_code=pydantic_code,
        additional_imports=additional_imports,
        meta_indexes=meta_indexes,
    )


def parse_hook(hook_str: str) -> tuple[str, str]:
    """
    Given something like "check_admin:Ensure user is admin",
    returns ("check_admin", "Ensure user is admin").
    If no ':' is found, default the desc to a generic string.
    """
    if ":" in hook_str:
        name, desc = hook_str.split(":", 1)
        return name.strip(), desc.strip()
    else:
        # No description, just name
        return hook_str.strip(), f"Before/After hook: {hook_str.strip()}"


def parse_params_block(block):
    """Parse a parameters block like 'query: page:int,limit:int' or 'action_name: custom_name'"""
    if not block:
        return {}

    block = block.strip("() ")
    if ":" not in block:
        return {}

    param_type, params_str = block.split(":", 1)
    param_type = param_type.strip()

    # Handle action_name specially
    if param_type == "action_name":
        return {"action_name": params_str.strip()}

    # Handle description
    if param_type == "desc":
        return {"desc": params_str.strip()}

    # Handle query and body params
    params = {}
    if params_str:
        param_pairs = [p.strip() for p in params_str.split(",")]
        for pair in param_pairs:
            if ":" in pair:
                name, type_ = pair.split(":", 1)
                params[name.strip()] = type_.strip()

    return {param_type: params}


def parse_method_spec(method_spec):
    """Parse a method specification into its components."""
    # First extract the method/path part (everything before the first parenthesis)
    method_path = method_spec.split("(")[0].strip()
    if ":" not in method_path:
        raise click.BadParameter(f"Invalid method format: {method_spec}")

    http_method, path = method_path.split(":", 1)

    # Extract the parameter blocks
    param_blocks = []
    current_block = ""
    paren_count = 0

    for char in method_spec[len(method_path) :]:
        if char == "(":
            paren_count += 1
            if paren_count == 1:  # Start of a new block
                current_block = "("
            else:
                current_block += char
        elif char == ")":
            paren_count -= 1
            current_block += char
            if paren_count == 0:  # End of current block
                param_blocks.append(current_block)
                current_block = ""
        elif paren_count > 0:  # Inside a block
            current_block += char

    # Parse each parameter block
    path_params = {}
    query_params = {}
    body_params = {}
    action_name = None
    description = None

    for block in param_blocks:
        params = parse_params_block(block)
        if "query" in params:
            query_params.update(params["query"])
        elif "body" in params:
            body_params.update(params["body"])
        elif "desc" in params:
            description = params["desc"]
        elif "action_name" in params:
            action_name = params["action_name"]

    # If no explicit action name is provided, generate one from the path
    if not action_name:
        path_parts = (
            [x for x in path.split("/") if "{" not in x] if "/" in path else [path]
        )
        action_name = to_snake_case(path_parts[-1]) if path_parts else ""

    if description is None:
        description = f"Custom {http_method.upper()} endpoint for {path}"

    return {
        "http_method": http_method.lower(),
        "path": path,
        "path_params": path_params,
        "query_params": query_params,
        "body_params": body_params,
        "action_name": action_name,
        "description": description,
    }


def get_default_action_name(
    http_method: str, path: str, path_params: dict[str, str]
) -> str:
    """
    Generate a default action name from the HTTP method and path,
    if no explicit (action_name: ...) is provided.

    Examples:
    - GET /widgets -> get_widgets
    - GET /widgets/{id} -> get_widget

    """
    # Remove leading/trailing slashes, then split.
    segments = [seg for seg in path.strip("/").split("/") if seg]

    # Filter out path parameter placeholders like '{id}'
    segments = [
        seg for seg in segments if not (seg.startswith("{") and seg.endswith("}"))
    ]

    # If there are no meaningful segments, fallback to just the HTTP method (e.g. 'get', 'post', etc.)
    if not segments:
        return http_method

    # We'll guess that the last segment is the resource name. If it ends with "s", strip it for a singular guess.
    resource_name = segments[-1]

    if resource_name.endswith("s"):
        resource_name = resource_name.rstrip("s")

    # Here we do a naive mapping from HTTP method to an action name.
    # Feel free to tweak these to your liking:
    if http_method == "get":
        # If there's a path param, we assume it's a 'show' or 'get'. If none, we assume it's a 'list'.
        return f"get_{resource_name}" if path_params else f"list_{resource_name}s"
    elif http_method == "post":
        return f"create_{resource_name}"
    elif http_method == "put":
        return f"update_{resource_name}"
    elif http_method == "delete":
        return f"delete_{resource_name}"

    # If none of the above, fallback to an e.g. 'patch_widget' or something:
    return f"{http_method}_{resource_name}"


def parse_field_choices(field_type: str) -> tuple[str, list[str] | None, str | None]:
    """
    Parse field type with optional choices syntax like 'string:choices[user*,admin]'.
    Returns (base_type, choices, default_value).
    """
    if ":choices[" in field_type:
        base_type, choices_part = field_type.split(":choices[")
        if not choices_part.endswith("]"):
            raise click.BadParameter(
                f"Invalid choices syntax in {field_type}. Missing closing bracket.]"
            )
        choices = choices_part.rstrip("]").split(",")
        if not choices:
            raise click.BadParameter(f"No choices provided in {field_type}")

        # Process choices and look for default
        clean_choices = []
        default_value = None

        for choice in choices:
            choice = choice.strip()
            if choice.endswith("*"):
                if default_value is not None:
                    raise click.BadParameter(
                        f"Multiple default values specified in {field_type}"
                    )
                default_value = choice.rstrip("*")
                clean_choices.append(default_value)
            else:
                clean_choices.append(choice)

        return base_type, clean_choices, default_value

    return field_type, None, None


def process_field(name, type_, optional=False, unique=False, indexed=False):
    """Centralized field processing logic."""
    fields_code = ""
    pydantic_code = ""

    # Strip markers from name
    name = name.rstrip("^@?")

    base_type, choices, default_value = parse_field_choices(type_)

    if choices:
        # MongoDB field with choices
        choices_str = ", ".join(f"'{choice}'" for choice in choices)
        field_attrs = [f"choices=[{choices_str}]"]

        if default_value:
            field_attrs.append(f"default='{default_value}'")
        elif not optional:
            field_attrs.append("required=True")

        if unique:
            field_attrs.append("unique=True")
        elif indexed:  # Only add db_index if not unique (since unique implies indexed)
            field_attrs.append("db_index=True")

        fields_code = f"    {name} = StringField({', '.join(field_attrs)})\n"

        # For Pydantic, use Literal type for strict validation
        choices_str = ", ".join(f'"{choice}"' for choice in choices)
        if default_value:
            pydantic_code = f'    {name}: Literal[{choices_str}] = "{default_value}"\n'
        else:
            pydantic_code = f"    {name}: Literal[{choices_str}]\n"

        return fields_code, pydantic_code

    # 1) Hashed string
    if type_ == "hashed_str":
        fields_code = f"    {name} = HashedField(required={not optional})\n"
        pydantic_code = f"    {name}: str  # Hashed field\n"

    # 2) Encrypted string
    elif type_ == "encrypted_str":
        fields_code = f"    {name} = EncryptedField(required={not optional})\n"
        pydantic_code = f"    {name}: str  # Encrypted field\n"

    # 3) File field
    elif type_ == "file":
        fields_code = f"    {name} = FileField(required={not optional})\n"

    # 4) List fields
    elif type_.startswith("list:"):
        inner_type = type_[5:]
        default = ", default=[]" if not optional else ""

        if inner_type == "file":
            attrs = []
            if not optional:
                attrs.append("default=[]")
            attrs_str = f"({', '.join(attrs)})" if attrs else "()"
            fields_code = f"    {name} = FileListField{attrs_str}\n"

        elif inner_type.startswith("ref:"):
            ref_model = inner_type[4:]
            fields_code = (
                f"    {name} = ListField(ReferenceField('{ref_model}'){default})\n"
            )
            pydantic_code = (
                f"    {name}: list[str]  # List of ObjectId references to {ref_model}\n"
            )

        else:
            base_field = mongoengine_type_mapping.get(
                f"list[{inner_type}]", "ListField()"
            )
            # Remove any existing default=[] from the mapping
            base_field = base_field.replace(", default=[]", "")
            # Add required and default if needed
            attrs = []
            if not optional:
                attrs.append("default=[]")
            if attrs:
                base_field = base_field.replace(")", f", {', '.join(attrs)})")

            fields_code = f"    {name} = {base_field}\n"
            pydantic_type = f'list[{pydantic_type_mapping.get(inner_type, "str")}]'
            pydantic_code = f"    {name}: {pydantic_type}\n"

    # 5) Dictionary field
    elif type_.startswith("dict:"):
        key_value_types = type_[5:].split(",")
        key_type = pydantic_type_mapping.get(key_value_types[0].strip(), "str")
        value_type = pydantic_type_mapping.get(key_value_types[1].strip(), "Any")
        fields_code = f"    {name} = DictField(required={not optional})\n"
        pydantic_code = f"    {name}: dict[{key_type}, {value_type}]\n"

    # 6) Reference field
    elif type_.startswith("ref:"):
        ref_model = type_[4:]
        fields_code = (
            f"    {name} = ReferenceField('{ref_model}', required={not optional})\n"
        )
        pydantic_code = f"    {name}: str  # ObjectId reference to {ref_model}\n"

    # 7) Standard fields
    else:
        mongo_field = mongoengine_type_mapping.get(type_.lower(), "StringField()")
        field_attrs = []
        if not optional:
            field_attrs.append("required=True")
        if unique:
            field_attrs.append("unique=True")
        elif indexed:  # Only add db_index if not unique
            field_attrs.append("db_index=True")
        if field_attrs:
            mongo_field = mongo_field.replace("()", f"({', '.join(field_attrs)})")

        fields_code = f"    {name} = {mongo_field}\n"
        pydantic_type = pydantic_type_mapping.get(type_.lower(), "str")
        pydantic_code = f"    {name}: {pydantic_type}\n"

    return fields_code, pydantic_code


def process_index_option(index_str: str) -> dict:
    """
    Process an index option string into a MongoEngine index specification.
    """
    # Split into fields and options
    if "[" in index_str:
        fields_part, options_part = index_str.rsplit("[", 1)
        if not options_part.endswith("]"):
            raise click.BadParameter(
                f"Invalid index format: {index_str}. Missing closing bracket.]"
            )
        options_str = options_part.rstrip("]")
        options = [opt.strip().lower() for opt in options_str.split(",")]
    else:
        fields_part = index_str
        options = []

    # Process fields
    fields = []
    for field in fields_part.split(","):
        field = field.strip()
        field.rstrip("^?")  # Strip any markers

        if not field:
            raise click.BadParameter(f"Empty field in index specification: {index_str}")
        # Add minus sign for descending order
        if "desc" in options:
            field = f"-{field}"
        fields.append(field)

    # If no special options, return simple tuple format
    if not {"unique", "sparse"}.intersection(options):
        return {"fields": tuple(fields)}

    # Process options with special flags
    index_spec = {"fields": fields}
    if "unique" in options:
        index_spec["unique"] = True
    if "sparse" in options:
        index_spec["sparse"] = True

    return index_spec


def load_model_class(model_name: str) -> DBBaseModel:
    """Load a model class by name."""
    if model_name in CORE_MODEL_MAPPINGS:
        module_path, class_name = CORE_MODEL_MAPPINGS[model_name].rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    else:
        models_dir = config.MODELS_DIR.lstrip(".").lstrip("/").rstrip("/").split("/")
        models_dir = os.path.join(os.getcwd(), *models_dir)

        if not os.path.exists(models_dir):
            raise click.ClickException(
                f"Error: Models directory '{models_dir}' not found."
            )

        for root, _, files in os.walk(models_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    file_path = os.path.join(root, file)
                    module_name = os.path.relpath(file_path, os.getcwd())[:-3].replace(
                        os.sep, "."
                    )

                    spec = importlib.util.spec_from_file_location(
                        module_name, file_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and name == model_name
                            and obj.__module__ == module.__name__
                        ):
                            return obj

        raise click.ClickException(
            f"Error: Model class '{model_name}' not found in '{models_dir}'."
        )


def extract_parent_fields(model_class: DBBaseModel) -> list[str]:
    """
    Extract parent class fields from a model class.
    """
    parent_fields = []
    for field_name, field_instance in model_class._fields.items():
        if field_name in {
            "created_at",
            "updated_at",
            "deleted_at",
            "id",
            "_cls",
            "_id",
        }:
            continue

        field_type = get_inner_field_type(field_instance)

        # Add field modifiers
        field_def = field_name
        if getattr(field_instance, "unique", False):
            field_def += "^"
        if not getattr(field_instance, "required", True):
            field_def += "?"

        field_def += f":{field_type}"

        parent_fields.append(field_def)

    return parent_fields
