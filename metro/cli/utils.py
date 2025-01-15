import click

from metro.utils import mongoengine_type_mapping, pydantic_type_mapping, to_snake_case


def clean_up_file_whitespace(text: str) -> str:
    """Clean up excessive whitespace in Python code while respecting scope.

    This function enforces the following rules:
    - Maximum 2 consecutive empty lines at root level (indent=0)
    - Maximum 1 consecutive empty line within indented blocks
    - Ensures 2 empty lines before class definitions at root level
    - Ensures 1 empty line when decreasing indentation level (except for closing brackets/braces and docstrings)
    - Preserves indentation and internal formatting
    - Strips trailing whitespace from each line
    - Ensures file ends with single newline
    """
    lines = text.splitlines()
    cleaned = []
    consecutive_empty = 0
    last_nonempty_indent = 0

    for i, line in enumerate(lines):
        # Get indentation level and check if line is empty
        indent = len(line) - len(line.lstrip())
        stripped_line = line.strip()
        is_empty = not stripped_line
        is_root_class = stripped_line.startswith("class ") and indent == 0

        # Check if this line is just a closing bracket/brace/quote
        is_closing = stripped_line in [")", "]", "}", '"""', "'''"]
        # Check if next line (if exists) starts with a closing bracket/brace/quote
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        next_is_closing = next_line in [")", "]", "}", '"""', "'''"]

        if is_empty:
            consecutive_empty += 1
            if consecutive_empty <= (1 if last_nonempty_indent > 0 else 2):
                cleaned.append("")
        else:
            if is_root_class:
                while cleaned and cleaned[-1] == "":
                    cleaned.pop()
                cleaned.extend(["", ""])
            # Only add newline for indentation decrease if:
            # - Current line isn't a closing character
            # - Next line isn't a closing character
            # - We're actually decreasing indentation
            # - We don't already have an empty line
            elif (
                indent < last_nonempty_indent
                and not is_closing
                and not next_is_closing
                and cleaned
                and cleaned[-1] != ""
            ):
                cleaned.append("")

            consecutive_empty = 0
            last_nonempty_indent = indent
            cleaned.append(line.rstrip())

    return "\n".join(cleaned).strip() + "\n"


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


def process_fields(fields: tuple[str, ...]) -> tuple[str, str]:
    """
    Process field definitions and generate model fields and Pydantic schemas.

    Args:
        fields: Tuple of field definitions in format "name:type"

    Returns:
        Tuple of (fields_code, pydantic_code)
    """
    fields_code = ""
    pydantic_code = ""

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

            if not name or not type_:
                raise click.BadParameter(
                    f"Invalid field format: {field}. Name and type cannot be empty"
                )

            unique = name.endswith("^")
            optional = name.endswith("_")
            field_code, pydantic = process_field(name, type_, optional, unique)
            fields_code += field_code
            pydantic_code += pydantic

        except ValueError as e:
            raise click.BadParameter(f"Error processing field {field}: {str(e)}")

    return fields_code, pydantic_code


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
    """Parse a parameters block like 'query: page:int,limit:int'"""
    if not block:
        return {}

    block = block.strip("() ")
    if ":" not in block:
        return {}

    param_type, params_str = block.split(":", 1)
    param_type = param_type.strip()
    params = {}

    if params_str:
        # For description, just use the entire params string as is
        if param_type == "desc":
            return {"desc": params_str.strip()}

        # For query and body params, parse the key-value pairs
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

    # Extract path parameters
    path_params = {}
    final_path_parts = []

    for part in path.split("/"):
        if not part:  # Skip empty parts
            continue

        if "{" in part and "}" in part:
            param_start = part.find("{") + 1
            param_end = part.find("}")
            param_name = part[param_start:param_end]

            # Check for type specification in ()
            param_type = "str"  # Default type
            if "(" in part and ")" in part:
                type_start = part.find("(") + 1
                type_end = part.find(")")
                param_type = part[type_start:type_end]

            path_params[param_name] = param_type
            final_path_parts.append(f"{{{param_name}}}")
        else:
            final_path_parts.append(part)

    final_path = "/".join(final_path_parts)

    # Parse parameter blocks for query, body, and description
    query_params = {}
    body_params = {}
    description = None

    path_parts = [x for x in path.split("/") if "{" not in x] if "/" in path else [path]
    action_name = to_snake_case(path_parts[-1]) if path_parts else ""
    if action_name in ["get", "post", "put", "delete"]:
        action_name = (
            to_snake_case(path_parts[:-2])
            if len(path_parts) > 1
            else f"{action_name}_method"
        )

    for block in param_blocks:
        params = parse_params_block(block)
        if "query" in params:
            query_params.update(params["query"])
        elif "body" in params:
            body_params.update(params["body"])
        elif "desc" in params:
            description = params["desc"]
        elif "action_name" in params:
            action_name = to_snake_case(["action_name"])

    if description is None:
        description = f"Custom {http_method.upper()} endpoint for {final_path}"

    return {
        "http_method": http_method.lower(),
        "path": final_path,
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


def process_field(name, type_, optional=False, unique=False):
    """Centralized field processing logic."""
    fields_code = ""
    pydantic_code = ""

    # Strip markers from name
    name = name.rstrip("^_")

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
            fields_code = f"    {name} = FileListField({default})\n"

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
        if field_attrs:
            mongo_field = mongo_field.replace("()", f"({', '.join(field_attrs)})")

        fields_code = f"    {name} = {mongo_field}\n"
        pydantic_type = pydantic_type_mapping.get(type_.lower(), "str")
        pydantic_code = f"    {name}: {pydantic_type}\n"

    return fields_code, pydantic_code