from fastapi import FastAPI, Request, Response
from .config import Config
from .exceptions import exception_handlers
from .db.connect_db import db_manager
from .jobs.worker import PyRailsWorker


class PyRailsApp(FastAPI):
    def __init__(self, config: Config = None, **kwargs):
        default_kwargs = {
            "title": "PyRails",
        }
        kwargs = {**default_kwargs, **kwargs}

        super().__init__(**kwargs)

        # Load configuration
        self.config = config or Config()

        # Register exception handlers
        for exc_class, handler in exception_handlers.items():
            self.add_exception_handler(exc_class, handler)

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
