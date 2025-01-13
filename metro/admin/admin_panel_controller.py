import json
import os

from fastapi import Form
from dataclasses import dataclass
import importlib
import pkgutil
import inspect

from starlette.responses import RedirectResponse

from metro.admin.find_auth_class import find_auth_class
from metro.controllers import Controller, get, post, put, delete, before_request
from metro.exceptions import BadRequestError, NotFoundError
from metro.requests import Request
from metro.config import config
from metro.models import (
    BaseModel,
    FileListField,
    FileField,
    BooleanField,
    StringField,
    IntField,
    FloatField,
    DateTimeField,
    ListField,
    ObjectIdField,
    ReferenceField,
)
from metro.utils import (
    pluralize,
    to_snake_case,
    to_pascal_case,
    mongoengine_type_mapping,
    pydantic_type_mapping,
    is_valid_identifier,
)
from metro.admin.templates import templates


@dataclass
class ModelInfo:
    name: str
    model_class: type[BaseModel]
    fields: dict[str, any]
    display_fields: list[tuple[str, any]]
    required_fields: set[str]


class AdminPanelController(Controller):
    def __init__(self):
        super().__init__()
        self._discovered_models = {}
        self._discover_models()
        self.admin_auth_class = find_auth_class()

    @before_request
    async def check_admin_auth(self, request: Request):
        """Check if the user is authenticated as admin"""
        admin_token = request.cookies.get("admin_token")
        if not admin_token or not self.admin_auth_class.verify_auth_token(admin_token):
            return RedirectResponse(f"/auth{config.ADMIN_PANEL_ROUTE_PREFIX}/login")

    def _discover_models(self):
        """Discover all models in the app/models directory that inherit from BaseModel"""
        models_dir = os.path.join(
            os.getcwd(), config.MODELS_DIR.lstrip(".").lstrip("/").rstrip("/")
        )
        models_path = config.MODELS_DIR.replace("/", ".").lstrip(".")

        for module_info in pkgutil.iter_modules([models_dir]):
            module = importlib.import_module(f"{models_path}.{module_info.name}")

            for name, obj in inspect.getmembers(module):
                if not inspect.isclass(obj):
                    continue

                if not issubclass(obj, BaseModel) or obj == BaseModel:
                    continue

                # Check if the class was defined in the current module
                if obj.__module__ != f"{models_path}.{module_info.name}":
                    continue

                # Check for abstract in both meta and Meta
                is_abstract = False

                # Check lowercase meta dictionary
                if hasattr(obj, "_meta"):
                    is_abstract = getattr(obj._meta, "abstract", False)

                # Check uppercase Meta class
                if hasattr(obj, "Meta"):
                    is_abstract = is_abstract or getattr(obj.Meta, "abstract", False)

                if is_abstract:
                    continue

                fields = {}
                display_fields = []
                required_fields = set()

                for field_name, field in obj._fields.items():
                    if not field_name.startswith("_"):
                        fields[field_name] = field
                        display_fields.append((field_name, field))
                        # Check if field is required
                        if getattr(field, "required", False):
                            required_fields.add(field_name)

                self._discovered_models[name.lower()] = ModelInfo(
                    name=name,
                    model_class=obj,
                    fields=fields,
                    display_fields=display_fields,
                    required_fields=required_fields,
                )

    @get(f"{config.ADMIN_PANEL_ROUTE_PREFIX}")
    async def admin_index(self, request: Request):
        """Admin dashboard showing available models"""
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "models": self._discovered_models,
                "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
            },
        )

    @get(f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{{model_name}}")
    async def list_model(self, request: Request, model_name: str):
        """List all records for a model with pagination and search"""
        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise NotFoundError(f"Model {model_name} not found")

        # Get query parameters
        query_params = request.query_params
        page = int(query_params.get("page", 1))
        per_page = int(query_params.get("per_page", 10))
        query_str = query_params.get("query", "").strip()

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
                    "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
                },
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
                    "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
                },
            )

    @get(f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{{model_name}}/new")
    async def new_model(self, request: Request, model_name: str):
        """Show form to create a new record"""
        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise ValidationError(f"Model {model_name} not found")

        return templates.TemplateResponse(
            "new.html",
            {
                "request": request,
                "model_info": model_info,
                "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
            },
        )

    @post(f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{{model_name}}")
    async def create_model(self, request: Request, model_name: str):
        """Create a new record"""
        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise NotFoundError(f"Model {model_name} not found")

        form_data = await request.form()
        processed_data = {}
        file_fields = {}

        try:
            # First pass: collect all file fields and their values
            for field_name, field in model_info.fields.items():
                if isinstance(field, FileListField):
                    # Get all files for this field using getlist
                    files = form_data.getlist(f"{field_name}[]")
                    valid_files = [
                        f
                        for f in files
                        if hasattr(f, "file") and getattr(f, "filename", "")
                    ]
                    if valid_files:
                        file_fields[field_name] = valid_files
                elif isinstance(field, FileField):
                    file = form_data.get(field_name)
                    if hasattr(file, "file") and getattr(file, "filename", ""):
                        file_fields[field_name] = file

            for field_name, field in model_info.fields.items():
                if field_name.startswith("_"):
                    continue

                if isinstance(field, (FileField, FileListField)):
                    if field_name in file_fields:
                        processed_data[field_name] = file_fields[field_name]
                    continue

                if isinstance(field, BooleanField):
                    processed_data[field_name] = field_name in form_data
                    continue

                # Get raw value
                value = form_data.get(field_name)
                if value is None:
                    continue

                # Strip whitespace for non-string fields
                if not isinstance(field, StringField):
                    value = value.strip()
                    if not value:
                        continue

                # Type conversion
                if isinstance(field, (IntField, FloatField)):
                    try:
                        value = (
                            int(value) if isinstance(field, IntField) else float(value)
                        )
                    except (ValueError, TypeError):
                        raise BadRequestError(
                            f"Invalid {field.__class__.__name__} value for {field_name}"
                        )

                elif isinstance(field, ListField):
                    value = form_data.get(field_name)
                    if value:
                        # Split comma-separated values and process based on field type
                        values = [v.strip() for v in value.split(",") if v.strip()]

                        if isinstance(field.field, IntField):
                            values = [int(v) for v in values]
                        elif isinstance(field.field, FloatField):
                            values = [float(v) for v in values]
                        elif isinstance(field.field, (ObjectIdField, ReferenceField)):
                            document_type = field.field.document_type
                            values = [document_type.objects.get(id=v) for v in values]

                        processed_data[field_name] = values

                # Handle date/time fields
                elif isinstance(field, DateTimeField):
                    if not value:
                        continue

                processed_data[field_name] = value

            record = model_info.model_class(**processed_data)
            record.save()

            return RedirectResponse(
                f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{model_name}", status_code=302
            )

        except Exception as e:
            # Return to the form with error message
            error_message = str(e)
            if "ValidationError" in error_message:
                # Clean up MongoDB validation error message
                error_message = error_message.split("ValidationError:", 1)[-1].strip()

            return templates.TemplateResponse(
                "new.html",
                {
                    "request": request,
                    "model_info": model_info,
                    "error": error_message,
                    "form_data": processed_data,  # Pass back the processed data
                    "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
                },
                status_code=400,
            )

    @get(f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{{model_name}}/{{id}}/edit")
    async def edit_model(self, request: Request, model_name: str, id: str):
        """Show form to edit an existing record"""
        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise BadRequestError(f"Model {model_name} not found")

        record = model_info.model_class.objects.get(id=id)

        return templates.TemplateResponse(
            "edit.html",
            {
                "request": request,
                "model_info": model_info,
                "record": record,
                "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
            },
        )

    @put(f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{{model_name}}/{{id}}")
    async def update_model(self, request: Request, model_name: str, id: str):
        """Update an existing record"""
        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise BadRequestError(f"Model {model_name} not found")

        record = model_info.model_class.objects.get(id=id)
        if not record:
            raise NotFoundError(f"Record with id {id} not found")

        try:
            form_data = await request.form()

            for field_name, field in model_info.fields.items():
                if field_name.startswith("_"):
                    continue

                if isinstance(field, FileListField):
                    # Get multi-file uploads with [] suffix
                    files = form_data.getlist(f"{field_name}[]")
                    valid_files = [
                        f
                        for f in files
                        if hasattr(f, "file") and getattr(f, "filename", "")
                    ]

                    # Get deleted files
                    deleted_files = form_data.get(f"{field_name}_deleted", "").split(
                        ","
                    )
                    deleted_files = [f for f in deleted_files if f]

                    # Get the FileListProxy
                    file_list = getattr(record, field_name)

                    # Remove deleted files
                    if deleted_files:
                        file_list[:] = [
                            f
                            for f in file_list
                            if f and f.filename not in deleted_files
                        ]

                    # Add new files
                    if valid_files:
                        file_list.extend(valid_files)

                elif isinstance(field, FileField):
                    # Single file handling
                    file = form_data.get(field_name)
                    deleted_files = form_data.get(f"{field_name}_deleted", "").split(
                        ","
                    )
                    deleted_files = [f for f in deleted_files if f]

                    if deleted_files:
                        setattr(record, field_name, None)
                    elif (
                        file and hasattr(file, "file") and getattr(file, "filename", "")
                    ):
                        setattr(record, field_name, file)

                elif isinstance(field, BooleanField):
                    setattr(record, field_name, field_name in form_data)

                elif isinstance(field, ListField):
                    value = form_data.get(field_name)
                    if value is not None:
                        # Split comma-separated values and process based on field type
                        values = [v.strip() for v in value.split(",") if v.strip()]

                        if isinstance(field.field, IntField):
                            values = [int(v) for v in values]
                        elif isinstance(field.field, FloatField):
                            values = [float(v) for v in values]
                        elif isinstance(field.field, (ObjectIdField, ReferenceField)):
                            document_type = field.field.document_type
                            values = [document_type.objects.get(id=v) for v in values]

                        setattr(record, field_name, values)

                else:
                    value = form_data.get(field_name)
                    if value is None:
                        continue

                    if isinstance(field, DateTimeField):
                        if value and value.strip():
                            setattr(record, field_name, value)
                    elif isinstance(field, IntField):
                        try:
                            value = int(value.strip()) if value.strip() else None
                            if value is not None:
                                setattr(record, field_name, value)
                        except ValueError:
                            continue
                    elif isinstance(field, FloatField):
                        try:
                            value = float(value.strip()) if value.strip() else None
                            if value is not None:
                                setattr(record, field_name, value)
                        except ValueError:
                            continue
                    else:
                        # String and other fields
                        setattr(record, field_name, value)

            record.save()
            return RedirectResponse(
                f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{model_name}", status_code=302
            )

        except Exception as e:
            error_message = str(e)
            if "ValidationError" in error_message:
                error_message = error_message.split("ValidationError:", 1)[-1].strip()

            return templates.TemplateResponse(
                "edit.html",
                {
                    "request": request,
                    "model_info": model_info,
                    "record": record,
                    "error": error_message,
                    "admin_route_prefix": config.ADMIN_PANEL_ROUTE_PREFIX,
                },
                status_code=400,
            )

    @delete(f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{{model_name}}/{{id}}")
    async def delete_model(self, request: Request, model_name: str, id: str):
        """Delete a record"""
        model_info = self._discovered_models.get(model_name.lower())
        if not model_info:
            raise BadRequestError(f"Model {model_name} not found")

        record = model_info.model_class.objects.get(id=id)
        record.delete()

        return RedirectResponse(
            f"{config.ADMIN_PANEL_ROUTE_PREFIX}/{model_name}", status_code=302
        )
