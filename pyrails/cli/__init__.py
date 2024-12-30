import importlib.util
import os
import shutil
import subprocess
import sys
import click
import uvicorn

from .project import new
from .generate import generate
from .db import db
from .admin import admin


@click.group()
def cli():
    pass


cli.add_command(new, name="new")
cli.add_command(generate, name="generate")
cli.add_command(generate, name="g")
cli.add_command(db, name="db")
cli.add_command(admin, name="admin")


@cli.command()
@click.option("--port", default=8080, help="Port to run the server on")
@click.option("--host", default="127.0.0.1", help="Host to run the server on")
@click.option("--docker", is_flag=True, help="Run the application in Docker")
def run(port, host, docker):
    """Run the PyRails application server."""
    if docker:
        run_docker_compose(port)
    else:
        run_local_server(host, port)


def run_docker_compose(port):
    click.echo("Starting PyRails server in Docker mode with hot reloading...")

    # Check if Docker is installed
    if not shutil.which("docker"):
        click.echo(
            "Docker is not installed. Please install Docker to use this feature."
        )
        sys.exit(1)

    # Check if docker-compose.yml exists
    if not os.path.exists("docker-compose.yml"):
        click.echo("docker-compose.yml not found in the current directory.")
        sys.exit(1)

    try:
        # Build and run Docker containers with hot reloading
        subprocess.run(["docker-compose", "build"], check=True)
        subprocess.run(["docker-compose", "up", "--build"], check=True)

        click.echo(
            f"PyRails application is running in Docker with hot reloading. Access it at http://localhost:{port}"
        )
        click.echo("Use Ctrl+C to stop the application.")
    except subprocess.CalledProcessError as e:
        click.echo(f"An error occurred while running Docker Compose: {e}")
        sys.exit(1)


def run_local_server(host, port):
    click.echo(f"Starting PyRails server locally on {host}:{port} with hot reloading...")

    try:
        # Get the current working directory
        current_dir = os.getcwd()

        # Add the current directory to sys.path
        sys.path.insert(0, current_dir)

        # Try to import the main module
        spec = importlib.util.spec_from_file_location(
            "main", os.path.join(current_dir, "main.py")
        )
        if spec is None:
            click.echo("main.py not found in the current directory.")
            return

        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)

        # Check if 'app' exists in the main module
        if not hasattr(main_module, "app"):
            click.echo(
                "'app' not found in main.py. Make sure you have defined 'app = PyRailsApp()' in your main.py file."
            )
            return

        # Run the application with hot reloading
        uvicorn.run("main:app", host=host, port=port, reload=True)
    except ImportError as e:
        click.echo(f"Failed to import the application: {e}")
        click.echo(
            "Make sure you're in the correct directory and all required packages are installed."
        )
        import traceback

        click.echo(traceback.format_exc())
    except Exception as e:
        click.echo(f"An error occurred while starting the server: {e}")
        import traceback

        click.echo(traceback.format_exc())


if __name__ == "__main__":
    cli()
