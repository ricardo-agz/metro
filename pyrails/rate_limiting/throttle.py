import functools
from typing import Awaitable, Callable, Optional, Union

from pyrails.rate_limiting.backends import (
    RateLimiterBackend,
    RateLimits,
    InMemoryRateLimiterBackend,
)
from pyrails.exceptions import TooManyRequestsError
from fastapi.requests import Request
from pyrails.utils.fastapi_dependencies import detect_dependency_usage


def default_callback(request: Request, allowed: bool, limit_info: RateLimits):
    if not allowed:
        raise TooManyRequestsError(
            detail=(
                f"Rate limit exceeded. Allowed={limit_info.limit}, Remaining={limit_info.remaining}, Reset={limit_info.reset}"
            )
        )


def default_key_func(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class ControllerThrottler:
    def __init__(
        self,
        name: str,
        backend: RateLimiterBackend | None = None,
        key: Callable[[Request], str] | str | None = None,
        limits: Callable[[Request], RateLimits] | RateLimits | None = None,
        cost: Callable[[Request], float] | float | None = 1.0,
        callback: Callable[[Request, bool, RateLimits], any] | None = None,
    ):
        self.name = name
        self.backend = backend or InMemoryRateLimiterBackend()
        self.backend.name = name
        self.key = key
        self.limits = limits
        self.cost = cost
        self.callback = callback or default_callback

    def __call__(
        self,
        key: Union[str, Callable[[Request], str]],
        limits: Union[RateLimits, Callable[[Request], RateLimits]],
        per_second: Callable[[Request], int] | int | None = None,
        per_minute: Callable[[Request], int] | int | None = None,
        per_hour: Callable[[Request], int] | int | None = None,
        per_day: Callable[[Request], int] | int | None = None,
        per_month: Callable[[Request], int] | int | None = None,
        cost: Union[float, Callable[[Request], float]] = 1.0,
        backend: RateLimiterBackend | None = None,
        callback: Callable[[Request, bool, RateLimits], any] | None = None,
    ):
        """
        This is triggered when we do `@throttler(...)`.

        Args:
            key: A function that takes the Request and returns an identifier (e.g., IP).
            limits: A function that takes the Request and returns a RateLimits object.
            per_second: Default rate limit per second.
            per_minute: Default rate limit per minute.
            per_hour: Default rate limit per hour.
            per_day: Default rate limit per day.
            per_month: Default rate limit per month.
            cost: Either a float or a callable that returns a float cost per request.
            backend: Optionally override the default backend for this route only.

        Returns:
            A decorator that wraps the endpoint, checking the rate limit before calling it.
        """
        if not limits and any([per_second, per_minute, per_hour, per_day, per_month]):

            def limits(request: Request):
                return RateLimits(
                    per_second=(
                        per_second(request) if callable(per_second) else per_second
                    ),
                    per_minute=(
                        per_minute(request) if callable(per_minute) else per_minute
                    ),
                    per_hour=per_hour(request) if callable(per_hour) else per_hour,
                    per_day=per_day(request) if callable(per_day) else per_day,
                    per_month=per_month(request) if callable(per_month) else per_month,
                )

        effective_backend = backend or self.backend
        key = key or self.key
        limits = limits or self.limits
        cost = cost or self.cost
        callback = callback or self.callback

        def decorator(func: Callable[..., Awaitable]):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # 1. Find the Request object (in kwargs or among positional args)
                request = kwargs.get("request")
                if not request:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break
                if not isinstance(request, Request):
                    raise RuntimeError(
                        "Could not locate 'request' in throttled endpoint. "
                        "Ensure your function signature includes `request: Request`."
                    )

                # 2. Build rate-limit info
                identifier = key(request) if callable(key) else key
                rate_limits = limits(request) if callable(limits) else limits
                usage_cost = cost(request) if callable(cost) else cost

                # 3. Call the underlying backend
                allowed, limit_info = effective_backend.check_rate_limit(
                    identifier, rate_limits, cost=usage_cost
                )

                callback(request, allowed, limit_info)

                if allowed:
                    return await func(*args, **kwargs)

            return wrapper

        return decorator


class RouteThrottler:
    def __init__(
        self,
        name: str,
        backend: RateLimiterBackend | None = None,
        key: Callable[[Request], str] | str | None = None,
        limits: Callable[[Request], RateLimits] | RateLimits | None = None,
        cost: Callable[[Request], float] | float | None = 1.0,
        callback: Callable[[Request, bool, RateLimits], any] | None = None,
    ):
        self.name = name
        self.backend = backend or InMemoryRateLimiterBackend()
        self.backend.name = name
        self.key = key
        self.limits = limits
        self.cost = cost
        self.callback = callback or default_callback

    def __call__(self, request: Request):
        identifier = self.key(request) if callable(self.key) else self.key
        rate_limits = self.limits(request) if callable(self.limits) else self.limits
        usage_cost = self.cost(request) if callable(self.cost) else self.cost

        # Call the underlying backend
        allowed, limit_info = self.backend.check_rate_limit(
            identifier,
            rate_limits,
            cost=usage_cost,
        )

        return self.callback(request, allowed, limit_info)


class Throttler:
    """
    A class-based Throttler that can be instantiated once and reused
    for multiple routes with a shared default RateLimiter backend.

    Usage (shared instance):
        in_memory_backend = InMemoryRateLimiter()
        throttler = Throttler(name="global", backend=in_memory_backend)

        @router.get("/endpoint")
        @throttler(key=lambda req: req.client.host, limits=lambda req: RateLimits(per_minute=60))
        async def endpoint(request: Request):
            return {"hello": "world"}

    Or override the backend / cost per route:
        @router.get("/other-endpoint")
        @throttler(
            key=lambda req: req.client.host,
            limits=lambda req: RateLimits(per_minute=120),
            cost=2.0,
            backend=SomeOtherRateLimiter(...),
        )
        ...
    """

    def __new__(
        cls,
        name: str,
        backend: RateLimiterBackend | None = None,
        key: Callable[[Request], str] | str | None = None,
        limits: Callable[[Request], RateLimits] | RateLimits | None = None,
        cost: Callable[[Request], float] | float | None = 1.0,
        per_second: Callable[[Request], int] | int | None = None,
        per_minute: Callable[[Request], int] | int | None = None,
        per_hour: Callable[[Request], int] | int | None = None,
        per_day: Callable[[Request], int] | int | None = None,
        per_month: Callable[[Request], int] | int | None = None,
        callback: Callable[[Request, bool, RateLimits], any] | None = None,
        as_dependency: bool = False,
    ):
        """
        Args:
            name: A human-friendly identifier for this Throttler instance.
            backend: Default RateLimiter (like InMemoryRateLimiter, RedisRateLimiter, etc.).
            key: Default string identifier for rate limiting.
            limits: Default RateLimits object (e.g., per_minute=60).
            cost: Default cost per request (e.g., 1.0).
            per_second: Default rate limit per second.
            per_minute: Default rate limit per minute.
            per_hour: Default rate limit per hour.
            per_day: Default rate limit per day.
            per_month: Default rate limit per month.
            callback: An optional callback to run after the rate limit check.
            as_dependency: Whether this Throttler should be used as a FastAPI dependency.
        """
        if not limits and any([per_second, per_minute, per_hour, per_day, per_month]):
            print(
                "limits not provided, but per_second, per_minute, per_hour, per_day, or per_month were.",
                per_second,
                per_minute,
                per_hour,
                per_day,
                per_month,
            )

            def limits(request: Request):
                lims = RateLimits(
                    per_second=(
                        per_second(request) if callable(per_second) else per_second
                    ),
                    per_minute=(
                        per_minute(request) if callable(per_minute) else per_minute
                    ),
                    per_hour=per_hour(request) if callable(per_hour) else per_hour,
                    per_day=per_day(request) if callable(per_day) else per_day,
                    per_month=per_month(request) if callable(per_month) else per_month,
                )
                print("limits", lims)
                return lims

        if as_dependency:
            return RouteThrottler(
                name=name,
                backend=backend,
                key=key,
                limits=limits,
                cost=cost,
                callback=callback,
            )
        else:
            return ControllerThrottler(
                name=name,
                backend=backend,
                key=key,
                limits=limits,
                cost=cost,
                callback=callback,
            )


def throttle(
    limits: Callable[[Request], RateLimits] | RateLimits | None = None,
    key: Callable[[Request], str] | str | None = None,
    cost: Union[float, Callable[[Request], float]] = 1.0,
    backend: Optional[RateLimiterBackend] = None,
    name: str = "throttler",
    per_second: Callable[[Request], int] | int | None = None,
    per_minute: Callable[[Request], int] | int | None = None,
    per_hour: Callable[[Request], int] | int | None = None,
    per_day: Callable[[Request], int] | int | None = None,
    per_month: Callable[[Request], int] | int | None = None,
    callback: Callable[[bool, RateLimits, Request], any] | None = None,
):
    """
    A simple function-based decorator for direct usage:

        from pyrails.throttling import throttle
        from fastapi import Request

        @router.get("/endpoint")
        @throttle(
            key=lambda r: r.client.host,
            limits=lambda r: RateLimits(per_minute=60),
            backend=InMemoryRateLimiter(),
        )
        async def endpoint(request: Request):
            return {"hello": "world"}

    Here, we spin up a temporary Throttler with your chosen backend.
    This is great for quickly applying throttling to a single route without
    setting up a shared instance.
    """

    # Instantiate a temporary Throttler, then call it immediately
    temp_throttler = Throttler(
        name=name,
        backend=backend,
        key=key,
        limits=limits,
        per_second=per_second,
        per_minute=per_minute,
        per_hour=per_hour,
        per_day=per_day,
        per_month=per_month,
        cost=cost,
        callback=callback,
    )
    return temp_throttler(key=key, limits=limits, cost=cost)
