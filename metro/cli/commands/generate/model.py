import os
import click
from pydantic import BaseModel

from metro.cli.utils import (
    process_field,
    process_fields,
    process_inheritance,
)
from metro.templates import model_template
from metro.utils import (
    to_snake_case,
    to_pascal_case,
)
from metro.utils.file_operations import insert_line_without_duplicating, format_python
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
    index: tuple[str, ...] = (),
    additional_template_vars: dict = None,
) -> GenerateModelOutput:
    snake_case_name = to_snake_case(model_name)
    pascal_case_name = to_pascal_case(model_name)

    base_classes, additional_imports_list = process_inheritance(model_inherits)
    processed_fields = process_fields(fields, indexes=index)

    meta_indexes = ""
    if processed_fields.meta_indexes:
        indexes_str = []
        for idx in processed_fields.meta_indexes:
            if "unique" in idx or "sparse" in idx:
                # Complex index with options
                fields_str = repr(idx["fields"])
                options = []
                if idx.get("unique"):
                    options.append("'unique': True")
                if idx.get("sparse"):
                    options.append("'sparse': True")
                indexes_str.append(f"{{'fields': {fields_str}, {', '.join(options)}}}")
            else:
                # Simple index
                fields_str = (
                    repr(idx["fields"])
                    if len(idx["fields"]) > 1
                    else repr(idx["fields"][0])
                )
                indexes_str.append(fields_str)

        meta_indexes = (
            f"\n        'indexes': [{', '.join(indexes_str)}]," if indexes_str else ""
        )

    fields_code, pydantic_code, fields_additional_imports = (
        processed_fields.fields_code,
        processed_fields.pydantic_code,
        processed_fields.additional_imports,
    )
    additional_imports_list.extend(fields_additional_imports)

    additional_imports = (
        "\n" + "\n".join(additional_imports_list) if additional_imports_list else ""
    )

    template_vars = {
        "resource_name_pascal": pascal_case_name,
        "resource_name_snake": snake_case_name,
        "fields": fields_code,
        "base_classes": base_classes,
        "additional_imports": additional_imports,
        "meta_indexes": meta_indexes,
    }

    if additional_template_vars:
        template_vars.update(additional_template_vars)

    content = model_template.format(**template_vars)
    content = format_python(content)

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
@click.option(
    "--index",
    multiple=True,
    help="Add compound index. Format: 'field1,field2[unique,sparse,desc]'",
)
def model(model_name, fields, model_inherits, index):
    """Generate a new model."""
    output = generate_model(model_name, fields, model_inherits, index)

    click.echo(
        click.style(
            f"Model '{output.pascal_case_name}' generated at '{output.model_path}' and added to {output.init_path}.",
            fg="green",
        )
    )
