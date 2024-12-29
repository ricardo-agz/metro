from fastapi import FastAPI, Request, Response
from fastapi.routing import ASGIApp
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers
from typing import Callable
from .config import Config, config as app_config
from .exceptions import exception_handlers
from .db.connect_db import db_manager
from .jobs.worker import PyRailsWorker
from pyrails.admin import AdminPanelController, AdminPanelAuthController


class MethodOverrideMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app: ASGIApp,
            override_method_header: str = "X-HTTP-Method-Override"
    ):
        super().__init__(app)
        self.override_method_header = override_method_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        original_receive = request.scope.get("receive", None)

        # Only check for method override if we have a _method field in the form
        # or the override header is present
        if request.headers.get(self.override_method_header) or (
                request.method == "POST" and
                any(h[0].decode() == "content-type" and b"form" in h[1] for h in request.scope["headers"])
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
                        return {"type": "http.request", "body": body, "more_body": False}

                    request.scope["receive"] = receive

            if method and method in ["PUT", "PATCH", "DELETE"]:
                request.scope["method"] = method

                # Update headers
                headers = dict(request.headers)
                headers[self.override_method_header.lower()] = method
                request.scope["headers"] = Headers(headers).raw

        response = await call_next(request)
        return response


class PyRailsApp(FastAPI):
    def __init__(self, config: Config = None, **kwargs):
        default_kwargs = {
            "title": "PyRails",
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

        # Enable admin panel if enabled
        if self.config.ADMIN_PANEL_ENABLED:
            self.include_controller(AdminPanelController)
            self.include_controller(AdminPanelAuthController)

    def connect_db(self):
        for alias, db_config in self.config.DATABASES.items():
            is_default = alias == "default"
            db_manager.connect_db(
                alias=alias,
                db_name=db_config["NAME"],
                db_url=db_config["URL"],
                is_default=is_default,
                ssl_reqs=db_config["SSL"],
                **db_config.get("KWARGS", {})
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


__all__ = [
    "PyRailsApp",
    "Request",
    "Response",
    "Config",
    "PyRailsWorker",
]
