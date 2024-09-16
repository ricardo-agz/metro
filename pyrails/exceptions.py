from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request


class NotFoundError(HTTPException):
    def __init__(self, detail="Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ValidationError(HTTPException):
    def __init__(self, detail="Validation failed"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail="Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


exception_handlers = {
    HTTPException: http_exception_handler,
}
