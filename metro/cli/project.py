import re

import click
import os
from metro.templates import (
    docker_compose_template,
    dockerfile_template,
    gitignore_template,
    dockerignore_template,
    readme_template,
    main_template,
)


def format_project_name(name: str) -> str:
    """Format project name to be a valid Python package name and directory name."""
    if name == ".":
        return name

    # Convert to lowercase
    name = name.lower()

    # Replace spaces and hyphens with underscores
    name = re.sub(r"[-\s]+", "_", name)

    # Remove any characters that aren't alphanumeric or underscore
    name = re.sub(r"[^\w]", "", name)

    # Ensure it starts with a letter (required for Python packages)
    if name and not name[0].isalpha():
        raise click.UsageError(
            click.style("Project name must start with a letter.", fg="red")
        )

    # If empty after cleaning, provide a default
    if not name:
        raise click.UsageError(click.style("Invalid project name.", fg="red"))

    return name


@click.command()
@click.argument("project_name")
def new(project_name):
    """Create a new Metro project."""
    # Handle base path
    base_path = "" if project_name == "." else f"{project_name}/"
    project_name = format_project_name(project_name)

    # Create directory structure
    if project_name != ".":
        os.makedirs(f"{base_path}app/controllers", exist_ok=True)
        os.makedirs(f"{base_path}app/models", exist_ok=True)
        os.makedirs(f"{base_path}config", exist_ok=True)
    else:
        os.makedirs("app/controllers", exist_ok=True)
        os.makedirs("app/models", exist_ok=True)
        os.makedirs("config", exist_ok=True)

    # Create files using the base path
    files_to_create = {
        f"{base_path}app/__init__.py": "",
        f"{base_path}app/controllers/__init__.py": "",
        f"{base_path}app/models/__init__.py": "",
        f"{base_path}config/__init__.py": "from .development import *\nfrom .production import *\nfrom .testing import *\n",
        f"{base_path}.env": "METRO_ENV=development\nDEBUG=True\n",
        f"{base_path}main.py": main_template,
        f"{base_path}docker-compose.yml": docker_compose_template.format(
            project_name=project_name.replace(".", os.path.basename(os.getcwd()))
        ),
        f"{base_path}Dockerfile": dockerfile_template.format(
            project_name=project_name.replace(".", os.path.basename(os.getcwd()))
        ),
        f"{base_path}.gitignore": gitignore_template,
        f"{base_path}.dockerignore": dockerignore_template,
        f"{base_path}README.md": readme_template.format(
            PROJECT_NAME=project_name.replace(".", os.path.basename(os.getcwd()))
        ),
        f"{base_path}requirements.txt": "metro\nuvicorn\n",
    }

    # Create config files
    for env in ["development", "production", "testing"]:
        files_to_create[f"{base_path}config/{env}.py"] = (
            f"DATABASE_URL = 'mongodb://localhost:27017'\n"
        )

    # Write all files
    for file_path, content in files_to_create.items():
        with open(file_path, "w") as f:
            f.write(content)

    project_display_name = (
        "current directory" if project_name == "." else f"'{project_name}'"
    )
    click.echo(
        click.style(
            f"🚀 Created new Metro project in {project_display_name}", fg="bright_green"
        )
    )
