import click
import pkg_resources


def load_plugins():
    """Load Metro CLI plugins"""
    for entry_point in pkg_resources.iter_entry_points("metro.plugins"):
        try:
            entry_point.load()()
        except Exception as e:
            click.echo(f"Failed to load plugin {entry_point.name}: {e}", err=True)
