import inspect
from functools import wraps
from typing import Annotated, Callable, Optional
from fastapi import Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from metro.requests import Request
from metro.exceptions import UnauthorizedError
from metro.auth.user.user_base import UserBase
from metro.config import config
from metro.models import BaseModel


models_dir = config.MODELS_DIR.lstrip(".").lstrip("/").rstrip("/")


def find_user_base_subclass() -> type[UserBase]:
    """
    Find the UserBase subclass in the models directory.
    :return: UserBase subclass
    """
    import importlib.util
    import os

    models_dir_path = os.path.join(os.getcwd(), models_dir)
    models_files = os.listdir(models_dir_path)

    for root, dirs, files in os.walk(models_dir_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file.replace(".py", "")
                module_path = os.path.join(root, file)

                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name in dir(module):
                    obj = getattr(module, name)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, UserBase)
                        and obj != UserBase
                    ):
                        return obj

    raise Exception("No UserBase subclass found in models directory")


security = HTTPBearer(
    scheme_name="Bearer Auth", description="Enter your Bearer token", auto_error=False
)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def get_token_from_request(request: Request) -> str | None:
    """Extract bearer token from request headers"""
    auth_headers = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )
    return auth_headers.replace("Bearer ", "") if auth_headers else None


def get_user_if_authenticated(request: Request) -> UserBase | None:
    """
    Check if a user is authenticated based on the request headers.
    :param request:
    :return: UserBase object if authenticated, False otherwise
    """
    token = get_token_from_request(request)
    user_class = find_user_base_subclass()

    return user_class.verify_auth_token(token) if token else None


def get_authenticated_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Security(security)
) -> UserBase:
    """
    Get the authenticated user from the request headers.
    :param request:
    :param credentials: Optional credentials from FastAPI security dependency
    :return: UserBase object if authenticated, raises UnauthorizedError otherwise
    :raises UnauthorizedError: If no authentication token is provided or if the token is invalid
    """

    token = credentials.credentials if credentials else get_token_from_request(request)
    if not token:
        raise UnauthorizedError("No authentication token provided")

    user_class = find_user_base_subclass()

    user = user_class.verify_auth_token(token)
    if not user:
        raise UnauthorizedError("Invalid authentication token")

    return user


def requires_auth(function: Callable):
    """
    Decorator to require authentication for a controller method.

    Controller method example:
        @get("/my-endpoint")
        @requires_auth
        async def my_endpoint(self, request: Request):
            ...
    """
    function._requires_auth = True

    @wraps(function)
    async def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(function)
        is_async = inspect.iscoroutinefunction(function)

        request = next(
            (arg for arg in args if isinstance(arg, Request)), kwargs.get("request")
        ) or kwargs.get("_request")
        credentials = next(
            (arg for arg in args if isinstance(arg, HTTPAuthorizationCredentials)),
            kwargs.get("credentials"),
        )

        curr_user = get_authenticated_user(credentials=credentials, request=request)

        if "user" in sig.parameters:
            kwargs["user"] = curr_user
        else:
            raise ValueError(
                f"Controller method {function.__qualname__} must accept a 'user' parameter when using @requires_auth.\n"
                f"Please update the method signature to:\n\n"
                f"    {'async def' if is_async else 'def'} {function.__name__}(self, request: Request, user: UserBase)"
            )

        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

        return await function(*args, **filtered_kwargs)

    return wrapper


def get_user_roles(user: UserBase) -> list[str]:
    """Helper to get roles from user object consistently"""
    if hasattr(user, "get_roles") and callable(user.get_roles):
        roles = user.get_roles()
    elif hasattr(user, "roles"):
        roles = user.roles
    else:
        raise Exception(
            "User model must either implement get_roles() method or have a roles attribute."
        )

    # Normalize roles to list
    if isinstance(roles, (str, bytes)):
        return [roles]
    elif isinstance(roles, (list, set, tuple)):
        return list(roles)
    else:
        try:
            return list(roles)
        except TypeError:
            raise Exception("User roles must be an iterable of role names")


def requires_role(role: str) -> Callable:
    """
    Authorization requires exact role.

    Usage:
        @requires_role('admin')
        async def admin_endpoint(self, request: Request):
            ...
    """
    if not isinstance(role, str):
        raise TypeError(
            "requires_role expects a string, use requires_any_roles for a list"
        )

    def decorator(func: Callable) -> Callable:
        # Don't use requires_auth decorator directly
        @wraps(func)
        async def wrapper(controller, request: Request = None, *args, **kwargs):
            if not request:
                request = kwargs.get("request") or kwargs.get("_request")

            # If we're being used with requires_auth, user will be in kwargs
            user = kwargs.get("user")
            if not user:
                # If no user in kwargs, we need to authenticate
                credentials = next(
                    (
                        arg
                        for arg in args
                        if isinstance(arg, HTTPAuthorizationCredentials)
                    ),
                    kwargs.get("credentials"),
                )
                user = get_authenticated_user(credentials=credentials, request=request)
                kwargs["user"] = user

            # Check roles
            user_roles = get_user_roles(user)
            if role not in user_roles:
                raise UnauthorizedError(f"User must have the role: {role}")

            # Add user to kwargs
            kwargs["user"] = user

            # Filter kwargs based on function signature
            sig = inspect.signature(func)
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

            if "request" in sig.parameters and request is not None:
                filtered_kwargs["request"] = request

            return await func(controller, *args, **filtered_kwargs)

        return wrapper

    return decorator


def requires_any_roles(roles: list[str]) -> Callable:
    """
    Authorization requires any of the specified roles.

    Usage:
        @requires_any_roles(['admin', 'editor'])
        async def manage_content(self, request: Request):
            ...
    """
    if not isinstance(roles, (list, tuple, set)):
        raise TypeError("requires_any_roles expects a list of roles")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @requires_auth
        async def wrapper(
            controller, request: Request, user: UserBase, *args, **kwargs
        ):
            user_roles = get_user_roles(user)

            if not any(role in user_roles for role in roles):
                raise UnauthorizedError(
                    f"User must have at least one of these roles: {', '.join(roles)}"
                )

            return await func(controller, request, *args, **kwargs)

        return wrapper

    return decorator


def requires_all_roles(roles: list[str]) -> Callable:
    """
    Authorization requires all specified roles.

    Usage:
        @requires_all_roles(['editor', 'verified'])
        async def publish_content(self, request: Request):
            ...
    """
    if not isinstance(roles, (list, tuple, set)):
        raise TypeError("requires_all_roles expects a list of roles")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @requires_auth
        async def wrapper(
            controller, request: Request, user: UserBase, *args, **kwargs
        ):
            user_roles = get_user_roles(user)

            missing_roles = [role for role in roles if role not in user_roles]
            if missing_roles:
                raise UnauthorizedError(
                    f"User is missing required roles: {', '.join(missing_roles)}"
                )

            return await func(controller, request, *args, **kwargs)

        return wrapper

    return decorator
