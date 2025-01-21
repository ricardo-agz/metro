import click

from metro.admin.find_auth_class import find_auth_class
from metro.config import config
from metro.db import db_manager


@click.group()
def admin():
    """Generate code."""
    pass


@admin.command()
@click.option("--all-fields", is_flag=True, help="Prompt for all fields.")
def createsuperuser(all_fields: bool = False):
    """Seeds a superuser."""
    admin_auth_class = find_auth_class()
    if not admin_auth_class:
        click.echo("Admin auth class not found. Please create a user model.")
        return

    fields = {}
    for field in admin_auth_class._fields.keys():
        if (
            field in ["id", "created_at", "updated_at", "deleted_at", "last_login"]
            and not all_fields
        ):
            continue

        if field in ["is_staff", "is_superuser"] and not all_fields:
            fields[field] = True
            continue

        field_type = admin_auth_class._fields[field].__class__.__name__
        value = click.prompt(field, default="", show_default=False)

        # Skip empty values
        if value == "":
            if field_type == "ListField":
                fields[field] = []
            continue

        if field_type == "BooleanField":
            value = value.lower() in ["true", "1", "yes"]
        elif field_type == "IntField":
            value = int(value)
        elif field_type == "FloatField":
            value = float(value)

        fields[field] = value

    for alias, db_config in config.DATABASES.items():
        is_default = alias == "default"
        db_manager.connect_db(
            alias=alias,
            db_name=db_config["NAME"],
            db_url=db_config["URL"],
            is_default=is_default,
            ssl_reqs=db_config["SSL"],
            **db_config.get("KWARGS", {})
        )

    admin_auth_class(**fields).save()

    click.echo("Superuser created successfully.")
