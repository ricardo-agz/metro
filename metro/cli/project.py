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


@click.command()
@click.argument("project_name")
def new(project_name):
    """Create a new Metro project."""
    os.makedirs(f"{project_name}/app/controllers", exist_ok=True)
    os.makedirs(f"{project_name}/app/models", exist_ok=True)
    os.makedirs(f"{project_name}/config", exist_ok=True)

    # create __init__.py files
    with open(f"{project_name}/app/__init__.py", "w") as f:
        f.write("")
    with open(f"{project_name}/app/controllers/__init__.py", "w") as f:
        f.write("")
    with open(f"{project_name}/app/models/__init__.py", "w") as f:
        f.write("")
    with open(f"{project_name}/config/__init__.py", "w") as f:
        f.write("from .development import *\n")
        f.write("from .production import *\n")
        f.write("from .testing import *\n")

    # Create .env file
    with open(f"{project_name}/.env", "w") as f:
        f.write("METRO_ENV=development\n")
        f.write("DEBUG=True\n")

    # Create main.py
    with open(f"{project_name}/main.py", "w") as f:
        f.write(main_template)

    # Create config files
    for env in ["development", "production", "testing"]:
        with open(f"{project_name}/config/{env}.py", "w") as f:
            f.write(f"DATABASE_URL = 'mongodb://localhost:27017'\n")

    # Create docker-compose.yml
    with open(f"{project_name}/docker-compose.yml", "w") as f:
        f.write(docker_compose_template.format(project_name=project_name))

    # Create Dockerfile
    with open(f"{project_name}/Dockerfile", "w") as f:
        f.write(dockerfile_template.format(project_name=project_name))

    # Create .gitignore
    with open(f"{project_name}/.gitignore", "w") as f:
        f.write(gitignore_template)

    # Create .dockerignore
    with open(f"{project_name}/.dockerignore", "w") as f:
        f.write(dockerignore_template)

    # Create README.md
    with open(f"{project_name}/README.md", "w") as f:
        f.write(readme_template.format(PROJECT_NAME=project_name))

    # Create requirements.txt
    with open(f"{project_name}/requirements.txt", "w") as f:
        f.write("metro\n")
        f.write("uvicorn\n")

    click.echo(f"New Metro project '{project_name}' created with Docker support.")
