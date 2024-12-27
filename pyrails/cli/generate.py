import os

import click

from ..templates import (
    controller_template,
    model_template,
    scaffold_controller_template,
    job_template,
    worker_template,
)
from ..utils import (
    pluralize,
    to_snake_case,
    to_pascal_case,
    mongoengine_type_mapping,
    pydantic_type_mapping,
    is_valid_identifier,
)
from ..utils.file_operations import insert_line_without_duplicating


@click.group()
def generate():
    """Generate code."""
    pass


@generate.command()
@click.argument("model_name")
@click.argument("fields", nargs=-1)
def model(model_name, fields):
    """Generate a new model."""
    snake_case_name = to_snake_case(model_name)
    pascal_case_name = to_pascal_case(model_name)

    fields_code = ""
    pydantic_code = ""

    for field in fields:
        # Split into name and type_ based on the first colon only
        name, type_ = field.split(":", 1)

        # Determine if the field should be unique or optional
        unique = name.endswith("^")
        optional = name.endswith("_")

        # Remove the trailing markers
        name = name.rstrip("^_")

        # Special field types:

        # 1) Hashed string
        if type_ == "hashed_str":
            fields_code += f"    {name} = HashedField(required={not optional})\n"
            pydantic_code += f"    {name}: str  # Hashed field\n"

        # 2) Encrypted string
        elif type_ == "encrypted_str":
            fields_code += f"    {name} = EncryptedField(required={not optional})\n"
            pydantic_code += f"    {name}: str  # Encrypted field\n"

        # 3) File field
        elif type_ == "file":
            # Use FileField, exclude from Pydantic (skip pydantic_code)
            fields_code += f"    {name} = FileField(required={not optional})\n"

        # 4) list:some_type logic (could be list:file or list:ref:Model, etc.)
        elif type_.startswith("list:"):
            inner_type = type_[5:]

            # 4a) list:file => FileListField
            if inner_type == "file":
                fields_code += f"    {name} = FileListField(required={not optional})\n"
                # Exclude from Pydantic
            # 4b) list:ref:Model => many-to-many references
            elif inner_type.startswith("ref:"):
                ref_model = inner_type[4:]
                fields_code += (
                    f"    {name} = ListField(ReferenceField('{ref_model}'), required={not optional})\n"
                )
                pydantic_code += f"    {name}: list[str]  # List of ObjectId references to {ref_model}\n"
            # 4c) list of standard type
            else:
                mongo_field = mongoengine_type_mapping.get(
                    f"list[{inner_type}]", "ListField()"
                )
                pydantic_type = f'list[{pydantic_type_mapping.get(inner_type, "str")}]'
                fields_code += f"    {name} = {mongo_field}\n"
                pydantic_code += f"    {name}: {pydantic_type}\n"

        # 5) dict: syntax (e.g. dict:str,int)
        elif type_.startswith("dict:"):
            key_value_types = type_[5:].split(",")
            key_type = pydantic_type_mapping.get(key_value_types[0].strip(), "str")
            value_type = pydantic_type_mapping.get(key_value_types[1].strip(), "Any")
            fields_code += f"    {name} = DictField(required={not optional})\n"
            pydantic_code += f"    {name}: dict[{key_type}, {value_type}]\n"

        # 6) Reference field (ref:SomeModel)
        elif type_.startswith("ref:"):
            ref_model = type_[4:]
            fields_code += (
                f"    {name} = ReferenceField('{ref_model}', required={not optional})\n"
            )
            pydantic_code += f"    {name}: str  # ObjectId reference to {ref_model}\n"

        # 7) Standard fields (str, int, bool, etc.)
        else:
            mongo_field = mongoengine_type_mapping.get(type_.lower(), "StringField()")
            # Add required and unique attributes
            if not optional:
                mongo_field = mongo_field.replace("()", "(required=True)")
            if unique:
                mongo_field = mongo_field.replace(")", ", unique=True)")
            pydantic_type = pydantic_type_mapping.get(type_.lower(), "str")

            fields_code += f"    {name} = {mongo_field}\n"
            pydantic_code += f"    {name}: {pydantic_type}\n"

    # Create final model file
    content = model_template.format(
        model_name=pascal_case_name,
        fields=fields_code,
        table_name=snake_case_name,
    )
    model_path = f"app/models/{snake_case_name}.py"
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "w") as f:
        f.write(content)

    # Update models/__init__.py
    init_path = "app/models/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {pascal_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(
        f"Model '{pascal_case_name}' generated at '{model_path}' and added to {init_path}."
    )


@generate.command()
@click.argument("controller_name")
@click.argument("methods", nargs=-1)  # Accept multiple methods
def controller(controller_name, methods):
    """Generate a new controller."""
    snake_case_name = to_snake_case(controller_name)
    pascal_case_name = to_pascal_case(controller_name)
    kebab_case_name = snake_case_name.replace("_", "-")

    methods_code = "    pass\n" if not methods else ""

    for method in methods:
        http_method, action = method.split(":")
        action_snake = to_snake_case(action)
        action_kebab = action_snake.replace("_", "-")

        if http_method.lower() == "get":
            methods_code += (
                f"    @get('/{kebab_case_name}/{action_kebab}')\n"
                f"    async def {action_snake}(self, request):\n"
                f"        pass\n\n"
            )
        elif http_method.lower() == "post":
            methods_code += (
                f"    @post('/{kebab_case_name}/{action_kebab}')\n"
                f"    async def {action_snake}(self, request):\n"
                f"        pass\n\n"
            )
        elif http_method.lower() == "put":
            methods_code += (
                f"    @put('/{kebab_case_name}/{action_kebab}')\n"
                f"    async def {action_snake}(self, request):\n"
                f"        pass\n\n"
            )
        elif http_method.lower() == "delete":
            methods_code += (
                f"    @delete('/{kebab_case_name}/{action_kebab}')\n"
                f"    async def {action_snake}(self, request):\n"
                f"        pass\n\n"
            )
        else:
            click.echo(
                f"Invalid HTTP method '{http_method}' provided for action '{action}'."
            )

    content = controller_template.format(
        pascal_case_name=pascal_case_name,
        methods_code=methods_code,
    ).rstrip()
    content += "\n"

    controller_path = f"app/controllers/{snake_case_name}_controller.py"
    os.makedirs(os.path.dirname(controller_path), exist_ok=True)
    with open(controller_path, "w") as f:
        f.write(content)

    # Update controllers __init__.py
    init_path = "app/controllers/__init__.py"
    line_to_insert = f"from .{snake_case_name}_controller import {pascal_case_name}Controller"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(f"Controller '{pascal_case_name}' generated at '{controller_path}'.")


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
def scaffold(name, fields):
    """
    Generate a model and controller with CRUD functionality.
    Skips file fields from the default Pydantic schema, so you'll create
    specialized routes for file uploads if needed.
    """
    snake_case_name = to_snake_case(name)
    pascal_case_name = to_pascal_case(name)
    plural_snake_case = to_snake_case(pluralize(name))
    plural_pascal_case = to_pascal_case(pluralize(name))
    plural_kebab_case = plural_snake_case.replace("_", "-")

    fields_code = ""
    pydantic_code = ""

    for field in fields:
        # Split into name and type_ based on the first colon only
        name, type_ = field.split(":", 1)

        # Determine if the field should be unique or optional
        unique = name.endswith("^")
        optional = name.endswith("_")

        # Remove trailing markers
        name = name.rstrip("^_")

        # 1) hashed_str
        if type_ == "hashed_str":
            fields_code += f"    {name} = HashedField(required={not optional})\n"
            pydantic_code += f"    {name}: str  # Hashed field\n"

        # 2) encrypted_str
        elif type_ == "encrypted_str":
            fields_code += f"    {name} = EncryptedField(required={not optional})\n"
            pydantic_code += f"    {name}: str  # Encrypted field\n"

        # 3) file (excluded from default pydantic)
        elif type_ == "file":
            fields_code += f"    {name} = FileField(required={not optional})\n"

        # 4) list:some_type
        elif type_.startswith("list:"):
            inner_type = type_[5:]

            if inner_type == "file":
                # FileListField => skip pydantic
                fields_code += f"    {name} = FileListField(required={not optional})\n"

            elif inner_type.startswith("ref:"):
                ref_model = inner_type[4:]
                fields_code += (
                    f"    {name} = ListField(ReferenceField('{ref_model}'), required={not optional})\n"
                )
                pydantic_code += f"    {name}: list[str]  # List of ObjectId references to {ref_model}\n"
            else:
                mongo_field = mongoengine_type_mapping.get(
                    f"list[{inner_type}]", "ListField()"
                )
                pydantic_type = f'list[{pydantic_type_mapping.get(inner_type, "str")}]'
                fields_code += f"    {name} = {mongo_field}\n"
                pydantic_code += f"    {name}: {pydantic_type}\n"

        # 5) dict:...
        elif type_.startswith("dict:"):
            key_value_types = type_[5:].split(",")
            key_type = pydantic_type_mapping.get(key_value_types[0].strip(), "str")
            value_type = pydantic_type_mapping.get(key_value_types[1].strip(), "Any")
            fields_code += f"    {name} = DictField(required={not optional})\n"
            pydantic_code += f"    {name}: dict[{key_type}, {value_type}]\n"

        # 6) ref:Model
        elif type_.startswith("ref:"):
            ref_model = type_[4:]
            fields_code += (
                f"    {name} = ReferenceField('{ref_model}', required={not optional})\n"
            )
            pydantic_code += f"    {name}: str  # ObjectId reference to {ref_model}\n"

        # 7) Standard field
        else:
            mongo_field = mongoengine_type_mapping.get(type_.lower(), "StringField()")
            field_attrs = []
            if not optional:
                field_attrs.append("required=True")
            if unique:
                field_attrs.append("unique=True")
            if field_attrs:
                # e.g. "StringField()" -> "StringField(required=True, unique=True)"
                mongo_field = mongo_field.replace("()", f"({', '.join(field_attrs)})")

            pydantic_type = pydantic_type_mapping.get(type_.lower(), "str")
            fields_code += f"    {name} = {mongo_field}\n"
            pydantic_code += f"    {name}: {pydantic_type}\n"

    # Build the model file content
    model_content = model_template.format(
        resource_name_pascal=pascal_case_name,
        resource_name_snake=snake_case_name,
        resource_name_plural_pascal=plural_pascal_case,
        resource_name_plural_kebab=plural_kebab_case,
        resource_name_plural_snake=plural_snake_case,
        fields=fields_code,
    )
    model_path = f"app/models/{snake_case_name}.py"
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "w") as f:
        f.write(model_content)

    # Build the controller file content
    controller_content = scaffold_controller_template.format(
        resource_name_pascal=pascal_case_name,
        resource_name_snake=snake_case_name,
        resource_name_plural_pascal=plural_pascal_case,
        resource_name_plural_kebab=plural_kebab_case,
        pydantic_fields=pydantic_code,
    )
    controller_path = f"app/controllers/{plural_snake_case}_controller.py"
    os.makedirs(os.path.dirname(controller_path), exist_ok=True)
    with open(controller_path, "w") as f:
        f.write(controller_content)

    # Update controllers __init__.py
    init_path = "app/controllers/__init__.py"
    line_to_insert = f"from .{plural_snake_case}_controller import {plural_pascal_case}Controller"
    insert_line_without_duplicating(init_path, line_to_insert)

    # Update models __init__.py
    init_path = "app/models/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {pascal_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(f"Scaffold for '{pascal_case_name}' generated.")


@generate.command()
@click.argument("job_name")
@click.option(
    "--queue",
    default="default",
    help="Specify the queue name for the job. Defaults to 'default'.",
)
@click.option(
    "--batch-size",
    type=int,
    default=None,
    help="Number of jobs to batch before execution.",
)
@click.option(
    "--batch-interval",
    type=int,
    default=None,
    help="Time interval (in seconds) to wait before executing a batch.",
)
def job(job_name, queue, batch_size, batch_interval):
    """Generate a new job class."""
    snake_case_name = to_snake_case(job_name)
    pascal_case_name = to_pascal_case(job_name)

    # Prepare batch parameters
    batchable_config_str = ""
    if batch_size is not None:
        batchable_config_str += f"    batch_size = {batch_size}\n"
    if batch_interval is not None:
        batchable_config_str += f"    batch_interval = {batch_interval}\n"
    if batchable_config_str:
        batchable_config_str = "\n" + batchable_config_str.rstrip()

    perform_str = """
    async def perform(self, *args, **kwargs):
        \"\"\"
        The method containing the job logic.
        Must be implemented by subclasses.
        \"\"\"
        logger.info(f"Executing {self.__class__.__name__} with args: {args} and kwargs: {kwargs}")
        # TODO: Implement the job logic here
        pass
    """.strip()

    perform_batch_str = """
    async def perform_batch(self, jobs: list[dict[str, any]]):
        \"\"\"
        The method containing the batch job logic.
        Must be implemented by batchable subclasses.
        \"\"\"
        logger.info(f"Executing batch {self.__class__.__name__} with {len(jobs)} jobs.")
        # TODO: Implement the batch job logic here
        pass
    """.strip()

    content = job_template.format(
        job_class_name=pascal_case_name,
        queue_name=queue,
        batchable_config=batchable_config_str,
        perform_method=(perform_batch_str if (batch_size or batch_interval) else perform_str),
    )
    job_path = f"app/jobs/{snake_case_name}.py"
    os.makedirs(os.path.dirname(job_path), exist_ok=True)
    with open(job_path, "w") as f:
        f.write(content)

    # Update jobs __init__.py
    init_path = "app/jobs/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {pascal_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(f"Job '{pascal_case_name}' generated at '{job_path}' and added to {init_path}.")


@generate.command()
@click.argument("worker_name", default="worker")
@click.option(
    "--backend-host",
    default="localhost",
    help="Redis backend host. Defaults to 'localhost'.",
)
@click.option(
    "--backend-port",
    default=6379,
    type=int,
    help="Redis backend port. Defaults to 6379.",
)
@click.option(
    "--backend-db",
    default=0,
    type=int,
    help="Redis backend database number. Defaults to 0.",
)
@click.option(
    "--job-modules",
    multiple=True,
    default=["app.jobs"],
    help="Specify job modules to include in the worker. Defaults to 'app.jobs'.",
)
@click.option(
    "--job-directories",
    multiple=True,
    default=["app/jobs"],
    help="Specify directories to load jobs from. Defaults to 'app/jobs'.",
)
def worker(
    worker_name,
    backend_host,
    backend_port,
    backend_db,
    job_modules,
    job_directories
):
    """Generate a new worker class."""
    if not is_valid_identifier(worker_name):
        click.echo(f"Error: '{worker_name}' is not a valid Python class name.")
        return

    snake_case_name = to_snake_case(worker_name)

    # Prepare job modules import
    job_modules_import = ", ".join(job_modules)

    # Prepare job directories as a list
    job_directories_str = "[" + ", ".join(f"'{dir_}'" for dir_ in job_directories) + "]"

    content = worker_template.format(
        backend_host=backend_host,
        backend_port=backend_port,
        backend_db=backend_db,
        job_modules_import=job_modules_import,
        job_directories=job_directories_str,
    )
    worker_path = f"workers/{snake_case_name}.py"
    os.makedirs(os.path.dirname(worker_path), exist_ok=True)
    with open(worker_path, "w") as f:
        f.write(content)

    # Update workers __init__.py
    init_path = "workers/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {snake_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(
        f"Worker '{snake_case_name}' generated at '{worker_path}' and added to {init_path}."
    )
