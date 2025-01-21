controller_template = """from metro.controllers import (
    Controller,
    Request,
    get,
    post,
    put,
    delete,
    before_request,
    after_request,
)
from metro.exceptions import (
    NotFoundError,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    TooManyRequestsError,
    HTTPException,
){additional_imports}

{pydantic_models}
class {controller_name}({base_controllers}):
    meta = {{
        "url_prefix": "{url_prefix}",
    }}

{controller_code}
"""
