from functools import wraps
from typing import Annotated, Callable

from fastapi import Depends

from metro.requests import Request
from metro.exceptions import UnauthorizedError
from metro.auth.user.user_base import UserBase


def current_user(request: Request) -> UserBase | None:
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    return UserBase.verify_auth_token(token) if token else None


def get_current_user(request: Request) -> UserBase:
    """Base dependency for getting the current user"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        raise UnauthorizedError("No authentication token provided")

    curr_user = UserBase.verify_auth_token(token)
    if not curr_user:
        raise UnauthorizedError("Invalid authentication token")

    return curr_user


def requires_auth(func: Callable = None):
    """
    Can be used either as a decorator or dependency.

    As decorator in controller:
        @get("/my-endpoint")
        @requires_auth
        async def my_endpoint(self, request: Request):
            ...

    As regular FastAPI dependency:
        @app.get("/my-endpoint", dependencies=[Depends(requires_auth)])
        async def my_endpoint(request: Request):
            ...

    As injectable dependency:
        @app.get("/my-endpoint")
        async def my_endpoint(user: Annotated[UserBase, Depends(requires_auth)]):
            ...
    """
    if func is None:
        # When used as a dependency, return the authentication function
        return get_current_user

    # When used as a decorator
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if being used in controller context
        if len(args) >= 2 and hasattr(args[0], '__class__'):
            controller, request, *rest = args
            # Handle controller method
            curr_user = get_current_user(request)
            kwargs['current_user'] = curr_user
            return await func(controller, request, *rest, **kwargs)
        else:
            # Handle regular route
            request = next((arg for arg in args if isinstance(arg, Request)), kwargs.get('request'))
            if not request:
                raise ValueError("Request object not found in arguments")

            curr_user = get_current_user(request)
            kwargs['current_user'] = curr_user
            return await func(*args, **kwargs)

    return wrapper


def requires_roles(*roles: str | Callable, require_all: bool = False):
    """
    Can be used either as a decorator or dependency.

    As decorator:
        @requires_roles('admin', 'manager')
        async def my_endpoint(request):
            ...

    As dependency:
        user: Annotated[UserBase, Depends(requires_roles('admin'))]
    """

    # Helper function to check roles
    def check_user_roles(curr_user: UserBase, required_roles: tuple[str]):
        if hasattr(curr_user, 'get_roles') and callable(curr_user.get_roles):
            user_roles = curr_user.get_roles()
        elif hasattr(curr_user, 'roles'):
            user_roles = curr_user.roles
        else:
            raise Exception(
                "User model must either implement get_roles() method or have a roles attribute."
            )

        # Convert to list if it's not already an iterable
        if isinstance(user_roles, (str, bytes)):
            user_roles = [user_roles]
        elif not isinstance(user_roles, (list, set, tuple)):
            try:
                user_roles = list(user_roles)
            except TypeError:
                raise Exception("User roles must be an iterable of role names")

        if require_all:
            missing_roles = [role for role in required_roles if role not in user_roles]
            if missing_roles:
                raise UnauthorizedError(
                    f"User is missing required roles: {', '.join(missing_roles)}"
                )
        else:
            if not any(role in user_roles for role in required_roles):
                raise UnauthorizedError(
                    f"User must have at least one of these roles: {', '.join(required_roles)}"
                )

    # If used as dependency (first arg is a string)
    if roles and isinstance(roles[0], (str, bytes)):
        async def role_checker(user: Annotated[UserBase, Depends(requires_auth())]):
            check_user_roles(user, roles)
            return user

        return Depends(role_checker)

    # If used as decorator (first arg is the function)
    func = roles[0]
    role_list = roles[1:]

    @wraps(func)
    @requires_auth
    async def wrapper(controller, request: Request, *args, **kwargs):
        curr_user = kwargs['current_user']
        check_user_roles(curr_user, role_list)
        return await func(controller, request, *args, **kwargs)

    return wrapper
    return wrapper


def requires_role(*roles: str, require_all: bool = False):
    """
    Decorator to check if a user has the required roles.
    Supports both get_roles() method and roles attribute.

    Args:
        *roles: Variable number of required role names
        require_all: If True, user must have ALL specified roles
                    If False, user must have ANY of the specified roles
    """
    def decorator(func):
        @wraps(func)
        @requires_auth
        async def wrapper(controller, request: Request, *args, **kwargs):
            curr_user = kwargs.get('current_user')

            if hasattr(curr_user, 'get_roles') and callable(curr_user.get_roles):
                user_roles = curr_user.get_roles()
            # Fall back to roles attribute if it exists
            elif hasattr(curr_user, 'roles'):
                user_roles = curr_user.roles
            else:
                raise Exception(
                    "User model must either implement get_roles() method or have a roles attribute."
                )

            # Convert to list if it's not already an iterable
            if isinstance(user_roles, (str, bytes)):
                user_roles = [user_roles]
            elif not isinstance(user_roles, (list, set, tuple)):
                try:
                    user_roles = list(user_roles)
                except TypeError:
                    raise Exception(
                        "User roles must be an iterable of role names"
                    )

            if require_all:
                # User must have ALL specified roles
                missing_roles = [role for role in roles if role not in user_roles]
                if missing_roles:
                    raise UnauthorizedError(
                        f"User is missing required roles: {', '.join(missing_roles)}"
                    )
            else:
                # User must have ANY of the specified roles
                if not any(role in user_roles for role in roles):
                    raise UnauthorizedError(
                        f"User must have at least one of these roles: {', '.join(roles)}"
                    )

            return await func(controller, request, *args, **kwargs)
        return wrapper
    return decorator

