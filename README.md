# Metro

Metro is a lightweight, opinionated, batteries-included Python web framework built on top of FastAPI and MongoEngine.   
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

Install Metro using pip:

`pip install metroapi`

---

## Creating a New Project

Create a new Metro project using the `new` command:

```
metro new my_project
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
metro run
```

This will start the development server on http://localhost:8000.


You can also run the service using Docker:

```
metro run --docker
```

---

## Scaffolding Resources

Metro includes a scaffold generator to quickly create models, controllers, and route definitions for a new resource.

To generate a scaffold for a `Post` resource with `title` and `body` fields:

```
metro generate scaffold Post title:str body:str
```

This will generate:

- `app/models/post.py` with a `Post` model class
- `app/controllers/posts_controller.py` with CRUD route handlers
- Update `app/controllers/__init__.py` to import the new controller
- Update `app/models/__init__.py` to import the new model 


### Scaffold Generator Options

```
metro generate scaffold NAME [FIELDS...] [OPTIONS]
```

#### Available Options:

`--actions`, `-a` (multiple): Define additional custom routes beyond CRUD operations

* Format: `http_method:path (query: params) (body: params) (desc: description) (action_name: action_name)`
* Example: `-a "get:search (query: term:str) (desc: Search users) (action_name: search_users)"`


`--exclude-crud`, `-x` (multiple): Specify which CRUD operations to exclude

* Choices: `index`, `show`, `create`, `update`, `delete`
* Example: `-x delete -x update`


`--model-inherits`: Specify base class(es) for the model

* Format: Single class or comma-separated list
* Example: `--model-inherits UserBase` or `--model-inherits "UserBase,SomeMixin"`


`--controller-inherits`: Specify base class(es) for the controller

* Format: Single class or comma-separated list
* Example: `--controller-inherits AdminController`


`--before-request`, `--before` (multiple): Add lifecycle hooks to run before each request

* Format: `hook_name` or `hook_name:description`
* Example: `--before "check_admin:Verify admin access"`


`--after-request`, `--after` (multiple): Add lifecycle hooks to run after each request

* Format: hook_name or hook_name:description
* Example: --after "log_action:Log all activities"


### Advanced Usage Examples

Full CRUD scaffold with search and custom actions:

```bash
metro generate scaffold Product name:str price:float \
  -a "get:search (query: term:str,min_price:float,max_price:float) (desc: Search products) (action_name: search_products)" \
  -a "post:bulk-update (body: ids:list,price:float) (desc: Update multiple products) (action_name: bulk_update_products)"
```

Scaffold with limited CRUD and inheritance:

```bash
metro generate scaffold AdminUser email:str role:str \
  --model-inherits "UserBase,AuditableMixin" \
  --controller-inherits AdminController \
  -x delete \
  --before "check_admin:Verify admin permissions" \
  --after "log_admin_action:Log admin activities"
```

Custom API endpoints with complex parameters:

```bash
metro generate scaffold Order items:list:ref:Product status:str \
  -a "post:process/{id} (body: payment_method:str) (desc: Process order payment) (action_name: process_order)" \
  -a "get:user/{user_id} (query: status:str,date_from:datetime) (desc: Get user orders) (action_name: get_user_orders)"
  --controller-inherits "BaseController,PaymentMixin"
```


#### Adding Custom Routes
Use the `--actions` or `-a` option to add additional routes beyond the standard CRUD endpoints:

ex.
```bash
metro generate scaffold Comment post_id:ref:Post author:str content:str --actions "post:reply"
# or
metro generate scaffold Post title:str body:str -a "post:publish" -a "get:drafts"
```

This will generate the standard CRUD routes plus two additional routes:
- `POST /posts/publish`
- `GET /posts/drafts`


#### Excluding CRUD Routes
Use the `--exclude-crud` or `-x` option to exclude specific CRUD routes you don't need:

```bash
metro generate scaffold Post title:str body:str -x delete -x update
```

This will generate a scaffold without the delete and update endpoints.

You can combine both options:

```bash
metro generate scaffold Post title:str body:str -a "post:publish" -x delete
```

## Generating Models and Controllers

You can also generate models and controllers individually.

### Generating a Model

To generate a `Comment` model with `post_id`, `author`, and `content` fields:

```
metro generate model Comment post_id:str author:str content:str
```

### Model Generator Options

```
metro generate model NAME [FIELDS...] [OPTIONS]
```

#### Available Options:

`--model-inherits`: Specify base class(es) for the model

* Format: Single class or comma-separated list
* Example: `--model-inherits UserBase` or `--model-inherits "UserBase,SomeMixin"`

Example with all options:

```
metro generate model User email:str password:hashed_str profile:ref:Profile roles:list:str --model-inherits "UserBase"
```

### Generating a Controller

To generate a controller for `Auth` routes:

```
metro generate controller Auth
```

You can also pass in the routes to generate as arguments:

```
metro generate controller Auth post:login post:register
```

### Controller Generator Options

```
metro generate controller NAME [ACTIONS...] [OPTIONS]
```

#### Available Options:

`--controller-inherits`: Specify base class(es) for the controller

* Format: Single class or comma-separated list
* Example: `--controller-inherits AdminController`

`--before-request`, `--before` (multiple): Add lifecycle hooks to run before each request

* Format: `hook_name` or `hook_name:description`
* Example: `--before "check_auth:Verify user authentication"`

`--after-request`, `--after` (multiple): Add lifecycle hooks to run after each request

* Format: `hook_name` or `hook_name:description`
* Example: `--after "log_request:Log API request"`

Example with all options:
```
metro generate controller Auth \
  "post:login (body: email:str,password:str) (desc: User login)" \
  "post:register (body: email:str,password:str,name:str) (desc: User registration)" \
  "post:reset-password/{token} (body: password:str) (desc: Reset password)" \
  --controller-inherits AuthBaseController \
  --before "rate_limit:Apply rate limiting" \
  --after "log_auth_attempt:Log authentication attempt"
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
metro generate model Post author:ref:User
```

This will generate a `Post` model with an `author` field referencing the `User` model.

- **Many-to-Many Relationship**: Use `list:` and `ref:` together.

```
metro generate model Student courses:list:ref:Course
```

This will generate a `Student` model with a `courses` field that is a list of references to `Course` models.

### Field Modifiers
`?` and `^`are used to define a field as optional or unique respectively.

#### Optional Field: 
Append `?` to the field name to mark it as optional.

```
metro generate model User email?:str
```

This will generate a `User` model with an optional `email` field.

#### Unique Field: 
Append `^` to the field name to specify it as unique.

```
metro generate model User username^:str
```

This will generate a `User` model with a unique `username` field.

#### Field Choices:
For string fields that should only accept specific values, use the `choices` syntax with optional default value (marked with `*`):

```bash
# required role with no default value (role must be specified)
metro generate model User role:string:choices[user,admin]

# optional role with default value of 'user'
metro generate model User role:string:choices[user*,admin]  # note it would be redundant to add ? here since the default value makes it optional
```

You can combine these modifiers to create fields with multiple attributes:

```bash
metro generate model Product \
  sku^:str \                                  # unique identifier 
  name^:str \                                 # unique name
  price:float \                               # no modifier makes price required
  description?:str \                          # optional description
  status:string:choices[active*,discontinued] # enum with default value
```

#### Indexes:
Use the `--index` flag to create indexes for more efficient querying. The syntax supports various MongoDB index options:

Note that built in timestamp fields like `created_at`, `updated_at`, and `deleted_at` are automatically indexed and don't need to be specified.

```bash
# Basic single field index
metro generate model User email:str --index "email"

# Basic compound index
metro generate model Product name:str price:float --index "name,price"

# Unique compound index
metro generate model Product name:str price:float --index "name,price[unique]"

# Compound index with descending order and sparse option
metro generate model Order total:float --index "created_at,total[desc,sparse]"  # note that created_at is a built-in field so it doesn't need to be defined explicitly
```

You can specify multiple compound indexes:
    
```bash
metro generate model Product \
  name:str \
  price:float \
  category:str \
  --index "name,price[unique]" \
  --index "category,created_at[desc,sparse]"
```

This will generate:

```python
class Product(BaseModel):
    name = StringField(required=True)
    price = FloatField(required=True)
    category = StringField(required=True) 
    created_at = DateTimeField(required=True)

    meta = {
        "collection": "product",
        'indexes': [
            {
                'fields': ['name', 'price'],
                'unique': True
            },
            {
                'fields': ['-category', '-created_at'],
                'sparse': True
            }
        ],
    }
```
    
#### Index Options:

* `unique`: Ensures no two documents can have the same values for these fields
* `sparse`: Only includes documents in the index if they have values for all indexed fields
* `desc`: Creates the index in descending order (useful for sorting)

## Specialty Field Types

### Hashed Field 
`hashed_str` is a special field type that automatically hashes the value before storing it in the database.

```
metro generate model User name:str password_hashed:str
```

This will generate a `User` model with a `password` field stored as a hashed value.

### File Fields
`file` and `list:file` are special field types for handling file uploads. They automatically upload
files to the specified storage backend (local filesystem, AWS S3, etc.) and store the file path and file metadata in the database.

- **`file`**: Generates a single `FileField` on the model.
- **`list:file`**: Generates a `FileListField`, allowing multiple files.

Example usage:
```
metro generate model User avatar:file
metro generate model Post attachments:list:file
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
    attachments: list[UploadFile] = File(None),
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
from metro.controllers import Controller, before_request, after_request
from metro.exceptions import UnauthorizedError
from metro import Request

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

## Rate Limiting

Metro includes a built-in rate limiter that can be applied to specific routes or controllers.

### Throttling Controller Endpoints:

To apply rate limiting to a controller endpoint, use the `@throttle` decorator:

```python
from metro.rate_limiting import throttle

class UserController(Controller):
    @get('/users/{id}')
    @throttle(per_second=1, per_minute=10)
    async def get_user(self, request: Request, id: str):
        return {"id": id}
```

### Throttling Routes

To apply rate limiting to a specific route, pass the `Throttler` class as a dependency:

```python
from metro.rate_limiting import Throttler

@app.get("/users/{id}", dependencies=[Depends(Throttler(per_second=1, per_minute=10))]
async def get_user(request: Request, id: str):
    return {"id": id}
```

### Customizing Rate Limiting

Parameters:
- `name`: Namespace for the rate limiter.
- `limits`: Compound rate limit definition. Can be a RateLimits() object or a function that returns a RateLimits() object.
- `per_second`: Number of requests allowed per second.
- `per_minute`: Number of requests allowed per minute.
- `per_hour`: Number of requests allowed per hour.
- `per_day`: Number of requests allowed per day.
- `per_week`: Number of requests allowed per week.
- `per_month`: Number of requests allowed per month.
- `backend`: Rate limiting backend (e.g., `InMemoryRateLimiterBackend`, `RedisRateLimiterBackend`). Defaults to InMemoryRateLimiterBackend.
- `callback`: Callback function to execute when the rate limit is exceeded. (request, limited, limit_info) => .... Defaults to raising a `TooManyRequestsError` if limit is exceeded.
- `key`: Custom key function to generate a unique key for rate limiting. (request) => str. Defaults to request IP.
- `cost`: Custom cost function to calculate the cost of a request. (request) => int. Defaults to 1.

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

## SMS Sending
Easily send SMS messages using the built-in `SMSSender` class, which supports multiple SMS providers like Twilio and Vonage.

1. Add the provider credentials to the environment variables or config file:
```
# For Twilio
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# For Vonage
VONAEG_API_KEY=your_api_key
VONAGE_API_SECRET=your_api_secret
VONAGE_PHONE_NUMBER=+1234567890
```

2. Send an SMS message:
```python
sms_sender = SMSSender()  # provider will be automatically detected based on environment variables but can also be specified explicitly

sms_sender.send_sms(
    source="+1234567890",
    recipients=["+1234567891"],
    message="This is a test SMS message!",
)
```
---

## Database Management

Metro provides commands to manage your MongoDB database.

### Starting a Local MongoDB Instance

To start a local MongoDB instance for development:

```
metro db up
```

### Stopping the Local MongoDB Instance

To stop the local MongoDB instance:

```
metro db down
```

### Running MongoDB in a Docker Container

You can also specify the environment and run MongoDB in a Docker container:

```
metro db up --env production --docker
```

---

## Configuration

Environment-specific configuration files are located in the `config` directory:

- `config/development.py`
- `config/production.py`

Here you can set your `DATABASE_URL`, API keys, and other settings that vary between environments.

---

## Admin Panel

Metro includes a built-in admin panel. You can view this at `/admin`

You can disable this or change the admin route in the `config/development.py` or `config/production.py` file:

```python
ENABLE_ADMIN_PANEL = False
ADMIN_PANEL_ROUTE_PREFIX = "/admin-panel"
```

---

## Conductor

"If the Rails generator was powered by an LLM"

### Configuring API Keys for Conductor

Add your OpenAI/Anthropic API keys to power Conductor

`metro conductor setup add-key`

`metro conductor setup list-keys`

`metro conductor setup remove-key`

### Initializing a New Project

Generate the starter code for a Metro project from a project description using the `init` command:

`metro conductor init <project_name> <description>`

ex.

`metro conductor init my-app "A social media app where users can make posts, comment, like, and share posts, and follow other users."`

---

## Documentation and Help

- **API Documentation**: http://localhost:8000/docs
- **CLI help**: `metro --help`

For guides, tutorials, and detailed API references, check out the Metro documentation site.

---

## License

Metro is open-source software licensed under the MIT license.
