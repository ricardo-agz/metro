import os
import click
from pydantic import BaseModel

from metro.cli.utils import (
    process_field,
    process_fields,
    process_inheritance,
    clean_up_file_whitespace,
)
from metro.templates import model_template
from metro.utils import (
    to_snake_case,
    to_pascal_case,
)
from metro.utils.file_operations import insert_line_without_duplicating
from metro.config import config


models_dir = config.MODELS_DIR.lstrip(".").lstrip("/").rstrip("/")


class GenerateModelOutput(BaseModel):
    model_path: str
    init_path: str
    pascal_case_name: str
    snake_case_name: str


def generate_model(
    model_name: str,
    fields: tuple[str, ...],
    model_inherits: str = None,
    additional_template_vars: dict = None,
) -> GenerateModelOutput:
    snake_case_name = to_snake_case(model_name)
    pascal_case_name = to_pascal_case(model_name)

    base_classes, additional_imports_list = process_inheritance(model_inherits)
    fields_code, pydantic_code = process_fields(fields)

    additional_imports = (
        "\n" + "\n".join(additional_imports_list) if additional_imports_list else ""
    )

    template_vars = {
        "resource_name_pascal": pascal_case_name,
        "resource_name_snake": snake_case_name,
        "fields": fields_code,
        "base_classes": base_classes,
        "additional_imports": additional_imports,
    }

    if additional_template_vars:
        template_vars.update(additional_template_vars)

    content = model_template.format(**template_vars)
    content = clean_up_file_whitespace(content)

    # Create the model file
    model_path = f"{models_dir}/{snake_case_name}.py"
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "w") as f:
        f.write(content)

    # Update __init__.py
    init_path = f"{models_dir}/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {pascal_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    return GenerateModelOutput(
        model_path=model_path,
        init_path=init_path,
        pascal_case_name=pascal_case_name,
        snake_case_name=snake_case_name,
    )


@click.command()
@click.argument("model_name")
@click.argument("fields", nargs=-1)
@click.option(
    "--model-inherits",
    default=None,
    help="Base class(es) to inherit from, e.g. UserBase or 'UserBase, SomeMixin'",
)
def model(model_name, fields, model_inherits):
    """Generate a new model."""
    output = generate_model(model_name, fields, model_inherits)

    click.echo(
        click.style(
            f"Model '{output.pascal_case_name}' generated at '{output.model_path}' and added to {output.init_path}.",
            fg="green",
        )
    )
