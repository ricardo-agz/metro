import json
import os

from fastapi import Form
from jinja2 import Environment, FileSystemLoader
from fastapi.templating import Jinja2Templates
from dataclasses import dataclass
import importlib
import pkgutil
import inspect

from starlette.responses import RedirectResponse

from pyrails.controllers import Controller, get, post, put, delete
from pyrails.exceptions import ValidationError
from pyrails import Request
from pyrails.config import config
from pyrails.models import BaseModel


TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates")


env = Environment(
    loader=FileSystemLoader(TEMPLATES_PATH),
)
TEMPLATE_GLOBALS = {
    # Basic built-ins
    'len': len,
    'min': min,
    'max': max,
    'sum': sum,
    'abs': abs,
    'round': round,
    'enumerate': enumerate,
    'range': range,
    'zip': zip,

    # Type conversion
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'set': set,

    # Other useful builtins
    'all': all,
    'any': any,
    'sorted': sorted,
    'filter': filter,
    'map': map
}
env.globals.update(TEMPLATE_GLOBALS)

templates = Jinja2Templates(directory=TEMPLATES_PATH)
templates.env = env


@dataclass
class ModelInfo:
    name: str
    model_class: type[BaseModel]
    fields: dict[str, any]
    display_fields: list[tuple[str, any]]


class AdminPanelController(Controller):
    def __init__(self):
        super().__init__()
        self._discovered_models = {}
        self._discover_models()

    def _discover_models(self):
        """Discover all models in the app/models directory that inherit from BaseModel"""
        models_dir = os.path.join(os.getcwd(), "app", "models")

        for module_info in pkgutil.iter_modules([models_dir]):
            module = importlib.import_module(f"app.models.{module_info.name}")

            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                        issubclass(obj, BaseModel) and
                        obj != BaseModel):

                    fields = {}
                    display_fields = []

                    for field_name, field in obj._fields.items():
                        if not field_name.startswith('_'):
                            fields[field_name] = field
                            display_fields.append((field_name, field))

                    self._discovered_models[name.lower()] = ModelInfo(
                        name=name,
                        model_class=obj,
                        fields=fields,
                        display_fields=display_fields
                    )

    async def _check_admin_auth(self, request: Request) -> bool:
        """Check if the user is authenticated as admin"""
        admin_token = request.cookies.get("admin_token")
        if not admin_token or admin_token != config.ADMIN_SECRET:
            return False
        return True

    @get(f'{config.ADMIN_ROUTE_PREFIX}')
    async def admin_index(self, request: Request):
        """Admin dashboard showing available models"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"/{config.ADMIN_ROUTE_PREFIX}/login")

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "models": self._discovered_models,
                "admin_route_prefix": config.ADMIN_ROUTE_PREFIX
            }
        )

    @get(f'{config.ADMIN_ROUTE_PREFIX}/login')
    async def admin_login_page(self, request: Request):
        """Show admin login page"""
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": None}
        )

    @post(f'{config.ADMIN_ROUTE_PREFIX}/login')
    async def admin_login(
        self,
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        """Handle admin login"""
        if (username == config.ADMIN_USERNAME and
                password == config.ADMIN_PASSWORD):
            response = RedirectResponse(
                f"{config.ADMIN_ROUTE_PREFIX}",
                status_code=302
            )
            response.set_cookie(
                "admin_token",
                config.ADMIN_SECRET,
                httponly=True,
                secure=True,
                samesite="lax"
            )
            return response

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid credentials"
            }
        )

    @delete(f'{config.ADMIN_ROUTE_PREFIX}/logout')
    async def admin_logout(self, request: Request):
        """Handle admin logout"""
        response = RedirectResponse(
            f"{config.ADMIN_ROUTE_PREFIX}/login",
            status_code=302
        )
        response.delete_cookie("admin_token")
        return response

    @get(f'{config.ADMIN_ROUTE_PREFIX}/{{model_name}}')
    async def list_model(self, request: Request, model_name: str):
        """List all records for a model with pagination and search"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"/{config.ADMIN_ROUTE_PREFIX}/login")

        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        # Get query parameters
        query_params = request.query_params
        page = int(query_params.get('page', 1))
        per_page = int(query_params.get('per_page', 10))
        query_str = query_params.get('query', '').strip()

        try:
            # Get total count and records
            query_dict = json.loads(query_str) if query_str else None

            if query_dict is not None:
                query = model_info.model_class.objects(**query_dict)
            else:
                # If there was a parsing error, show all records
                query = model_info.model_class.objects

            total_records = query.count()
            offset = (page - 1) * per_page
            records = query.skip(offset).limit(per_page)

            total_pages = (total_records + per_page - 1) // per_page
            has_next = page < total_pages

            return templates.TemplateResponse(
                "list.html",
                {
                    "request": request,
                    "model_info": model_info,
                    "records": records,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                    "total_records": total_records,
                    "has_next": has_next,
                    "query": query_str,
                    "error": "",
                    "admin_route_prefix": config.ADMIN_ROUTE_PREFIX
                }
            )
        except Exception as e:
            # Handle any other errors (database errors, etc)
            return templates.TemplateResponse(
                "list.html",
                {
                    "request": request,
                    "model_info": model_info,
                    "records": [],
                    "page": 1,
                    "per_page": per_page,
                    "total_pages": 0,
                    "total_records": 0,
                    "has_next": False,
                    "query": query_str,
                    "error": f"Error executing query: {str(e)}",
                    "admin_route_prefix": config.ADMIN_ROUTE_PREFIX
                }
            )

    @get(f'{config.ADMIN_ROUTE_PREFIX}/{{model_name}}/new')
    async def new_model(self, request: Request, model_name: str):
        """Show form to create a new record"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"/{config.ADMIN_ROUTE_PREFIX}/login")

        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        return templates.TemplateResponse(
            "new.html",
            {
                "request": request,
                "model_info": model_info,
                "admin_route_prefix": config.ADMIN_ROUTE_PREFIX
            }
        )

    @post(f'{config.ADMIN_ROUTE_PREFIX}/{{model_name}}')
    async def create_model(self, request: Request, model_name: str):
        """Create a new record"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"/{config.ADMIN_ROUTE_PREFIX}/login")

        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        form_data = await request.form()
        processed_data = {}
        file_fields = {}

        # First pass: collect all file fields and their values
        for field_name, value in form_data.items():
            # Strip the '[]' suffix if present
            clean_field_name = field_name.replace('[]', '')

            field = model_info.fields.get(clean_field_name)
            if field and field.__class__.__name__ in ['FileField', 'FileListField']:
                if clean_field_name not in file_fields:
                    file_fields[clean_field_name] = []
                if hasattr(value, 'file'):  # Check if it's a file object
                    file_fields[clean_field_name].append(value)

        # Process all form fields
        for field_name, field in model_info.fields.items():
            # Skip internal fields
            if field_name.startswith('_'):
                continue

            # Handle file fields
            if field.__class__.__name__ in ['FileField', 'FileListField']:
                if field_name in file_fields:
                    if field.__class__.__name__ == 'FileField':
                        # For single file field, take the last file
                        files = file_fields[field_name]
                        if files:
                            processed_data[field_name] = files[-1]
                    else:
                        # For file list field, use all files
                        processed_data[field_name] = file_fields[field_name]

            # Handle regular fields
            else:
                # Check both normal and array versions of the field name
                value = form_data.get(field_name) or form_data.get(f"{field_name}[]")

                if field.__class__.__name__ in ['DateTimeField', 'DateField']:
                    if value and value != '':
                        processed_data[field_name] = value
                elif value:
                    processed_data[field_name] = value

        record = model_info.model_class(**processed_data)
        record.save()

        return RedirectResponse(
            f"{config.ADMIN_ROUTE_PREFIX}/{model_name}",
            status_code=302
        )

    @get(f'{config.ADMIN_ROUTE_PREFIX}/{{model_name}}/{{id}}/edit')
    async def edit_model(self, request: Request, model_name: str, id: str):
        """Show form to edit an existing record"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"{config.ADMIN_ROUTE_PREFIX}/login")

        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        record = model_info.model_class.objects.get(id=id)

        return templates.TemplateResponse(
            "edit.html",
            {
                "request": request,
                "model_info": model_info,
                "record": record,
                "admin_route_prefix": config.ADMIN_ROUTE_PREFIX
            }
        )

    @put(f'{config.ADMIN_ROUTE_PREFIX}/{{model_name}}/{{id}}')
    async def update_model(self, request: Request, model_name: str, id: str):
        """Update an existing record"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"{config.ADMIN_ROUTE_PREFIX}/login")

        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        form_data = await request.form()
        record = model_info.model_class.objects.get(id=id)

        # Process all form fields
        for field_name, field in model_info.fields.items():
            if field_name.startswith('_'):
                continue

            if field.__class__.__name__ in ['FileField', 'FileListField']:
                # Handle file fields
                is_multiple = field.__class__.__name__ == 'FileListField'

                # Get any new file uploads - filter out empty uploads
                if is_multiple:
                    new_files = [
                        f for f in form_data.getlist(field_name)
                        if f and hasattr(f, 'file') and getattr(f, 'filename', '')
                    ]
                else:
                    new_file = form_data.get(field_name)
                    new_files = (
                        [new_file]
                        if new_file and hasattr(new_file, 'file') and getattr(new_file, 'filename', '')
                        else []
                    )

                # Get deleted files
                deleted_files = form_data.get(f"{field_name}_deleted", "").split(',')
                deleted_files = [f for f in deleted_files if f]

                if is_multiple:
                    # For FileListField, handle multiple files
                    current_files = getattr(record, field_name) or []

                    # Remove deleted files
                    current_files = [f for f in current_files if f.filename not in deleted_files]

                    # Add new files
                    if new_files:
                        current_files.extend(new_files)

                    setattr(record, field_name, current_files)
                else:
                    # For FileField, handle single file
                    if deleted_files:
                        setattr(record, field_name, None)
                    elif new_files:  # Only set if we have actual new files
                        setattr(record, field_name, new_files[0])

            elif field.__class__.__name__ == 'BooleanField':
                # Handle boolean fields
                value = field_name in form_data
                setattr(record, field_name, value)

            elif field.__class__.__name__ in ['DateTimeField', 'DateField']:
                # Handle date/time fields
                value = form_data.get(field_name)
                if value and value.strip():
                    setattr(record, field_name, value)

            else:
                # Handle regular fields
                value = form_data.get(field_name)
                if value is not None:
                    if field.__class__.__name__ == 'IntField':
                        try:
                            value = int(value) if value.strip() else None
                        except ValueError:
                            continue
                    setattr(record, field_name, value)

        record.save()

        return RedirectResponse(
            f"{config.ADMIN_ROUTE_PREFIX}/{model_name}",
            status_code=302
        )

    @delete(f'{config.ADMIN_ROUTE_PREFIX}/{{model_name}}/{{id}}')
    async def delete_model(self, request: Request, model_name: str, id: str):
        """Delete a record"""
        if not await self._check_admin_auth(request):
            return RedirectResponse(f"/{config.ADMIN_ROUTE_PREFIX}/login")

        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        record = model_info.model_class.objects.get(id=id)
        record.delete()

        return RedirectResponse(
            f"{config.ADMIN_ROUTE_PREFIX}/{model_name}",
            status_code=302
        )

