import click
from .commands import register_commands


@click.group()
def cli():
    """Top-level Click group for Metro CLI."""
    pass


register_commands(cli)
