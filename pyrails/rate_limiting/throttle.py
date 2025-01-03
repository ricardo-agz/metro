import functools
from typing import Awaitable, Callable, Optional, Union

from pyrails.rate_limiting.backends import RateLimiterBackend, RateLimits, InMemoryRateLimiterBackend
from pyrails.exceptions import TooManyRequestsError
from fastapi.requests import Request


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

    def __init__(
        self,
        name: str,
        backend: RateLimiterBackend | None = None,
        key: Callable[[Request], str] | str | None = None,
        limits: Callable[[Request], RateLimits] | RateLimits | None = None,
        cost: Callable[[Request], float] | float | None = 1.0,
        per_second: int | None = None,
        per_minute: int | None = None,
        per_hour: int | None = None,
        per_day: int | None = None,
        per_month: int | None = None,
    ):
        """
        Args:
            name: A human-friendly identifier for this Throttler instance.
            backend: Default RateLimiter (like InMemoryRateLimiter, RedisRateLimiter, etc.).
            key: Default string identifier for rate limiting.
            limits: Default RateLimits object (e.g., per_minute=60).
            cost: Default cost per request (e.g., 1.0).
        """
        if not limits:
            limits = RateLimits(
                per_second=per_second,
                per_minute=per_minute,
                per_hour=per_hour,
                per_day=per_day,
                per_month=per_month,
            )

        self.name = name
        self.backend = backend or InMemoryRateLimiterBackend()
        self.key = key
        self.limits = limits
        self.cost = cost

        self.backend.name = name

        print("bakend init", self.backend)

    def __call__(
        self,
        key: Union[str, Callable[[Request], str]],
        limits: Union[RateLimits, Callable[[Request], RateLimits]],
        cost: Union[float, Callable[[Request], float]] = 1.0,
        backend: RateLimiterBackend | None = None,
    ):
        """
        This is triggered when we do `@throttler(...)`.

        Args:
            key: A function that takes the Request and returns an identifier (e.g., IP).
            limits: A function that takes the Request and returns a RateLimits object.
            cost: Either a float or a callable that returns a float cost per request.
            backend: Optionally override the default backend for this route only.

        Returns:
            A decorator that wraps the endpoint, checking the rate limit before calling it.
        """
        effective_backend = backend or self.backend
        key = key or self.key
        limits = limits or self.limits
        cost = cost or self.cost

        print("effective_backend", effective_backend)

        # If the user didn’t supply a key function, default to IP
        if key is None:
            def key(request: Request) -> str:
                # If request.client is sometimes None, handle gracefully
                return request.client.host if request.client else "unknown"

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
                if not allowed:
                    raise TooManyRequestsError(
                        detail=(
                            f"Rate limit exceeded. "
                            f"Allowed={limit_info.limit}, "
                            f"Remaining={limit_info.remaining}, "
                            f"Reset={limit_info.reset}"
                        )
                    )

                # 4. If allowed, call the original function
                return await func(*args, **kwargs)

            return wrapper

        return decorator


def throttle(
    limits: Callable[[Request], RateLimits] | RateLimits | None = None,
    key: Callable[[Request], str] | str | None = None,
    cost: Union[float, Callable[[Request], float]] = 1.0,
    backend: Optional[RateLimiterBackend] = None,
    name: str = "throttler",
    per_second: int | None = None,
    per_minute: int | None = None,
    per_hour: int | None = None,
    per_day: int | None = None,
    per_month: int | None = None,
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

    if not limits:
        limits = RateLimits(
            per_second=per_second,
            per_minute=per_minute,
            per_hour=per_hour,
            per_day=per_day,
            per_month=per_month,
        )

    print("backend", backend)

    # Instantiate a temporary Throttler, then call it immediately
    temp_throttler = Throttler(name=name, backend=backend, key=key, limits=limits, cost=cost)
    return temp_throttler(key=key, limits=limits, cost=cost)
