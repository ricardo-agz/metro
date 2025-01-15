import click


@click.group()
def generate():
    """Generator commands"""
    pass


def register_commands(cli):
    """
    Import and register all commands with the given 'cli' group.
    This keeps import logic in one place and avoids circular references.
    """
    from .scaffold import scaffold
    from .controller import controller
    from .model import model
    from .job import job
    from .worker import worker

    cli.add_command(scaffold, name="scaffold")
    cli.add_command(controller, name="controller")
    cli.add_command(model, name="model")
    cli.add_command(job, name="job")
    cli.add_command(worker, name="worker")


register_commands(generate)
