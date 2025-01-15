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

* Format: `http_method:path (query: params) (body: params) (desc: description)`
* Example: `-a "get:search (query: term:str) (desc: Search users)"`


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
  -a "get:search (query: term:str,min_price:float,max_price:float) (desc: Search products)" \
  -a "post:bulk-update (body: ids:list,price:float) (desc: Update multiple products)"
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
  -a "post:process/{id} (body: payment_method:str) (desc: Process order payment)" \
  -a "get:user/{user_id} (query: status:str,date_from:datetime) (desc: Get user orders)" \
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
`?`, `^`, `@` are used to define a field as optional, unique, or an index respectively.

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

#### Indexed Field:
Append `@` to the field name to create an index for that field.

```bash
metro generate model Product price@:float category@:str
```

This will generate a `Product` model with indexed `price` and `category` fields for faster querying and filtering.

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
  price@:float \                              # indexed for price filtering/sorting
  stock@:int \                                # indexed for inventory queries
  category@:str \                             # indexed for category filtering
  description?:str \                          # optional description
  status:string:choices[active*,discontinued] # enum with default value
```

#### Compound Indexes:
Use the `--index` flag to create compound indexes that span multiple fields. The syntax supports various MongoDB index options:

```bash
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
