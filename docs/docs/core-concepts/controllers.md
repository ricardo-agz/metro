---
sidebar_position: 2
---

# Controllers

Controllers in Metro handle HTTP requests and define your API endpoints. They provide a clean, organized way to structure your application's business logic.

## Generating Controllers

Create a new controller using the Metro generator:

```bash
# Generate a basic controller
metro generate controller User

# Generate a controller with specific routes
metro generate controller Auth post:login post:register get:me
```

## Basic Controller Structure

A typical Metro controller looks like this:

```python
from metro.controllers import Controller
from metro import Request
from metro.exceptions import NotFoundError

class UserController(Controller):
    @get('/users')
    async def index(self, request: Request):
        users = User.find_many()
        return {"users": [user.to_dict() for user in users]}

    @get('/users/{id}')
    async def show(self, request: Request, id: str):
        user = User.find_by_id(id)
        if not user:
            raise NotFoundError(detail="User not found")
        return user.to_dict()

    @post('/users')
    async def create(self, request: Request):
        data = await request.json()
        user = User(**data)
        user.save()
        return user.to_dict()

    @put('/users/{id}')
    async def update(self, request: Request, id: str):
        user = User.find_by_id(id)
        if not user:
            raise NotFoundError(detail="User not found")
        data = await request.json()
        user.update(**data)
        return user.to_dict()

    @delete('/users/{id}')
    async def delete(self, request: Request, id: str):
        user = User.find_by_id(id)
        if not user:
            raise NotFoundError(detail="User not found")
        user.delete()
        return {"status": "success"}
```

## Resource Scaffolding

Generate a complete CRUD resource with a single command:

```bash
metro generate scaffold Post title:str content:str author:ref:User
```

This creates:
- A Post model
- A PostsController with CRUD endpoints
- Necessary import statements in `__init__.py` files

## Controller Lifecycle Hooks

Controllers support various hooks for cross-cutting concerns:

```python
class AdminController(Controller):
    @before_request
    async def check_admin(self, request: Request):
        user = await get_current_user(request)
        if not user.is_admin:
            raise UnauthorizedError(detail="Admin access required")

    @after_request
    async def log_request(self, request: Request):
        print(f"Request processed: {request.method} {request.url}")

# This controller inherits the admin checks
class AdminUserController(AdminController):
    @get('/admin/users')
    async def index(self, request: Request):
        users = User.find_many()
        return {"users": [user.to_dict() for user in users]}
```

## Rate Limiting

Add rate limiting to your endpoints using the `@throttle` decorator:

```python
from metro.rate_limiting import throttle

class UserController(Controller):
    @get('/users/{id}')
    @throttle(
        per_second=1,
        per_minute=30,
        per_hour=500
    )
    async def show(self, request: Request, id: str):
        user = User.find_by_id(id)
        return user.to_dict()
```

### Custom Rate Limiting

Customize rate limiting behavior:

```python
@throttle(
    name="api_endpoint",  # Namespace for the rate limiter
    per_minute=30,
    backend=RedisRateLimiterBackend(),  # Custom backend
    key=lambda request: request.client.host,  # Custom key function
    cost=lambda request: 2 if request.method == "POST" else 1  # Custom cost
)
```

## File Uploads

Handle file uploads in your controllers:

```python
class UserController(Controller):
    @put('/users/{id}/avatar')
    async def update_avatar(
        self,
        id: str,
        avatar: UploadFile = File(None)
    ):
        user = User.find_by_id(id=id)
        if avatar:
            user.avatar = avatar
            user.save()
        return user.to_dict()

    @post('/galleries/{id}/images')
    async def upload_images(
        self,
        id: str,
        images: List[UploadFile] = File(None)
    ):
        gallery = Gallery.find_by_id(id=id)
        if images:
            gallery.images.extend(images)
            gallery.save()
        return gallery.to_dict()
```

## Error Handling

Metro provides standard exceptions for common scenarios:

```python
from metro.exceptions import (
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    ForbiddenError
)

class PostController(Controller):
    @get('/posts/{id}')
    async def show(self, request: Request, id: str):
        post = Post.find_by_id(id)
        if not post:
            raise NotFoundError(detail="Post not found")
        
        user = await get_current_user(request)
        if not post.can_view(user):
            raise ForbiddenError(detail="Not allowed to view this post")
            
        return post.to_dict()
```

## Authentication Example

Here's an example of an authentication controller:

```python
class AuthController(Controller):
    @post('/auth/login')
    async def login(self, request: Request):
        data = await request.json()
        user = User.find_one(email=data['email'])
        
        if not user or not user.verify_password(data['password']):
            raise UnauthorizedError(detail="Invalid credentials")
            
        token = create_jwt_token(user.id)
        return {
            "token": token,
            "user": user.to_dict()
        }

    @get('/auth/me')
    @throttle(per_minute=60)
    async def me(self, request: Request):
        user = await get_current_user(request)
        return user.to_dict()
```

## Next Steps

- Learn about [Rate Limiting](../features/rate-limiting) in detail
- Explore [File Handling](../features/file-handling) configuration
- Set up [Email Sending](../features/email) in your controllers