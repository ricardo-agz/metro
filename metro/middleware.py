from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pre-processing logic
        print(f"Incoming request: {request.method} {request.url}")
        response = await call_next(request)
        # Post-processing logic
        print(f"Response status: {response.status_code}")
        return response
