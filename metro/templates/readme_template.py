readme_template = """# {PROJECT_NAME}

This project was bootstrapped with Metro. 

## Quick Start

### Installation

```
pip install metro
```

### Available Scripts

Start MongoDB:
   ```
   metro db up
   ```

Run the application:
   ```
   metro run
   ```
   
Run the application (with Docker):
    ```
    metro run --docker
    ```

Access the app at `http://localhost:8000`.

## Features

### CLI Commands

- Create a new project: `metro new ProjectName`
- Run the application: `metro run [--port PORT] [--host HOST] [--docker]`
- Generate code: `metro generate [model|controller|scaffold] [options]`
- Database management: `metro db [up|down] [--env ENV] [--method METHOD]`

### Generators

- Model: `metro generate model ModelName field1:type field2:type`
- Controller: `metro generate controller ControllerName`
- Scaffold: `metro generate scaffold ResourceName field1:type field2:type`

### Database Management

- Start database: `metro db up [--env ENV] [--method METHOD]`
- Stop database: `metro db down [--env ENV] [--method METHOD]`
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
- Start with Docker: `metro db up --method docker`
- Start locally: `metro db up --method local`

## Deployment

### Docker

1. Build: `docker build -t {{PROJECT_NAME}} .`
2. Run: `docker run -p 8000:8000 {{PROJECT_NAME}}`

### Docker Compose

1. Build and run: `docker-compose up --build`

### Manual

1. Set up MongoDB
2. Configure `config/production.py`
3. Run: `metro run --host 0.0.0.0 --port 8000`

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Advanced Features

### Background Tasks

Use the `BackgroundTasks` class to run tasks in the background:

```python
from metro.background import BackgroundTasks

@app.get("/")
async def root(background_tasks: BackgroundTasks):
    background_tasks.add_task(some_long_running_task)
    return {{"message": "Task added to background"}}
```

### Middleware

Add custom middleware in `main.py`:

```python
from metro.middleware import LoggingMiddleware

app = Metro()
app.add_middleware(LoggingMiddleware)
```

### Custom Exceptions

Use built-in exceptions or create custom ones:

```python
from metro.exceptions import NotFoundError

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

For more help, consult the Metro documentation or open an issue on the project repository.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.
"""
