## Creating Resources

Let's create a User resource with some fields:

```bash
metro generate scaffold User username^:str email^:str password_hash:hashed_str name:str bio?:str avatar?:file posts:list:ref:Post
```` 

:::info What did we just do?
The structure for a scaffold generator is this `metro generate scaffold ResourceName field1_name:field1_type field2_name:field2_type ...`

The suffix `^` at the end of a name marks it as unique (no 2 users can share the same username or email)

The suffix `?` marks it as optional (users can choose to leave their bio blank)

`list:ref:Post` means this field will be a list of references to the Post model (which we still need to create)

`hashed_str` is a special field type which automatically hashes a string before saving it in the db

`file` is a special field type which will save the actual file data to our backend of choice (filesystem, s3, etc.) and the metadata pointer in the db
:::

This command:
1. Creates a Post model in `app/models/post.py`
2. Generates a PostsController in `app/controllers/posts_controller.py`
3. Sets up all necessary CRUD routes

The generated model looks like this:

```python
from metro.models import *

class User(BaseModel):
    username = StringField(required=True, unique=True)
    email = StringField(required=True, unique=True)
    password_hash = HashedField(required=True)
    name = StringField(required=True)
    bio = StringField()
    avatar = FileField(required=False)
    posts = ListField(ReferenceField('Post'), default=[])
```

And the controller:

```python
from metro import Request, Controller
from app.models.user import User
...

class UserssController(Controller):
    @get('/users')
    async def index(self, request: Request):
        items = User.find()
        return [item.to_dict() for item in items]

    @get('/users/{id}')
    async def show(self, request: Request, id: str):
        item = User.find_by_id(id=id)
        if item:
            return item.to_dict()
        raise NotFoundError('User not found')

    # Other CRUD endpoints...
```

<br/>

Now, let's create a Post resource with some string content and an optional image. 

```bash
metro g scaffold Post content:str image?:file author:ref:User
```

(You can just use `g` as a shorthand for `generate`)


## Setting up the Admin Panel

If we intend on `User` being the registered Admin Auth Class, we don't explicitly need to declare it. Otherwise, we need to set `ADMIN_AUTH_CLASS = "CustomUser"` as a config variable.

To set up auth to enable us to sign-in to the admin panel, we need to write a couple of methods in our User model: `authenticate`, `get_auth_token`, and `verify_auth_token`. We'll just keep them simple for now.
```python
from metro.models import *
from typing import Optional
import json

class User(BaseModel):
    username = StringField(required=True, unique=True)
    email = StringField(required=True, unique=True)
    password_hash = HashedField(required=True)
    name = StringField(required=True)
    bio = StringField()
    avatar = FileField(required=False)
    posts = ListField(ReferenceField('Post'), default=[])

    @classmethod
    def authenticate(cls, identifier: str, password: str) -> Optional["User"]:
        user = cls.find_one(username=identifier) or cls.find_one(email=identifier)
        if user and user.password_hash.verify(password):
            return user
        return None

    def get_auth_token(self) -> str:
        # dummy method for now, the real method would create an actual JWT token
        return json.dumps({"user_id": str(self.id)})

    @classmethod
    def verify_auth_token(cls, token: str) -> Optional["User"]:
        # dummy method for now, the real method would try to decode an actual JWT token
        data = json.loads(token)
        return cls.find_by_id(data["user_id"])
        
```

### Creating a SuperUser

Let's create a user account with superuser permissions to access the admin panel:
```bash
metro admin createsuperuser
# This will prompt you for all necessary fields including username, email, and password
```

Now, we should be able to sign in to the admin panel at [localhost:8000/admin](http://localhost:8000/admin) using the credentials we just created.


### Saving Ourselves Some Boilerplate

To save ourselves a lot of authentication boilerplate, we should also set our User model to inherit from `metro.auth.UserBase`.

```python
from metro.models import *
from metro.auth import UserBase

class User(UserBase):
    name = StringField(required=True)
    bio = StringField(required=False)
    avatar = FileField(required=False)
    posts = ListField(ReferenceField('Post'), default=[])

    """ 
    # Fields defined in UserBase class, we don't need to redefine them
    username = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    password_hash = HashedField(required=True)
    is_staff = BooleanField(default=False)        # Can access admin site
    is_superuser = BooleanField(default=False)    # Has all permissions
    
    # Methods defined in UserBase class, we don't need to redefine them
    def authenticate(cls, identifier: str, password: str) -> Optional["User"]:
        ...
        
    def get_auth_token(self) -> str:
        ...
        
    def verify_auth_token(cls, token: str) -> Optional["User"]:
        ...
    """
```
