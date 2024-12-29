# PyRails

PyRails is a lightweight, opinionated, batteries-included Python web framework built on top of FastAPI and MongoEngine.   
It is means to provide helpful, lightweight abstractions to enable standard ways of implementing common patters to 
prevent the SaaSification of the developer stack. 

**The goal is to enhance not inhibit.**


## Features

- Built on top of FastAPI and MongoEngine ODM
- CLI tool for project management and code generation
- Built-in database management (MongoDB)
- Support for both local and Docker-based development
- Environment-specific configurations
- Automatic API documentation

---

## Installation

Install PyRails using pip:

`pip install pyrails`

---

## Creating a New Project

Create a new PyRails project using the `new` command:

```
pyrails new my_project
cd my_project
```

This will create a new directory `my_project` with the default project structure:

```
my_project/
├── app/
│   ├── controllers/
│   ├── models/
│   └── __init__.py
├── config/
│   ├── development.py
│   ├── production.py  
│   └── __init__.py
├── main.py
├── Dockerfile
└── docker-compose.yml
```

---

## Starting the Development Server

Start the development server using the `run` command:

```
pyrails run
```

This will start the development server on http://localhost:8000.


You can also run the service using Docker:

```
pyrails run --docker
```

---

## Scaffolding Resources

PyRails includes a scaffold generator to quickly create models, controllers, and route definitions for a new resource.

To generate a scaffold for a `Post` resource with `title` and `body` fields:

```
pyrails generate scaffold Post title:str body:str
```

This will generate:

- `app/models/post.py` with a `Post` model class
- `app/controllers/posts_controller.py` with CRUD route handlers
- Update `app/controllers/__init__.py` to import the new controller
- Update `app/models/__init__.py` to import the new model 


## Generating Models and Controllers

You can also generate models and controllers individually.

### Generating a Model

To generate a `Comment` model with `post_id`, `author`, and `content` fields:

```
pyrails generate model Comment post_id:str author:str content:str
```

### Generating a Controller

To generate a controller for `Auth` routes:

```
pyrails generate controller Auth
```

You can also pass in the routes to generate as arguments:

```
pyrails generate controller Auth post:login post:register
```

## Field types

### Basic Field Types:
`str`, `int`, `float`, `bool`, `datetime`, `date`, `dict`, `list`.


### Special Field Types:
`ref`, `file`, `list:ref`, `list:file`, `hashed_str`.

### Defining Model Relationships

You can define relationships between models using the following syntax:

- **One-to-Many Relationship**: Use the `ref:` prefix followed by the related model name.

```
pyrails generate model Post author:ref:User
```

This will generate a `Post` model with an `author` field referencing the `User` model.

- **Many-to-Many Relationship**: Use `list:` and `ref:` together.

```
pyrails generate model Student courses:list:ref:Course
```

This will generate a `Student` model with a `courses` field that is a list of references to `Course` models.

### Field Modifiers
`_`, `^` are used to define a field as optional or unique.

#### Optional Field: 
Append `_` to the field name to mark it as optional.

```
pyrails generate model User email_:str
```

This will generate a `User` model with an optional `email` field.

#### Unique Field: 
Append `^` to the field name to specify it as unique.

```
pyrails generate model User username^:str
```

This will generate a `User` model with a unique `username` field.

## Specialty Field Types

### Hashed Field 
`hashed_str` is a special field type that automatically hashes the value before storing it in the database.

```
pyrails generate model User name:str password_hashed:str
```

This will generate a `User` model with a `password` field stored as a hashed value.

### File Fields
`file` and `list:file` are special field types for handling file uploads. They automatically upload
files to the specified storage backend (local filesystem, AWS S3, etc.) and store the file path and file metadata in the database.

- **`file`**: Generates a single `FileField` on the model.
- **`list:file`**: Generates a `FileListField`, allowing multiple files.

Example usage:
```
pyrails generate model User avatar:file
pyrails generate model Post attachments:list:file
```

This will generate the following model classes:

```python
class User(BaseModel):
    avatar = FileField()
    
class Post(BaseModel):
    attachments = FileListField()
```

Uploading files to s3 then becomes as easy as:

```python
# Set an individual file field
@put('/users/{id}/update-avatar')
async def update_avatar(
    self,
    id: str,
    avatar: UploadFile = File(None),
):
    user = User.find_by_id(id=id)
    if avatar:
        # This stages the file for upload
        user.avatar = avatar
        # This actually uploads the file and stores the metadata in the database
        user.save()
    
    return user.to_dict()

# Work with a list of files 
@post('/posts/{id}/upload-attachments')
async def upload_attachments(
    self,
    id: str,
    attachments: List[UploadFile] = File(None),
):
    post = Post.find_by_id(id=id)
    if attachments:
        # This stages the new files for upload
        post.attachments.extend(attachments)
        # This actually uploads the files and adds appends to the attachments list in the db with the new metadata
        post.save()
    
    return post.to_dict()
```

### File Storage Configuration
The default configuration is set to use the local filesystem and store files in the `uploads` directory. You can change the storage backend and location in the `config/development.py` or `config/production.py` file.

Default configuration:
```python
FILE_STORAGE_BACKEND = "filesystem"
FILE_SYSTEM_STORAGE_LOCATION = "./uploads"
FILE_SYSTEM_BASE_URL = "/uploads/"
```

Custom configuration in `config/development.py` or `config/production.py`:
```python
FILE_STORAGE_BACKEND = 'filesystem'
FILE_SYSTEM_STORAGE_LOCATION = './uploads_dev'
FILE_SYSTEM_BASE_URL = '/uploads_dev/'
```
Or to use AWS S3:
```python
FILE_STORAGE_BACKEND = 's3'
S3_BUCKET_NAME = "my-bucket"
AWS_ACCESS_KEY_ID = "..."
AWS_SECRET_ACCESS_KEY = "..."
AWS_REGION_NAME = "us-east-1"
```

---

## Controller Lifecycle Hooks

Lifecycle hooks like `before_request` and `after_request` can be defined directly in a controller or inherited from a parent controller. Hooks are useful for tasks such as authentication, logging, or cleanup.

### Example: AdminController and AdminUserController

**`admin_controller.py`**
```python
from pyrails.controllers import Controller, before_request, after_request
from pyrails.exceptions import UnauthorizedError
from pyrails import Request

class AdminController(Controller):
    @before_request
    async def check_admin(self, request: Request):
        is_admin = False  # Replace with actual logic
        print("Checking admin status... (this will be run before each request)")
        if not is_admin:
            raise UnauthorizedError(detail="Unauthorized access.")

    @after_request
    async def cleanup_stuff(self, request: Request):
        print("Cleaning up... (this will be run after each request)")
```

**`admin_user_controller.py`**
```python
from app.controllers.admin_controller import AdminController

class AdminUserController(AdminController):
    @get('/admin-user/all-users')
    async def all_users(self, request):
        return {"users": []}
```

### Key Points:
- Hooks like `check_admin` and `after_request` can be defined directly in a controller or inherited from a parent.
- In `AdminUserController`, hooks are inherited from `AdminController` and run before and after each request handler.

### Execution:
- If a `before_request` hook raises an exception (e.g., `UnauthorizedError`), the request handler is skipped, but the `after_request` hook still runs.

---

## Email Sending
Easily send emails using the built-in `EmailSender` class, which supports multiple email providers like Mailgun and AWS SES.

```python
# 1. Configure the provider:
# - For Mailgun
mailgun_provider = MailgunProvider(
    domain=os.getenv("MAILGUN_DOMAIN"), api_key=os.getenv("MAILGUN_API_KEY")
)
mailgun_sender = EmailSender(provider=mailgun_provider)

# - For AWS SES (coming soon)
ses_provider = AWSESProvider(region_name="us-west-2")
ses_sender = EmailSender(provider=ses_provider)

# 2. Send the email:
mailgun_sender.send_email(
    source="sender@example.com",
    recipients=["recipient@example.com"],
    subject="Test Email",
    body="This is a test email sent using Mailgun.",
)
```

---

## Database Management

PyRails provides commands to manage your MongoDB database.

### Starting a Local MongoDB Instance

To start a local MongoDB instance for development:

```
pyrails db up
```

### Stopping the Local MongoDB Instance

To stop the local MongoDB instance:

```
pyrails db down
```

### Running MongoDB in a Docker Container

You can also specify the environment and run MongoDB in a Docker container:

```
pyrails db up --env production --docker
```

---

## Configuration

Environment-specific configuration files are located in the `config` directory:

- `config/development.py`
- `config/production.py`

Here you can set your `DATABASE_URL`, API keys, and other settings that vary between environments.

---

## Admin Panel

PyRails includes a built-in admin panel. You can view this at `/admin`

You can disable this or change the admin route in the `config/development.py` or `config/production.py` file:

```python
ENABLE_ADMIN_PANEL = False
ADMIN_PANEL_ROUTE_PREFIX = "/admin-panel"
```

---

## Documentation and Help

- **API Documentation**: http://localhost:8000/docs
- **CLI help**: `pyrails --help`

For guides, tutorials, and detailed API references, check out the PyRails documentation site.

---

## License

PyRails is open-source software licensed under the MIT license.
