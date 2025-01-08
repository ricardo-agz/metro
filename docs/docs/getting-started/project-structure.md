---
sidebar_position: 3
---

# Project Structure

Metro follows a conventional project structure to let the framework 

## Default Project Structure

When you create a new Metro project using `metro new my_project`, it creates the following structure:

```
my_project/
├── app/
│   ├── controllers/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   └── __init__.py
├── config/
│   ├── development.py
│   ├── production.py
│   └── __init__.py
├── main.py
├── Dockerfile
└── docker-compose.yml
```

A more complete project structure may look something like this:

```
my_project/
├── app/
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── users_controller.py
│   │   ├── posts_controller.py
│   │   └── ...
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── post.py
│   │   └── ...
│   └── __init__.py
├── config/
│   ├── development.py
│   ├── staging.py
│   ├── production.py
│   └── __init__.py
├── main.py
├── Dockerfile
├── docker-compose.yml
├── .env
├── .env.development
├── .env.staging
└── .env.development
```

Let's look at each component in detail:

## Core Directories

### `app/` Directory

The `app/` directory contains your application's core logic:

```
app/
├── controllers/              # HTTP request handlers
│   ├── users_controller.py
│   ├── posts_controller.py
│   ├── auth_controller.py
│   └── __init__.py
├── models/                   # Database models
│   ├── user.py
│   ├── post.py
│   └── __init__.py
└── __init__.py
```

#### Controllers
- Contains all your application's controllers
- Each controller typically handles one resource
- Controllers are automatically imported and registered
- Example: `users_controller.py`, `posts_controller.py`

#### Models
- Contains your database models
- Each model typically represents one collection in MongoDB
- Models are automatically discovered and registered
- Example: `user.py`, `post.py`

### `config/` Directory

The `config/` directory contains environment-specific configurations:

```
config/
├── development.py        # Development environment settings
├── production.py         # Production environment settings
└── __init__.py
```

:::caution Configuration Security
The config directory is only meant to store **non-sensitive** configuration settings. Secrets should be stored in `.env` files and environment specific secrets should be stored in `.env.*` files (e.g. `.env.development` or `.env.production`)
:::

<br/>

Common configuration options:

```python
# config/development.py
DATABASE_URL = "mongodb://localhost:27017/my_project_dev"
DEBUG = True
ENABLE_ADMIN_PANEL = True
FILE_STORAGE_BACKEND = "filesystem"
FILE_SYSTEM_STORAGE_LOCATION = "./uploads"

# config/production.py
DEBUG = False
ENABLE_ADMIN_PANEL = False
FILE_STORAGE_BACKEND = "s3"
```

:::info Environment Variables
It is not necessary to declare secrets in config files (e.g. `MY_SECRET = os.getenv("MY_SECRET")`). Env config vars are automatically loaded first from `.env` then their respective `.env.{environment}` file.
:::

## Root Files

### `main.py`

The application entry point:

```python
from metro import Metro
from contextlib import asynccontextmanager
from app.controllers import *


@asynccontextmanager
async def lifespan(app: Metro):
    app.connect_db()
    yield


app = Metro(lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

```

### `Dockerfile`

Default Docker configuration:

```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["metro", "run"]
```

### `docker-compose.yml`

Docker Compose configuration for development:

```yaml
version: '3'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - ENVIRONMENT=development
    depends_on:
      - mongo

  mongo:
    image: mongo:4.4
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

## Best Practices

1. **File Naming**
   - Controllers: `users_controller.py`, `payments_controller.py`, `auth_controller.py`, etc.
   - Models: `user.py`, `post.py`
   - Use snake_case for file names

2. **Class Naming**
   - Controllers (plural): `UsersController`, `PaymentsController`, `AuthController`, etc.
   - Models (singular): `User`, `Post`, etc.
   - Use PascalCase for class names

3. **Organization**
   - Follow the intended project structure.

4. **Configuration**
   - Use config files for **non-sensitive** application settings.
   - Use .env files for secrets.

## Next Steps

- Learn about [Models](../core-concepts/models)
- Explore [Controllers](../core-concepts/controllers)
- Understand [Configuration](../deployment/configuration)