import os
import click

from metro.templates import worker_template
from metro.utils import (
    to_snake_case,
    is_valid_identifier,
)
from metro.utils.file_operations import insert_line_without_duplicating
from metro.config import config


workers_dir = config.WORKERS_DIR.lstrip(".").lstrip("/").rstrip("/")


@click.command()
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
    worker_name, backend_host, backend_port, backend_db, job_modules, job_directories
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
    worker_path = f"{workers_dir}/{snake_case_name}.py"
    os.makedirs(os.path.dirname(worker_path), exist_ok=True)
    with open(worker_path, "w") as f:
        f.write(content)

    # Update workers __init__.py
    init_path = f"{workers_dir}/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {snake_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(
        f"Worker '{snake_case_name}' generated at '{worker_path}' and added to {init_path}."
    )
