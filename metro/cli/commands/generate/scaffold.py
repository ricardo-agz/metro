import click

from metro.cli.commands.generate.controller import generate_controller
from metro.cli.commands.generate.model import generate_model


@click.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option(
    "--actions",
    "-a",
    multiple=True,
    help="Additional methods in format 'http_method:path (query: params) (body: params) (desc: description)'",
)
@click.option(
    "--exclude-crud",
    "-x",
    multiple=True,
    type=click.Choice(["index", "show", "create", "update", "delete"]),
    help="CRUD methods to exclude from scaffold",
)
@click.option(
    "--model-inherits",
    default=None,
    help="Base class(es) to inherit from, e.g. UserBase or 'UserBase,SomeMixin'",
)
@click.option(
    "--controller-inherits",
    default=None,
    help="Base controller class(es), e.g. AdminController or 'AdminController, SomeMixin'",
)
@click.option(
    "--before-request",
    "--before",
    multiple=True,
    help="Lifecycle hooks to run before each request.",
)
@click.option(
    "--after-request",
    "--after",
    multiple=True,
    help="Lifecycle hooks to run after each request.",
)
@click.option(
    "--index",
    multiple=True,
    help="Add compound index. Format: 'field1,field2[unique,sparse,desc]'",
)
def scaffold(
    name,
    fields,
    actions,
    exclude_crud,
    model_inherits,
    controller_inherits,
    before_request,
    after_request,
    index,
):
    """
    Generate a model and controller with CRUD functionality.

    Actions can be specified in multiple formats:

    Simple format:
        get:search

    With path parameters:
        get:detail/{id}

    With query parameters:
        get:search (query: name:str,age:int)

    With body parameters:
        put:update/{id} (body: name:str,email:str)

    With description:
        get:search (query: term:str) (desc: Search for items)

    Example:
        metro generate scaffold User name:str email:str \
            -a "get:search (query: term:str) (desc: Search users)" \
            -a "put:verify/{token}(str) (desc: Verify user email)" \
            -a "post:password/{id}(str) (body: old:str,new:str) (desc: Change password)"
    """

    output = generate_controller(
        resource_name=name,
        actions=actions,
        exclude_crud=exclude_crud,
        controller_inherits=controller_inherits,
        before_hooks=before_request,
        after_hooks=after_request,
        resource_fields=fields,
        is_scaffold=True,
        model_inherits=model_inherits,
    )
    click.echo(
        click.style(
            f"Scaffold controller '{output.controller_name}' generated at '{output.controller_path}' and added to {output.init_path}.",
            fg="green",
        )
    )

    output = generate_model(
        model_name=name, fields=fields, model_inherits=model_inherits, index=index
    )
    click.echo(
        click.style(
            f"Scaffold model '{output.pascal_case_name}' generated at '{output.model_path}' and added to {output.init_path}.",
            fg="green",
        )
    )
