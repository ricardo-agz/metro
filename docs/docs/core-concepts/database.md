---
sidebar_position: 4
---

# Database

Metro uses MongoDB as its database, providing a powerful ODM (Object-Document Mapper) through MongoEngine. This guide covers database setup, configuration, and management.

## Database Setup

### Local Development

Start a local MongoDB instance:

```bash
# Start MongoDB
metro db up

# Stop MongoDB
metro db down

# Check MongoDB status
metro db status
```

### Using Docker

Run MongoDB in a Docker container:

```bash
# Start MongoDB with Docker
metro db up --docker

# Stop MongoDB container
metro db down --docker
```

## Configuration

Configure your database connection in the environment config files:

```python
# config/development.py
DATABASE_URL = "mongodb://localhost:27017/my_app_dev"

# config/production.py
DATABASE_URL = os.getenv("DATABASE_URL")
```

## Basic Database Operations

### Finding Documents

```python
# Find by ID
user = User.find_by_id("12345")

# Find one document
user = User.find_one(email="example@email.com")

# Find many documents
active_users = User.find_many(active=True)

# Find with conditions
adult_users = User.find_many(age__gte=18)
```

### Creating Documents

```python
# Create a single document
user = User(name="John Doe", email="john@example.com")
user.save()

# Create multiple documents
users = User.create_many([
    {"name": "John", "email": "john@example.com"},
    {"name": "Jane", "email": "jane@example.com"}
])
```

### Updating Documents

```python
# Update a single document
user = User.find_by_id("12345")
user.name = "New Name"
user.save()

# Update multiple documents
User.update_many(
    {"active": False},  # query
    {"$set": {"status": "inactive"}}  # update
)
```

### Deleting Documents

```python
# Delete a single document
user = User.find_by_id("12345")
user.delete()

# Delete multiple documents
User.delete_many(active=False)
```

## Querying

### Query Operators

Metro supports MongoDB query operators:

```python
# Greater than
User.find_many(age__gt=21)

# Less than
User.find_many(age__lt=65)

# In list
User.find_many(status__in=["active", "pending"])

# Regular expression
User.find_many(email__regex=r".*@gmail\.com")

# Exists
User.find_many(profile_picture__exists=True)
```

### Complex Queries

```python
# AND conditions
users = User.find_many(
    age__gte=18,
    active=True,
    country="US"
)

# OR conditions
from mongoengine.queryset.visitor import Q

users = User.find_many(
    Q(age__gte=18) | Q(parental_consent=True)
)
```

### Aggregation

```python
from mongoengine.queryset.visitor import Q

# Count
active_count = User.find_many(active=True).count()

# Distinct
countries = User.find_many().distinct("country")

# Aggregate
result = Post.objects.aggregate([
    {"$group": {
        "_id": "$author",
        "total_posts": {"$sum": 1}
    }}
])
```

## Relationships

### One-to-Many Relationships

```python
class User(BaseModel):
    name = StringField()

class Post(BaseModel):
    title = StringField()
    author = ReferenceField(User, required=True)

# Usage
user = User.find_by_id("12345")
posts = Post.find_many(author=user)
```

### Many-to-Many Relationships

```python
class Course(BaseModel):
    name = StringField()

class Student(BaseModel):
    name = StringField()
    courses = ListField(ReferenceField(Course))

# Usage
student = Student.find_by_id("12345")
for course in student.courses:
    print(course.name)
```

## Indexes

```python
class User(BaseModel):
    email = StringField(required=True, unique=True)
    username = StringField(required=True, unique=True)
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'indexes': [
            'email',  # Single field index
            ('username', 'created_at'),  # Compound index
            {
                'fields': ['$name', '$email'],  # Text index
                'default_language': 'english'
            }
        ]
    }
```

## Database Administration

### Database Status

```bash
# Check database status
metro db status

# Get database statistics
metro db stats
```

### Database Backup

```bash
# Backup database
metro db backup

# Restore database
metro db restore backup_file.dump
```

## Configuration Options

Common database configuration options:

```python
# config/development.py
DATABASE_URL = "mongodb://localhost:27017/my_app_dev"
DATABASE_MAX_POOL_SIZE = 100
DATABASE_MIN_POOL_SIZE = 10
DATABASE_MAX_IDLE_TIME_MS = 10000
DATABASE_CONNECT_TIMEOUT_MS = 20000

# Enable query logging for development
DATABASE_QUERY_LOGGING = True
```

## Next Steps

- Learn about [Models](models) in detail
- Explore [Controllers](controllers) for API creation
- Understand [Project Structure](../getting-started/project-structure)