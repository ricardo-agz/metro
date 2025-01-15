import os
import click
from pydantic import BaseModel

from metro.cli.utils import (
    parse_hook,
    parse_method_spec,
    get_default_action_name,
    process_controller_inheritance,
    process_fields,
    clean_up_file_whitespace,
)
from metro.templates import controller_template
from metro.utils import (
    to_snake_case,
    to_pascal_case,
    pluralize,
)
from metro.utils.file_operations import insert_line_without_duplicating
from metro.config import config


controllers_dir = config.CONTROLLERS_DIR.lstrip(".").lstrip("/").rstrip("/")


class ControllerActionMethod(BaseModel):
    method_code: str
    pydantic_model: str | None


class GenerateControllerOutput(BaseModel):
    controller_path: str
    init_path: str
    controller_name: str


def generate_imports(
    actions: tuple[str, ...] | None,
    controller_inherits: str | None,
    include_pydantic: bool = False,
    associated_models: list[str] = None,
) -> str:
    additional_imports = ""

    has_body_params = any("body:" in action for action in actions)
    if has_body_params or include_pydantic:
        additional_imports += "\nfrom pydantic import BaseModel\n"

    (_, controller_imports) = (
        process_controller_inheritance(controller_inherits)
        if controller_inherits
        else (None, "")
    )
    additional_imports += "\n" + "\n".join(controller_imports)

    if associated_models:
        for model in associated_models:
            additional_imports += f"\nfrom app.models.{to_snake_case(model)} import {to_pascal_case(model)}\n"

    return additional_imports


def generate_lifecycle_hooks(
    before_hooks: tuple[str, ...],
    after_hooks: tuple[str, ...],
) -> list[str]:
    """Generate lifecycle hook methods."""
    hooks_code = []

    for hook_spec in before_hooks:
        hook_name, hook_desc = parse_hook(hook_spec)
        hooks_code.append(
            f"    @before_request\n"
            f"    async def {hook_name}(self, request: Request):\n"
            f'        """{hook_desc}"""\n'
            f"        # TODO\n"
            f"        pass\n"
        )

    for hook_spec in after_hooks:
        hook_name, hook_desc = parse_hook(hook_spec)
        hooks_code.append(
            f"    @after_request\n"
            f"    async def {hook_name}(self, request: Request):\n"
            f'        """{hook_desc}"""\n'
            f"        # TODO\n"
            f"        pass\n"
        )

    return hooks_code


def generate_method_docstring(
    description: str,
    path_params: dict,
    query_params: dict,
    pydantic_class_name: str = None,
) -> str:
    docstring_lines = [
        f'        """{description}\n\n',
        "        Args:\n",
        "            request (Request): The request object\n",
    ]
    for param_name, param_type in path_params.items():
        docstring_lines.append(
            f"            {param_name} ({param_type}): Path parameter\n"
        )
    for param_name, param_type in query_params.items():
        docstring_lines.append(
            f"            {param_name} ({param_type}): Query parameter\n"
        )
    if pydantic_class_name:
        docstring_lines.append(
            f"            data ({pydantic_class_name}): Request body\n"
        )
    docstring_lines.append('        """\n')
    return "".join(docstring_lines)


def generate_crud_methods(
    url_prefix: str,
    resource_name: str,
    pydantic_code: str,
    exclude_crud: tuple[str, ...] = (),
) -> list[ControllerActionMethod]:
    controller_actions = []

    resource_name_pascal = to_pascal_case(resource_name)
    resource_name_plural_pascal = to_pascal_case(pluralize(resource_name))

    if "index" not in exclude_crud:
        controller_actions.append(
            ControllerActionMethod(
                method_code=(
                    f"    @get('/{url_prefix}')\n"
                    f"    async def index(self, request: Request):\n"
                    f'        """List all {resource_name_plural_pascal}.\n\n'
                    f"        Returns:\n"
                    f"            list: List of {resource_name_pascal} objects\n"
                    f'        """\n'
                    f"        items = {resource_name_pascal}.find()\n"
                    f"        return [item.to_dict() for item in items]\n\n"
                ),
                pydantic_model=None,
            )
        )

    if "show" not in exclude_crud:
        controller_actions.append(
            ControllerActionMethod(
                method_code=(
                    f"    @get('/{url_prefix}/{{id}}')\n"
                    f"    async def show(self, request: Request, id: str):\n"
                    f'        """Get a specific {resource_name_pascal} by ID.\n\n'
                    f"        Args:\n"
                    f"            request (Request): The request object\n"
                    f"            id (str): The {resource_name_pascal} ID\n\n"
                    f"        Returns:\n"
                    f"            dict: The {resource_name_pascal} object\n\n"
                    f"        Raises:\n"
                    f"            NotFoundError: If {resource_name_pascal} is not found\n"
                    f'        """\n'
                    f"        item = {resource_name_pascal}.find_by_id(id=id)\n"
                    f"        if item:\n"
                    f"            return item.to_dict()\n"
                    f"        raise NotFoundError('{resource_name_pascal} not found')\n\n"
                ),
                pydantic_model=None,
            )
        )

    if "create" not in exclude_crud:
        pydantic_model = (
            f"class {resource_name_pascal}Create(BaseModel):\n" f"{pydantic_code}\n"
        )

        controller_actions.append(
            ControllerActionMethod(
                method_code=(
                    f"    @post('/{url_prefix}')\n"
                    f"    async def create(self, request: Request, data: {resource_name_pascal}Create):\n"
                    f'        """Create a new {resource_name_pascal}.\n\n'
                    f"        Args:\n"
                    f"            request (Request): The request object\n"
                    f"            data ({resource_name_pascal}Create): The creation data\n\n"
                    f"        Returns:\n"
                    f"            dict: The created {resource_name_pascal} object\n"
                    f'        """\n'
                    f"        item = {resource_name_pascal}(**data.dict()).save()\n"
                    f"        return item.to_dict()\n\n"
                ),
                pydantic_model=pydantic_model,
            )
        )

    if "update" not in exclude_crud:
        pydantic_model = (
            f"class {resource_name_pascal}Update(BaseModel):\n" f"{pydantic_code}\n"
        )

        controller_actions.append(
            ControllerActionMethod(
                method_code=(
                    f"    @put('/{url_prefix}/{{id}}')\n"
                    f"    async def update(self, request: Request, id: str, data: {resource_name_pascal}Update):\n"
                    f'        """Update a specific {resource_name_pascal}.\n\n'
                    f"        Args:\n"
                    f"            request (Request): The request object\n"
                    f"            id (str): The {resource_name_pascal} ID\n"
                    f"            data ({resource_name_pascal}Update): The update data\n\n"
                    f"        Returns:\n"
                    f"            dict: The updated {resource_name_pascal} object\n\n"
                    f"        Raises:\n"
                    f"            NotFoundError: If {resource_name_pascal} is not found\n"
                    f'        """\n'
                    f"        item = {resource_name_pascal}.find_by_id_and_update(id=id, **data.dict(exclude_unset=True))\n"
                    f"        if item:\n"
                    f"            return item.to_dict()\n"
                    f"        raise NotFoundError('{resource_name_pascal} not found')\n\n"
                ),
                pydantic_model=pydantic_model,
            )
        )

    if "delete" not in exclude_crud:
        controller_actions.append(
            ControllerActionMethod(
                method_code=(
                    f"    @delete('/{url_prefix}/{{id}}')\n"
                    f"    async def delete(self, request: Request, id: str):\n"
                    f'        """Delete a specific {resource_name_pascal}.\n\n'
                    f"        Args:\n"
                    f"            request (Request): The request object\n"
                    f"            id (str): The {resource_name_pascal} ID to delete\n\n"
                    f"        Returns:\n"
                    f"            dict: A success message\n\n"
                    f"        Raises:\n"
                    f"            NotFoundError: If {resource_name_pascal} is not found\n"
                    f'        """\n'
                    f"        item = {resource_name_pascal}.find_by_id_and_delete(id=id)\n"
                    f"        if item is None:\n"
                    f"            raise NotFoundError('{resource_name_pascal} not found')\n"
                    f"        return {{'detail': '{resource_name_pascal} deleted'}}\n\n"
                ),
                pydantic_model=None,
            )
        )

    return controller_actions


def generate_additional_methods(
    actions: tuple[str, ...],
    url_prefix: str,
    pydantic_class_prefix: str,
) -> list[ControllerActionMethod]:
    """Generate additional controller methods from action specifications."""
    controller_actions = []
    taken_action_names = set()

    for action in actions:
        # Use the robust parse_method_spec function here!
        try:
            spec = parse_method_spec(action)
        except Exception as e:
            click.echo(f"Error parsing method specification: {str(e)}")
            continue

        http_method = spec["http_method"]  # e.g. get, put, post, ...
        final_path = f"/{url_prefix}/{spec['path'].lstrip('/')}"
        path_params = spec["path_params"]
        query_params = spec["query_params"]
        body_params = spec["body_params"]
        action_name = spec["action_name"]
        description = spec["description"]

        if action_name in taken_action_names:
            action_name = f"{http_method.lower()}_{action_name}"

        taken_action_names.add(action_name)

        if http_method not in ["get", "post", "put", "delete"]:
            click.echo(
                click.style(
                    f"Invalid HTTP method '{http_method}' provided for action '{action_name}'.",
                    fg="red",
                )
            )
            continue

        # Build method signature
        method_params = ["self", "request: Request"]
        for param_name, param_type in path_params.items():
            method_params.append(f"{param_name}: {param_type}")
        for param_name, param_type in query_params.items():
            method_params.append(f"{param_name}: {param_type}")

        # If body params exist, define a pydantic class for them
        pydantic_model = None
        pydantic_model_name = None
        if body_params:
            pydantic_model_name = (
                f"{pydantic_class_prefix}{to_pascal_case(action_name)}Body"
            )
            # Build a small Pydantic model
            model_fields = []
            for param_name, param_type in body_params.items():
                model_fields.append(f"    {param_name}: {param_type}")
            pydantic_model = (
                f"class {pydantic_model_name}(BaseModel):\n"
                + "\n".join(model_fields)
                + "\n"
            )
            method_params.append(f"data: {pydantic_model_name}")

        # Build docstring
        docstring = generate_method_docstring(
            description=description,
            path_params=path_params,
            query_params=query_params,
            pydantic_class_name=pydantic_model_name,
        )

        controller_actions.append(
            ControllerActionMethod(
                method_code=(
                    f"    @{http_method}('{final_path}')\n"
                    f"    async def {action_name}({', '.join(method_params)}):\n"
                    f"{docstring}"
                    f"        # TODO: Implement the {action_name} logic\n"
                    f"        pass\n\n"
                ),
                pydantic_model=pydantic_model,
            )
        )

    return controller_actions


def generate_controller(
    resource_name: str,
    actions: tuple[str, ...] = (),
    exclude_crud: tuple[str, ...] = (),
    controller_inherits: str | None = None,
    before_hooks: tuple[str, ...] = (),
    after_hooks: tuple[str, ...] = (),
    resource_fields: tuple[str, ...] = None,
    is_scaffold: bool = False,
) -> GenerateControllerOutput:
    """Generate a controller file and update __init__.py"""

    # Process pluralized names
    controller_name = pluralize(resource_name) if is_scaffold else resource_name
    controller_name_pascal = to_pascal_case(controller_name)
    controller_name_snake = to_snake_case(controller_name)
    url_prefix = controller_name_snake.replace("_", "-")

    additional_imports = generate_imports(
        actions=actions,
        controller_inherits=controller_inherits,
        include_pydantic=is_scaffold,
        associated_models=[resource_name] if is_scaffold else None,
    )

    # Process inheritance
    base_controllers, _ = process_controller_inheritance(controller_inherits)

    hooks_code_list = generate_lifecycle_hooks(before_hooks, after_hooks)
    hooks_code = "\n".join(hooks_code_list) if hooks_code_list else ""

    controller_actions = []
    if is_scaffold:
        _, crud_pydantic_code = process_fields(resource_fields)

        crud_methods = generate_crud_methods(
            url_prefix=url_prefix,
            resource_name=resource_name,
            pydantic_code=crud_pydantic_code,
            exclude_crud=exclude_crud,
        )
        controller_actions.extend(crud_methods)

    additional_methods = generate_additional_methods(
        actions=actions,
        url_prefix=url_prefix,
        pydantic_class_prefix=controller_name_pascal,
    )
    controller_actions.extend(additional_methods)

    controller_actions_code = "\n".join([a.method_code for a in controller_actions])

    controller_code = hooks_code + controller_actions_code
    if not controller_code.strip():
        controller_code = "    pass\n"

    all_pydantic_models = "\n".join(
        [a.pydantic_model for a in controller_actions if a.pydantic_model]
    )
    pydantic_models_code = (
        "\n" + all_pydantic_models + "\n\n" if all_pydantic_models.strip() else ""
    )

    # Generate the controller file
    controller_content = controller_template.format(
        controller_name=f"{controller_name_pascal}Controller",
        pydantic_models=pydantic_models_code,
        controller_code=controller_code,
        additional_imports=additional_imports,
        base_controllers=base_controllers,
    )

    controller_content = clean_up_file_whitespace(controller_content)

    controller_path = f"{controllers_dir}/{controller_name_snake}_controller.py"
    os.makedirs(os.path.dirname(controller_path), exist_ok=True)
    with open(controller_path, "w") as f:
        f.write(controller_content)

    # Update controllers/__init__.py
    init_path = f"{controllers_dir}/__init__.py"
    line_to_insert = f"from .{controller_name_snake}_controller import {controller_name_pascal}Controller"
    insert_line_without_duplicating(init_path, line_to_insert)

    return GenerateControllerOutput(
        controller_path=controller_path,
        init_path=init_path,
        controller_name=f"{controller_name_pascal}Controller",
    )


@click.command()
@click.argument("controller_name")
@click.argument(
    "direct_actions", nargs=-1, required=False
)  # Optional positional arguments
@click.option(
    "--actions",
    "-a",
    multiple=True,
    help="Additional methods in format 'http_method:path (query: params) (body: params) (desc: description)'",
)
@click.option(
    "--controller-inherits",
    default=None,
    help="Base controller class(es), e.g. AdminController or 'AdminController,SomeMixin'",
)
@click.option(
    "--before",
    multiple=True,
    help="Lifecycle hooks to run before each request. Repeat for multiple.",
)
@click.option(
    "--after",
    multiple=True,
    help="Lifecycle hooks to run after each request. Repeat for multiple.",
)
def controller(
    controller_name, direct_actions, actions, controller_inherits, before, after
):
    """
    Generate a new controller.

    Actions can be specified in multiple formats:

    Simple format:
        get:posts

    With path parameters:
        get:posts/{id}

    With query parameters:
        get:posts/{id} (query: page:int,limit:int)

    With body parameters:
        put:users/{id} (body: name:str,email:str)

    With description:
        get:posts/{id} (query: page:int) (desc: Get post details)

    Controller inheritance can be specified using --controller-inherits:
        --controller-inherits AdminController
        --controller-inherits "AdminController,AuthMixin"

    Lifecycle hooks can be added using --before and --after:
        --before check_admin
        --before "check_permissions:Verify user has required permissions"
        --after log_request
        --after "update_metrics:Update API usage metrics"

    Examples:

    1. Basic controller with actions:
        metro generate controller Auth post:login post:register

    2. Controller with path, query and body parameters:
        metro generate controller User \
            "get:profile" \
            "get:posts/{id} (query: page:int,limit:int) (desc: Get user posts)" \
            "put:users/{id} (body: name:str,email:str) (desc: Update user)"

    3. Admin controller with inheritance and hooks:
        metro generate controller UserManagement \
            "get:users (query: page:int,status:str)" \
            "post:users/bulk-update (body: ids:list,status:str)" \
            --controller-inherits AdminController \
            --before "check_admin:Ensure user is admin" \
            --after "log_admin_action:Log all admin activities"

    4. Controller with multiple inheritance and hooks:
        metro generate controller ProductManagement \
            "post:products (body: name:str,price:float,category:str)" \
            "put:products/{id} (body: name:str,price:float)" \
            --controller-inherits "AdminController,AuditableMixin" \
            --before "check_admin:Verify admin access" \
            --before "validate_product:Validate product data" \
            --after "notify_updates:Send notification on changes" \
            --after "update_cache:Refresh product cache"
    """
    all_actions = tuple(direct_actions) + tuple(actions)

    output = generate_controller(
        resource_name=controller_name,
        actions=all_actions,
        controller_inherits=controller_inherits,
        before_hooks=before,
        after_hooks=after,
    )

    click.echo(
        click.style(
            f"Controller '{output.controller_name}' generated at '{output.controller_path}' and added to {output.init_path}.",
            fg="green",
        )
    )
