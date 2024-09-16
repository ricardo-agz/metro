readme_template = """# {PROJECT_NAME}

A PyRails application built with FastAPI and MongoEngine, providing a Ruby on Rails-like experience for Python developers.

## Features

- FastAPI-based web framework with MongoEngine ORM
- CLI tool for project management and code generation
- Built-in database management (MongoDB)
- Support for local and Docker-based development
- Environment-specific configurations
- Automatic API documentation

## Quick Start

### Local Setup

1. Install PyRails:
   ```
   pip install pyrails
   ```

2. Create a new project:
   ```
   pyrails new {{PROJECT_NAME}}
   cd {{PROJECT_NAME}}
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Start MongoDB:
   ```
   pyrails db up
   ```

5. Run the application:
   ```
   pyrails run
   ```

### Docker Setup

1. Create a new project:
   ```
   pyrails new {{PROJECT_NAME}}
   cd {{PROJECT_NAME}}
   ```

2. Build and run with Docker Compose:
   ```
   docker-compose up --build
   ```

Access the app at `http://localhost:8000`.

## Project Structure

```
{{PROJECT_NAME}}/
├── app/
│   ├── controllers/
│   ├── models/
│   └── __init__.py
├── config/
│   ├── development.py
│   ├── production.py
│   ├── testing.py
│   └── __init__.py
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Development

### CLI Commands

- Create a new project: `pyrails new ProjectName`
- Run the application: `pyrails run [--port PORT] [--host HOST] [--docker]`
- Generate code: `pyrails generate [model|controller|scaffold] [options]`
- Database management: `pyrails db [up|down] [--env ENV] [--method METHOD]`

### Generators

- Model: `pyrails generate model ModelName field1:type field2:type`
- Controller: `pyrails generate controller ControllerName`
- Scaffold: `pyrails generate scaffold ResourceName field1:type field2:type`

### Database Management

- Start database: `pyrails db up [--env ENV] [--method METHOD]`
- Stop database: `pyrails db down [--env ENV] [--method METHOD]`
- Methods: `docker`, `local`, `manual`

### Testing

Run tests with pytest:
```
python -m pytest
```

## Configuration

Environment-specific settings are in `config/`:
- `development.py`
- `production.py`
- `testing.py`

Update `DATABASE_URL` and other settings as needed.

## Database

- Default: MongoDB
- Configuration: Update `DATABASE_URL` in the appropriate config file
- Start with Docker: `pyrails db up --method docker`
- Start locally: `pyrails db up --method local`

## Deployment

### Docker

1. Build: `docker build -t {{PROJECT_NAME}} .`
2. Run: `docker run -p 8000:8000 {{PROJECT_NAME}}`

### Docker Compose

1. Build and run: `docker-compose up --build`

### Manual

1. Set up MongoDB
2. Configure `config/production.py`
3. Run: `pyrails run --host 0.0.0.0 --port 8000`

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Advanced Features

### Background Tasks

Use the `BackgroundTasks` class to run tasks in the background:

```python
from pyrails.background import BackgroundTasks

@app.get("/")
async def root(background_tasks: BackgroundTasks):
    background_tasks.add_task(some_long_running_task)
    return {{"message": "Task added to background"}}
```

### Middleware

Add custom middleware in `main.py`:

```python
from pyrails.middleware import LoggingMiddleware

app = PyRailsApp()
app.add_middleware(LoggingMiddleware)
```

### Custom Exceptions

Use built-in exceptions or create custom ones:

```python
from pyrails.exceptions import NotFoundError

@app.get("/items/{{item_id}}")
async def read_item(item_id: str):
    item = find_item(item_id)
    if item is None:
        raise NotFoundError(f"Item {{item_id}} not found")
    return item
```

## Troubleshooting

1. Verify all dependencies are installed
2. Ensure MongoDB is running and accessible
3. Check application logs for errors
4. Verify environment-specific configurations

For more help, consult the PyRails documentation or open an issue on the project repository.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.
"""
