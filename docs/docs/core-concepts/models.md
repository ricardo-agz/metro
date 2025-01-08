---
sidebar_position: 1
---

# Models

Models in PyRails are MongoDB documents powered by MongoEngine ODM. They provide an elegant and powerful way to interact with your database.

## Generating Models

The easiest way to create a new model is using the PyRails generator:

```bash
pyrails generate model User name:str email:str age:int
```

This creates a new model file `app/models/user.py` with basic field definitions.

## Field Types

PyRails supports a variety of field types to handle different kinds of data.

### Basic Field Types

| Type | Python Type | Description |
|------|-------------|-------------|
| `str` | `str` | String field |
| `int` | `int` | Integer field |
| `float` | `float` | Floating point field |
| `bool` | `bool` | Boolean field |
| `datetime` | `datetime` | DateTime field |
| `date` | `date` | Date field |
| `dict` | `dict` | Dictionary field |
| `list` | `list` | List field |

Example:
```bash
pyrails generate model Product \
    name:str \
    price:float \
    in_stock:bool \
    created_at:datetime
```

### Special Field Types

#### Reference Fields (Relationships)
Use `ref` to create relationships between models:

```bash
# Create a one-to-many relationship
pyrails generate model Post author:ref:User title:str content:str

# Create a many-to-many relationship
pyrails generate model Student courses:list:ref:Course name:str
```

This generates models with proper relationships:

```python
# Generated Post model
class Post(BaseModel):
    author = ReferenceField(User, required=True)
    title = StringField(required=True)
    content = StringField(required=True)

# Generated Student model
class Student(BaseModel):
    courses = ListField(ReferenceField(Course))
    name = StringField(required=True)
```

#### File Fields
PyRails provides special fields for handling file uploads:

```bash
# Single file upload
pyrails generate model Profile avatar:file bio:str

# Multiple file uploads
pyrails generate model Gallery images:list:file title:str
```

This creates models with file handling capabilities:

```python
class Profile(BaseModel):
    avatar = FileField()
    bio = StringField(required=True)

class Gallery(BaseModel):
    images = FileListField()
    title = StringField(required=True)
```

#### Hashed String Fields
For sensitive data like passwords:

```bash
pyrails generate model User email:str password:hashed_str
```

The generated model will automatically hash sensitive data:

```python
class User(BaseModel):
    email = StringField(required=True)
    password = HashedStringField(required=True)
```

## Field Modifiers

### Optional Fields
Append `_` to make a field optional:

```bash
pyrails generate model User \
    username:str \
    middle_name_:str  # Optional field
```

Generated model:
```python
class User(BaseModel):
    username = StringField(required=True)
    middle_name = StringField(required=False)
```

### Unique Fields
Append `^` to make a field unique:

```bash
pyrails generate model User \
    email^:str  # Unique field \
    username^:str  # Another unique field
```

Generated model:
```python
class User(BaseModel):
    email = StringField(required=True, unique=True)
    username = StringField(required=True, unique=True)
```

## Working with Models

### Basic CRUD Operations

```python
# Create
user = User(name="John Doe", email="john@example.com")
user.save()

# Read
user = User.find_by_id(id="123")
users = User.find_many(age__gt=18)

# Update
user.name = "Jane Doe"
user.save()

# Delete
user.delete()
```

### File Handling

```python
# Setting a single file
@put('/users/{id}/update-avatar')
async def update_avatar(self, id: str, avatar: UploadFile = File(None)):
    user = User.find_by_id(id=id)
    if avatar:
        user.avatar = avatar
        user.save()  # This uploads the file and saves the metadata
    return user.to_dict()

# Working with multiple files
@post('/galleries/{id}/add-images')
async def add_images(self, id: str, images: List[UploadFile] = File(None)):
    gallery = Gallery.find_by_id(id=id)
    if images:
        gallery.images.extend(images)
        gallery.save()  # This uploads all files and saves their metadata
    return gallery.to_dict()
```

## Model Validation

PyRails models automatically validate data before saving:

```python
class Product(BaseModel):
    name = StringField(required=True, min_length=2)
    price = FloatField(required=True, min_value=0)
    sku = StringField(required=True, regex=r'^[A-Z]{2}\d{6}$')

# This will raise a ValidationError
product = Product(name="A", price=-10, sku="invalid")
product.save()  # Raises ValidationError
```

## Model Hooks

You can define hooks that run before or after certain operations:

```python
class User(BaseModel):
    email = StringField(required=True)
    last_login = DateTimeField()

    def before_save(self):
        if self._created:  # New document
            self.send_welcome_email()

    def after_save(self):
        self.clear_cache()
```

## Next Steps

- Learn about [Controllers](../tutorial/controllers) to handle HTTP requests
- Explore [File Storage Configuration](../features/file-handling) for file upload settings
- See how to use models with [Rate Limiting](../features/rate-limiting)