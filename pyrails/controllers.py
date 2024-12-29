from collections import defaultdict
from typing import Callable, Awaitable

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    Request,
)
from functools import wraps
import inspect

from pyrails.exceptions import UnauthorizedError, HTTPException
from pyrails.logger import logger


# Lifecycle Hook Decorators
def before_request(func: Callable[..., Awaitable[None]]):
    """Decorator to mark a method as a before_request hook."""
    func._hook_type = "before_request"
    return func


def after_request(func: Callable[..., Awaitable[None]]):
    """Decorator to mark a method as an after_request hook."""
    func._hook_type = "after_request"
    return func


def on_connect(func: Callable[..., Awaitable[None]]):
    """Decorator to mark a method as an on_websocket_connect hook."""
    func._hook_type = "on_websocket_connect"
    return func


def on_disconnect(func: Callable[..., Awaitable[None]]):
    """Decorator to mark a method as an on_websocket_disconnect hook."""
    func._hook_type = "on_websocket_disconnect"
    return func


# Route Decorators
def websocket(path: str):
    def decorator(func):
        func._websocket_route_info = {"path": path}
        return func

    return decorator


def route(path: str, methods: list[str]):
    def decorator(func):
        func._route_info = {"path": path, "methods": methods}
        return func

    return decorator


def get(path: str):
    return route(path, ["GET"])


def post(path: str):
    return route(path, ["POST"])


def put(path: str):
    return route(path, ["PUT"])


def delete(path: str):
    return route(path, ["DELETE"])


class WebSocketManager:
    def __init__(self):
        # Maps path to list of active WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)
        # Maps room name to set of WebSocket connections
        self.active_rooms: dict[str, set[WebSocket]] = defaultdict(set)
        # Maps WebSocket connections to the rooms they have joined
        self.connection_rooms: dict[WebSocket, set[str]] = defaultdict(set)

    async def connect(self, path: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[path].append(websocket)
        logger.info(f"WebSocket connected: {websocket.client} at path: {path}")

    def disconnect(self, path: str, websocket: WebSocket):
        if websocket in self.active_connections[path]:
            self.active_connections[path].remove(websocket)
            logger.info(f"WebSocket disconnected: {websocket.client} from path: {path}")
            # Remove from any rooms
            rooms = self.connection_rooms.pop(websocket, set())
            for room in rooms:
                self.active_rooms[room].discard(websocket)
                logger.info(f"WebSocket {websocket.client} left room: {room}")
            if not self.active_connections[path]:
                del self.active_connections[path]

    async def broadcast(self, path: str, message: str):
        connections = self.active_connections.get(path, [])
        logger.info(
            f"Broadcasting message to {len(connections)} connections at path: {path}"
        )
        for connection in connections:
            try:
                await connection.send_text(message)
            except WebSocketException as e:
                logger.error(f"Error sending message to {connection.client}: {e}")
                self.disconnect(path, connection)

    async def send_to_room(self, room: str, message: str):
        connections = self.active_rooms.get(room, set())
        logger.info(
            f"Sending message to room '{room}' with {len(connections)} connections"
        )
        for connection in connections:
            try:
                await connection.send_text(message)
            except WebSocketException as e:
                logger.error(f"Error sending message to {connection.client}: {e}")
                # Assuming path is known; alternatively, track path per connection
                # Here, we skip disconnecting for simplicity
                continue

    def join_room(self, websocket: WebSocket, room: str):
        self.active_rooms[room].add(websocket)
        self.connection_rooms[websocket].add(room)
        logger.info(f"WebSocket {websocket.client} joined room: {room}")

    def leave_room(self, websocket: WebSocket, room: str):
        self.active_rooms[room].discard(websocket)
        self.connection_rooms[websocket].discard(room)
        logger.info(f"WebSocket {websocket.client} left room: {room}")
        if not self.active_rooms[room]:
            del self.active_rooms[room]


class ControllerMeta(type):
    def __new__(cls, name, bases, attrs):
        router = APIRouter()
        new_cls = super().__new__(cls, name, bases, attrs)
        new_cls.router = router
        new_cls.websocket_manager = WebSocketManager()

        # Initialize lifecycle hooks if not present
        new_cls._lifecycle_hooks = {
            "before_request": [],
            "after_request": [],
            "on_websocket_connect": [],
            "on_websocket_disconnect": [],
        }

        # Copy hooks from direct base classes
        for base in bases:
            if hasattr(base, "_lifecycle_hooks"):
                for hook_type, hooks in base._lifecycle_hooks.items():
                    new_cls._lifecycle_hooks[hook_type].extend(hooks)

        # Collect hooks defined in the current class
        for attr_name, attr_value in attrs.items():
            if callable(attr_value) and hasattr(attr_value, "_hook_type"):
                hook_type = getattr(attr_value, "_hook_type")
                new_cls._lifecycle_hooks[hook_type].append(attr_value)

        def create_websocket_endpoint(
            bound_method: Callable[..., Awaitable[None]], path: str
        ):
            """Creates and registers a WebSocket endpoint."""

            @router.websocket(path)
            async def websocket_endpoint(websocket: WebSocket):
                logger.info(f"Establishing WebSocket connection at path: {path}")

                controller_instance = new_cls()
                try:
                    # Connect WebSocket
                    await new_cls.websocket_manager.connect(path, websocket)

                    # Execute before_request hooks (if any specific for WebSocket, adjust accordingly)
                    await controller_instance._execute_hooks(
                        "before_request", websocket
                    )

                    # Execute on_websocket_connect hooks
                    await controller_instance._execute_hooks(
                        "on_websocket_connect", websocket
                    )

                    # Call the user-defined WebSocket handler
                    await bound_method(controller_instance, websocket)
                except WebSocketDisconnect:
                    logger.info(f"WebSocket {websocket.client} disconnected")
                except UnauthorizedError as ue:
                    logger.warning(f"Unauthorized WebSocket connection: {ue.detail}")
                    await websocket.close(code=1008)  # Policy Violation
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    await websocket.close(code=1011)  # Internal Error
                finally:
                    # Execute on_websocket_disconnect hooks
                    await controller_instance._execute_hooks(
                        "on_websocket_disconnect", websocket
                    )

                    # Disconnect WebSocket
                    new_cls.websocket_manager.disconnect(path, websocket)

        def create_http_endpoint(
            bound_method: Callable[..., Awaitable], path: str, methods: list[str]
        ):
            """Creates and registers an HTTP endpoint."""
            sig = inspect.signature(bound_method)
            params = list(sig.parameters.values())
            if params and params[0].name == "self":
                params = params[1:]
            new_sig = sig.replace(parameters=params)

            @wraps(bound_method)
            async def endpoint(*args, **kwargs):
                request: Request = kwargs.get("request")
                controller_instance = new_cls()
                response = None

                try:
                    try:
                        # Execute before_request hooks
                        hook_response = await controller_instance._execute_hooks("before_request", request)
                        if hook_response is not None:
                            return hook_response

                        # Call the user-defined endpoint handler
                        response = await bound_method(
                            controller_instance, *args, **kwargs
                        )
                    except Exception as e:
                        logger.error(f"Error during request handling: {e}")
                        raise e  # Re-raise the exception to be handled by FastAPI
                finally:
                    try:
                        # Execute after_request hooks
                        await controller_instance._execute_hooks(
                            "after_request", request
                        )
                    except Exception as e:
                        logger.error(f"Error in after_request hook: {e}")
                        # Decide whether to raise or log silently

                return response

            endpoint.__signature__ = new_sig

            for http_method in methods:
                getattr(router, http_method.lower())(path)(endpoint)

        # Register both HTTP and WebSocket routes
        for attr_name, method in attrs.items():
            # HTTP Routes
            if hasattr(method, "_route_info"):
                route_info = method._route_info
                path = route_info["path"]
                methods = route_info["methods"]

                bound_method = method.__get__(None, new_cls)
                create_http_endpoint(bound_method, path, methods)

            # WebSocket Routes
            elif hasattr(method, "_websocket_route_info"):
                route_info = method._websocket_route_info
                path = route_info["path"]

                bound_method = method.__get__(None, new_cls)
                create_websocket_endpoint(bound_method, path)

        return new_cls


class Controller(metaclass=ControllerMeta):
    """Base Controller class to be inherited by all controllers."""

    async def before_request(self, obj):
        """Override this method to perform actions before each request."""
        pass

    async def after_request(self, obj):
        """Override this method to perform actions after each request."""
        pass

    async def on_websocket_connect(self, websocket: WebSocket):
        """Override this method to handle actions when a WebSocket connects."""
        pass

    async def on_websocket_disconnect(self, websocket: WebSocket):
        """Override this method to handle actions when a WebSocket disconnects."""
        pass

    async def _execute_hooks(self, hook_name: str, obj):
        """Execute all hooks of a given type."""
        hooks = getattr(self.__class__, "_lifecycle_hooks", {}).get(hook_name, [])
        for hook in hooks:
            try:
                result = await hook(self, obj)
                # If a hook returns a response, return it immediately
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"Error executing {hook_name} hook: {e}")
                # Depending on the hook type, decide whether to continue or halt
                if hook_name == "before_request":
                    raise e  # Critical for request handling
                # For other hooks, continue execution
