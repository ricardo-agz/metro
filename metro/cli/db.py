import click
from ..db.mongodb import start_mongodb, stop_mongodb
from ..config import Config


@click.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option(
    "--env", default="development", help="Environment (development/test/production)"
)
@click.option(
    "--method",
    type=click.Choice(["d", "l", "m"]),
    default="l",
    help="Method to start the database (d=docker, l=local, m=manual)",
)
@click.option(
    "--docker",
    is_flag=True,
)
def up(env, method, docker):
    """Spin up a database for the specified environment."""
    config = Config(env)
    method_map = {"d": "docker", "l": "local", "m": "manual"}
    if docker:
        method = "d"

    full_method = method_map[method]
    start_mongodb(config, full_method)


@db.command()
@click.option(
    "--env", default="development", help="Environment (development/test/production)"
)
@click.option(
    "--method",
    type=click.Choice(["d", "l", "m"]),
    default="l",
    help="Method used to start the database (d=docker, l=local, m=manual)",
)
@click.option(
    "--docker",
    is_flag=True,
)
def down(env, method, docker):
    """Stop the database for the specified environment."""
    config = Config(env)  # Create config object
    method_map = {"d": "docker", "l": "local", "m": "manual"}
    if docker:
        method = "d"
    full_method = method_map[method]
    stop_mongodb(config.ENV, full_method)
