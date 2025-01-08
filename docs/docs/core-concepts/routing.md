---
sidebar_position: 3
---

# Routing

PyRails provides a simple and expressive routing system built on top of FastAPI. Routes are defined directly in your controllers using decorators.

## Basic Routing

Routes are defined in controllers using HTTP method decorators:

```python
from pyrails.controllers import Controller
from pyrails import Request

class UsersController(Controller):
    @get('/users')
    async def index(self, request: Request):
        return {"message": "List users"}

    @post('/users')
    async def create(self, request: Request):
        return {"message": "Create user"}

    @get('/users/{id}')
    async def show(self, request: Request, id: str):
        return {"message": f"Show user {id}"}

    @put('/users/{id}')
    async def update(self, request: Request, id: str):
        return {"message": f"Update user {id}"}

    @delete('/users/{id}')
    async def delete(self, request: Request, id: str):
        return {"message": f"Delete user {id}"}
```

## Route Parameters

### Path Parameters
Use curly braces to define path parameters:

```python
class PostsController(Controller):
    @get('/users/{user_id}/posts/{post_id}')
    async def show(self, request: Request, user_id: str, post_id: str):
        return {
            "user_id": user_id,
            "post_id": post_id
        }
```

### Query Parameters
Access query parameters from the request:

```python
class PostsController(Controller):
    @get('/posts')
    async def index(self, request: Request):
        # Access /posts?page=1&per_page=10
        page = request.query_params.get('page', 1)
        per_page = request.query_params.get('per_page', 10)
        return {
            "page": page,
            "per_page": per_page
        }
```

## Request Body

Handle JSON request bodies:

```python
class UsersController(Controller):
    @post('/users')
    async def create(self, request: Request):
        data = await request.json()
        user = User(**data)
        user.save()
        return user.to_dict()
```

## File Uploads

Handle file uploads using FastAPI's `File` and `UploadFile`:

```python
from fastapi import File, UploadFile
from typing import List

class MediaController(Controller):
    @post('/upload')
    async def upload(
        self,
        file: UploadFile = File(...)
    ):
        return {"filename": file.filename}

    @post('/upload-multiple')
    async def upload_multiple(
        self,
        files: List[UploadFile] = File(...)
    ):
        return {"filenames": [f.filename for f in files]}
```

## Route Generation

PyRails can generate routes through the CLI:

```bash
# Generate basic CRUD routes
pyrails generate scaffold Post title:str content:str

# Generate specific controller routes
pyrails generate controller Auth post:login post:register get:me
```

## Route Groups

Group related routes using controller inheritance:

```python
class AdminController(Controller):
    @before_request
    async def check_admin(self, request: Request):
        # Admin authentication logic here
        pass

class AdminUsersController(AdminController):
    @get('/admin/users')
    async def index(self, request: Request):
        users = User.find_many()
        return {"users": [user.to_dict() for user in users]}
```

## Response Types

PyRails controllers can return various types:

```python
class ResponsesController(Controller):
    @get('/text')
    async def text(self, request: Request):
        # Return plain text
        return "Hello, World!"

    @get('/json')
    async def json(self, request: Request):
        # Return JSON (dict automatically converted)
        return {"message": "Hello, World!"}

    @get('/model')
    async def model(self, request: Request):
        # Return model (automatically converted to JSON)
        user = User.find_one(email="example@email.com")
        return user
```

## Error Handling

Use PyRails exceptions for error responses:

```python
from pyrails.exceptions import NotFoundError, UnauthorizedError

class UsersController(Controller):
    @get('/users/{id}')
    async def show(self, request: Request, id: str):
        user = User.find_by_id(id)
        if not user:
            raise NotFoundError(detail="User not found")
        return user.to_dict()

    @post('/users')
    async def create(self, request: Request):
        if not is_authorized(request):
            raise UnauthorizedError(detail="Not authorized")
        # ... create user logic
```

## Rate Limiting Routes

Apply rate limiting to routes:

```python
from pyrails.rate_limiting import throttle

class ApiController(Controller):
    @get('/api/data')
    @throttle(per_minute=60)
    async def get_data(self, request: Request):
        return {"data": "some data"}
```

## API Documentation

Routes are automatically documented in the OpenAPI schema. Access the documentation at `/docs`:

- Interactive API documentation at http://localhost:8000/docs
- OpenAPI schema at http://localhost:8000/openapi.json

## Next Steps

- Learn about [Controllers](controllers) in detail
- Explore [Models](models) for data handling
- Understand [Rate Limiting](../features/rate-limiting)