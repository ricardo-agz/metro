import asyncio
import inspect
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, runtime_checkable, Protocol


@runtime_checkable
class DependencyAware(Protocol):
    is_dependency: bool

    async def __call__(self, *args: any, **kwargs: any) -> any: ...


P = ParamSpec("P")
R = TypeVar("R")


def detect_dependency_usage(func: Callable[P, R]) -> DependencyAware:
    """
    A decorator that allows a function to detect when it's being used as a FastAPI dependency.
    Works with both sync and async functions.
    """
    # Store the original function for inspection
    original_func = func
    is_async = asyncio.iscoroutinefunction(original_func)

    def check_dependency_stack(frame: any) -> bool:
        """Check if we're being called from FastAPI's dependency system."""
        while frame is not None:
            # Get the local variables in this frame
            local_vars = frame.f_locals

            # Look for FastAPI's Depends class in the locals
            if any(
                str(var).startswith("<fastapi.params.Depends")
                for var in local_vars.values()
            ):
                return True

            # Also check if we're in FastAPI's dependency resolution
            if frame.f_code.co_name in {
                "solve_dependencies",
                "request_params_to_args",
            } and any(
                p in frame.f_code.co_filename
                for p in {"fastapi", "routing.py", "dependencies.py"}
            ):
                return True

            frame = frame.f_back
        return False

    if is_async:

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            frame = inspect.currentframe()
            try:
                wrapper.is_dependency = check_dependency_stack(frame)
                return await original_func(*args, **kwargs)
            finally:
                del frame

    else:

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            frame = inspect.currentframe()
            try:
                wrapper.is_dependency = check_dependency_stack(frame)
                return original_func(*args, **kwargs)
            finally:
                del frame

    # Initialize the is_dependency flag
    wrapper.is_dependency = False

    return wrapper
