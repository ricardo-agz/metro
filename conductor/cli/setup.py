# conductor/cli/setup.py
import click
import inquirer

from conductor.key_storage import key_storage
from conductor.constants import PROVIDERS


def prompt_provider(providers: list[str] = None):
    """Interactive provider selection with arrow keys"""
    providers = providers or PROVIDERS

    questions = [
        inquirer.List(
            "provider",
            message="Select API provider",
            choices=providers,
        ),
    ]
    answers = inquirer.prompt(questions)
    return answers["provider"]


@click.group()
def setup():
    """Configure API keys and settings"""
    pass


@setup.command()
@click.option(
    "--provider",
    type=click.Choice(PROVIDERS),
    help="API provider to configure",
)
def add_key(provider):
    """Add or update an API key"""
    if not provider:
        provider = prompt_provider()

    key = click.prompt(f"Enter your {provider} API key", hide_input=True)
    key_storage.set_key(provider, key)
    click.echo(f"Successfully saved {provider} API key!")


@setup.command()
@click.option(
    "--provider",
    type=click.Choice(PROVIDERS),
    help="API provider to configure",
)
def remove_key(provider):
    """Remove an API key"""
    configured_providers = [p for p in PROVIDERS if key_storage.get_key(p)]
    print("keys", [key_storage.get_key(p) for p in PROVIDERS])
    print("configured_providers", configured_providers)

    if not provider:
        provider = prompt_provider(providers=configured_providers)

    key_storage.remove_key(provider)
    click.echo(f"Removed {provider} API key if it existed")


@setup.command(name="list")
def list_keys():
    """List configured API keys"""
    click.echo("Configured API keys:")
    click.echo("-" * 40)
    for provider in ["openai", "anthropic"]:
        key = key_storage.get_key(provider)
        if key:
            masked_key = f"{key[:4]}...{key[-4:]}"
            click.echo(f"{provider}: {masked_key}")
        else:
            click.echo(f"{provider}: Not configured")
