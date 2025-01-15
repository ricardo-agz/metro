def register_commands(cli):
    """
    Import and register all commands with the given 'cli' group.
    This keeps import logic in one place and avoids circular references.
    """
    from .project import new
    from .generate import generate
    from .db import db
    from .admin import admin
    from .run import run
    from ..plugins import load_plugins

    cli.add_command(new, name="new")
    cli.add_command(generate, name="generate")
    cli.add_command(generate, name="g")
    cli.add_command(db, name="db")
    cli.add_command(admin, name="admin")
    cli.add_command(run, name="run")

    load_plugins()
