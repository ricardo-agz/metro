# conductor/cli/__init__.py
import os
import subprocess
import shlex
import sys
import threading
import time

import click
from conductor.cli.setup import setup
from conductor.generator.init_project.generator_commands import handle_feedback_loop
from conductor.load_api_keys import load_api_keys
from conductor.generator.init_project import (
    init_project_design_draft,
    init_project_generator_commands,
)
from conductor.utils import Spinner


def run_command(command: str) -> tuple[bool, str]:
    """Execute a shell command and return success status and output"""
    try:
        # Use shlex.split() to properly handle quoted arguments
        args = shlex.split(command)
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def execute_commands(commands: list[str]) -> bool:
    """Execute a list of commands with visual feedback"""
    click.echo("\nExecuting commands:")

    for cmd in commands:
        spinner = Spinner(message=click.style(f"  {cmd}", fg="bright_blue"))
        spinner.start()
        success, output = run_command(cmd)
        spinner.stop()

        if not success:
            click.echo(
                click.style(
                    f"    Error running cmd: {cmd}\n\n{output}", fg="bright_red"
                )
            )
            return False

        click.echo(click.style(f"  ✓ {cmd}", fg="bright_green"))
    return True


@click.group()
def conductor():
    """AI-powered scaffolding for Metro applications"""
    pass


conductor.add_command(setup, name="setup")


@conductor.command()
@click.argument("directory")
@click.argument("description", required=False)
def init(directory: str, description: str = None):
    """Initialize a new component based on the provided description"""
    try:
        if description is None:
            description = directory
            directory = "."

        click.echo(
            click.style(f"⚙️ Generating scaffold based on: ", fg="bright_blue")
            + click.style(description, fg="bright_white")
        )

        # Load API keys
        load_api_keys()

        # Generate initial design draft
        spinner = Spinner(message="Generating design draft")
        spinner.start()
        design_draft = init_project_design_draft(description)
        spinner.stop()

        click.echo("\nGenerated Design Draft:")
        click.echo(click.style(design_draft, fg="bright_white"))

        # Generate initial commands
        spinner = Spinner(message="Generating scaffold commands")
        spinner.start()
        initial_commands = init_project_generator_commands(description, design_draft)
        spinner.stop()

        # Handle feedback loop
        final_commands = handle_feedback_loop(
            description, design_draft, initial_commands
        )

        run_command(f"metro new {directory}")
        if directory != ".":
            os.chdir(directory)

        # Execute commands
        if execute_commands(final_commands):
            click.echo(
                click.style("\n✨ Scaffold generation complete! ✨", fg="bright_green")
            )
        else:
            click.echo(click.style("\n❌ Scaffold generation failed", fg="bright_red"))
            raise click.Abort()

    except Exception as e:
        click.echo(click.style(f"\nError: {str(e)}", fg="bright_red"), err=True)
        raise click.Abort()


def register_commands():
    from metro.cli import cli

    cli.add_command(conductor)
