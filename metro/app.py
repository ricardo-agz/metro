import importlib
import inspect
import os
import pkgutil
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.routing import ASGIApp
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers
from typing import Callable

from metro.controllers import Controller
from metro.config import Config, config as app_config
from metro.exceptions import exception_handlers
from metro.db.connect_db import db_manager
from metro.jobs.worker import MetroWorker
from metro.admin import AdminPanelController, AdminPanelAuthController
from metro.logger import logger


class MethodOverrideMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, override_method_header: str = "X-HTTP-Method-Override"
    ):
        super().__init__(app)
        self.override_method_header = override_method_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check for method override if we have a _method field in the form
        # or the override header is present
        if request.headers.get(self.override_method_header) or (
            request.method == "POST"
            and any(
                h[0].decode() == "content-type" and b"form" in h[1]
                for h in request.scope["headers"]
            )
        ):
            # Create a buffer for the body
            body = await request.body()

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            # Update request to use our modified receive
            request.scope["receive"] = receive

            # Try to get method from headers first
            method = request.headers.get(self.override_method_header)

            # If no header, try to get from form data
            if not method and request.method == "POST":
                content_type = request.headers.get("content-type", "")

                if "form" in content_type:
                    form = await request.form()
                    method = form.get("_method", "").upper()

                    # Reset the request body after reading form
                    async def receive():
                        return {
                            "type": "http.request",
                            "body": body,
                            "more_body": False,
                        }

                    request.scope["receive"] = receive

            if method and method in ["PUT", "PATCH", "DELETE"]:
                request.scope["method"] = method

                # Update headers
                headers = dict(request.headers)
                headers[self.override_method_header.lower()] = method
                request.scope["headers"] = Headers(headers).raw

        response = await call_next(request)
        return response


class DirectoryNotFoundError(Exception):
    """Raised when the controllers directory cannot be found."""

    pass


def discover_controllers(
    controllers_dir: str = "app/controllers",
) -> list[tuple[type[Controller], str]]:
    """
    Discovers all controller classes in the specified directory and their URL prefixes.
    """
    controllers = []

    # First verify the directory exists
    abs_path = Path(controllers_dir).resolve()
    if not abs_path.exists():
        raise DirectoryNotFoundError(
            f"Controllers directory not found: {controllers_dir}"
        )

    # Convert to proper Python package path relative to current working directory
    try:
        # Convert controllers_dir to a module path
        module_parts = controllers_dir.split("/")
        base_module = ".".join(module_parts)

        # Import the base controllers package
        controllers_package = importlib.import_module(base_module)
        package_path = Path(controllers_package.__file__).parent

        def get_url_prefix(module_name: str) -> str:
            """Convert module path to URL prefix"""
            # Remove base module prefix to get relative path
            if module_name.startswith(base_module):
                rel_path = module_name[len(base_module) :].lstrip(".")
            else:
                rel_path = module_name

            if not rel_path:
                return ""

            # Convert module path to URL path segments
            path_parts = rel_path.split(".")

            # Remove the final part if it's a controller module name
            if path_parts[-1].endswith("_controller"):
                path_parts = path_parts[:-1]

            # Convert to URL path
            if path_parts:
                return "/" + "/".join(path_parts)
            return ""

        # Walk through all modules in the package
        for finder, name, is_pkg in pkgutil.walk_packages(
            [str(package_path)], f"{base_module}."
        ):
            try:
                # Import the module
                module = importlib.import_module(name)
                url_prefix = get_url_prefix(name)

                # Find controller classes in the module
                for item_name, item in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(item, Controller)
                        and item != Controller
                        and item.__module__ == module.__name__
                    ):

                        # Combine module path prefix with explicit controller prefix
                        controller_meta = getattr(item, "meta", {})
                        controller_prefix = controller_meta.get("url_prefix", "")

                        if controller_prefix:
                            # Ensure controller prefix starts with /
                            if not controller_prefix.startswith("/"):
                                controller_prefix = "/" + controller_prefix
                            full_prefix = url_prefix + controller_prefix
                        else:
                            full_prefix = url_prefix

                        controllers.append((item, full_prefix))

            except ImportError as e:
                logger.error(f"Failed to import module {name}: {e}")
                continue

    except ImportError as e:
        raise ImportError(f"Failed to import controllers package: {e}")

    return controllers


class Metro(FastAPI):
    def __init__(self, config: Config = None, **kwargs):
        default_kwargs = {
            "title": "Metro API",
        }
        kwargs = {**default_kwargs, **kwargs}

        super().__init__(**kwargs)

        # Load configuration
        self.config = config or app_config

        # Register exception handlers
        for exc_class, handler in exception_handlers.items():
            self.add_exception_handler(exc_class, handler)

        # Add method override middleware by default
        self.add_middleware(MethodOverrideMiddleware)

        disable_admin_panel = not kwargs.get("admin_panel_enabled", True)
        auto_discover_controllers = kwargs.get("auto_discover_controllers", True)

        # Enable admin panel if enabled
        if self.config.ADMIN_PANEL_ENABLED and not disable_admin_panel:
            self.include_controller(AdminPanelController)
            self.include_controller(AdminPanelAuthController)
            if "server" in self.config.APP_MODE:  # or some similar check
                logger.info(
                    f"Admin panel running on {self.config.ADMIN_PANEL_ROUTE_PREFIX}."
                )

        if self.config.AUTO_DISCOVER_CONTROLLERS and auto_discover_controllers:
            controllers_dir = getattr(self.config, "CONTROLLERS_DIR", "app/controllers")
            self.auto_discover_controllers(controllers_dir)

    def customize_openapi(self):
        """
        Overwrites FastAPI's default openapi() method to
        insert a global bearerAuth security scheme.
        """
        if self.openapi_schema:
            return self.openapi_schema

        openapi_schema = get_openapi(
            title=self.title,
            version=self.version,
            description=self.description,
            routes=self.routes,
        )
        # Insert a global bearerAuth scheme in the "components" section
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",  # or whatever format you use
            }
        }

        # If you want to enforce Bearer auth by default on all endpoints,
        # uncomment the line below. Then you'll only skip auth for endpoints
        # that explicitly override the security. But typically you keep this empty:
        # openapi_schema["security"] = [{"bearerAuth": []}]

        self.openapi_schema = openapi_schema
        return self.openapi_schema

    def connect_db(self):
        for alias, db_config in self.config.DATABASES.items():
            is_default = alias == "default"
            db_manager.connect_db(
                alias=alias,
                db_name=db_config["NAME"],
                db_url=db_config["URL"],
                is_default=is_default,
                ssl_reqs=db_config["SSL"],
                **db_config.get("KWARGS", {}),
            )

    def include_controller(self, controller_cls, prefix: str = "", tags: list = None):
        controller_instance = controller_cls()
        self.include_router(
            controller_instance.router,
            prefix=prefix,
            tags=tags or [controller_cls.__name__.replace("Controller", "")],
        )

    def include_route(self, route_func):
        if hasattr(route_func, "_route_info"):
            route_info = route_func._route_info
            path = route_info["path"]
            methods = route_info["methods"]
            self.add_api_route(path, route_func, methods=methods)
        else:
            # Assume it's a standard FastAPI route
            pass

    def auto_discover_controllers(self, controllers_dir: str = "app/controllers"):
        """
        Automatically discovers and registers all controllers in the specified directory.
        Handles nested directory prefixes and explicit controller prefixes.

        Args:
            controllers_dir: Path to the controllers directory relative to the project root
        """
        try:
            # Gets list of (controller_class, url_prefix) tuples
            discovered_controllers = discover_controllers(controllers_dir)

            for controller_cls, prefix in discovered_controllers:
                # Get the controller name without 'Controller' suffix for use as a tag
                controller_name = controller_cls.__name__.replace("Controller", "")

                # Register the controller using the prefix from discovery
                # (which already includes both directory structure and explicit prefixes)
                self.include_controller(
                    controller_cls, prefix=prefix, tags=[controller_name]
                )

        except (DirectoryNotFoundError, ImportError) as e:
            logger.error(f"Controller auto-discovery failed: {e}")
            raise


__all__ = [
    "Metro",
    "Request",
    "Response",
    "Config",
    "MetroWorker",
]
