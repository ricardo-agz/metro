# Introduction to Metro

Metro is a modern and high-performance Python web framework for building robust, production-ready APIs quickly and efficiently. It takes an opinionated but flexible, batteries-included approach with many features out of the box. Under the hood, it is powered by FastAPI and MongoEngine and takes a lot of inspiration from Ruby on Rails and Django.

## Key Features:

- **Fast and performant**: Thanks to FastAPI/Starlette and MongoEngine powering the web and database parts.
- **Super-fast to code**: Generate full resources, models, and controllers with a single command. `metro generate scaffold Post title:str content:str author:ref:User`
- **Built-in admin panel**: Auto-generated admin panel for managing resources. `localhost:8000/admin` and `metro admin createsuperuser`
- **Built-in authentication**: User authentication and authorization out of the box. `from metro.auth import UserBase`
- **First-class file storage support**: Built-in support for file uploads and storage. `avatar = FileField(required=False)` automatically handles file uploads to the backend of choice (file storage, S3, etc.) and stores a pointer in the database.
- **Built-in rate limiting**: Rate limiting for API endpoints. `@throttle(per_minute=100, key=lambda req: req.client.host)` to limit the number of requests to an endpoint.
- **MongoDB native**: First-class support for MongoDB as the default database, powered by MongoEngine under the hood for the ODM.
- **FastAPI compatible**: Since Metro is powered by FastAPI under the hood, you can turn a FastAPI app into a Metro app without having to start from scratch or 


## Why Metro?

### Fast to Code

* **Convention Over Configuration**: Spend less time making decisions about project structure and more time building features
* **Built-in Generators**: Scaffold entire resources, models, and controllers with a single command
* **Batteries Included**: Common patterns for file handling, rate limiting, and messaging come pre-configured

### Fast to Run

* **Built on FastAPI**: Leverage FastAPI's high performance and automatic OpenAPI documentation
* **MongoDB Native**: First-class support for MongoDB through MongoEngine with optimized queries
* **Type Safety**: Full type checking support through Python type hints and Pydantic

### Fast to Scale

* **Docker-Ready**: Built-in Docker support for both development and production
* **Environment-Aware**: Separate configurations for development and production environments
* **Modern Stack**: Based on proven technologies: FastAPI, MongoDB, Pydantic, and Python 3.7+

## Key Features

### 🚀 Modern Python Web Framework

```python
from metro import Controller, get

class UserController(Controller):
    @get("/users/{id}")
    async def get_user(self, id: str):
        user = User.find_by_id(id)
        return user.to_dict()
```

### 📦 Powerful CLI Tools

```bash
# Create a new project
metro new my_project

# Generate a full resource
metro generate scaffold Post title:str content:str author:ref:User

# Start the development server
metro run
```

### 🗃️ Intuitive Database Models

```python
from metro import BaseModel, fields

class User(BaseModel):
    name = fields.StringField(required=True)
    email = fields.EmailField(unique=True)
    posts = fields.ListField(fields.ReferenceField('Post'))
```

## Getting Started

Ready to build your first Metro application? Follow our [Quick Start Guide](./getting-started/quickstart) or dive into the [Installation Instructions](./getting-started/installation.md).


## Community and Support

- 📚 [Documentation](https://docs.metroapi.dev)

## License

Metro is open-source software licensed under the MIT license.