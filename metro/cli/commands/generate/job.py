import os
import click

from metro.templates import job_template
from metro.utils import (
    to_snake_case,
    to_pascal_case,
)
from metro.utils.file_operations import insert_line_without_duplicating
from metro.config import config


jobs_dir = config.JOBS_DIR.lstrip("/").lstrip(".").lstrip("/").rstrip("/")


@click.command()
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
        perform_method=(
            perform_batch_str if (batch_size or batch_interval) else perform_str
        ),
    )
    job_path = f"{jobs_dir}/{snake_case_name}.py"
    os.makedirs(os.path.dirname(job_path), exist_ok=True)
    with open(job_path, "w") as f:
        f.write(content)

    # Update jobs __init__.py
    init_path = f"{jobs_dir}/__init__.py"
    line_to_insert = f"from .{snake_case_name} import {pascal_case_name}"
    insert_line_without_duplicating(init_path, line_to_insert)

    click.echo(
        f"Job '{pascal_case_name}' generated at '{job_path}' and added to {init_path}."
    )
