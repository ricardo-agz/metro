import time

import click

from conductor.generator.init_project.design_draft import init_project_design_draft
from conductor.llms import completion
from conductor.utils import extract_xml_content, Spinner

PROMPT = """
You are Conductor, an expert AI in designing backend APIs for projects using Metro API, a batteries-included Python web 
framework, similar to Django. Your task is to generate Metro commands to implement the starting scaffold for a given 
project based on a project description and a high-level design draft.

You will be provided with two inputs:
1. <project_description>{{PROJECT_DESCRIPTION}}</project_description>
This is a brief description of the project's main purpose and features.

2. <design_draft>{{DESIGN_DRAFT}}</design_draft>
This is a detailed design draft that includes information about the application overview, user stories, data schema, 
API endpoints, and other considerations.

Carefully analyze the project description and design draft. Pay special attention to the data schema and API endpoints 
sections, as these will be crucial for generating the appropriate Metro commands.

Based on your analysis, generate a list of Metro commands to scaffold the initial structure of the project. Follow 
these guidelines:

1. Start with model generation commands, as they form the foundation of the data structure.
2. Follow with controller generation commands to create the necessary route handlers.
3. Use scaffold generation commands when appropriate to create both models and controllers for primary resources.
4. Ensure that all required fields, relationships, and special field types are correctly specified in the commands.
5. Order the commands logically, typically starting with user-related models and progressing to dependent resources.

Provide your output in the following format:
<metro_commands>
[List your generated Metro commands here, one per line]
</metro_commands>

Here is the relevant documentation from the Metro API framework docs regarding generator commands:
<metro_generator_documentation>
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


## Generating Models and Controllers

You can also generate models and controllers individually.

### Generating a Model

To generate a `Comment` model with `post_id`, `author`, and `content` fields:

```
metro generate model Comment post_id:str author:str content:str
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
`_`, `^` are used to define a field as optional or unique.

#### Optional Field: 
Append `_` to the field name to mark it as optional.

```
metro generate model User email_:str
```

This will generate a `User` model with an optional `email` field.

#### Unique Field: 
Append `^` to the field name to specify it as unique.

```
metro generate model User username^:str
```

This will generate a `User` model with a unique `username` field.

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
</metro_generator_documentation>

Remember to adhere to Metro syntax and best practices:
- Use `metro generate model` for creating models
- Use `metro generate controller` for creating controllers
- Use `metro generate scaffold` for creating both models and controllers for a resource
- Specify field types correctly (str, int, bool, datetime, etc.)
- Use `ref:` for relationships between models
- Use `list:` for array fields
- Use `^` for unique fields and `_` for optional fields
- Use `hashed_str` for password fields
- Use `file` or `list:file` for file upload fields
- Timestamp fields for creation and last update like created_at and updated_at are automatically added and are not 
required in the model definition.

Ensure that your generated commands cover all necessary models, controllers, and relationships described in the design 
draft. If you encounter any ambiguities or need to make assumptions, note them briefly after the command list.

Remember your final output for the Metro commands should be enclosed in the `<metro_commands>` XML tags.
"""


FEEDBACK_PROMPT = """
The user has chosen to provide feedback on the generated Metro commands. Your task is to review the provided feedback
and make any necessary adjustments to the Metro commands based on the feedback.

The user has chosen not to accept the generated Metro commands as they are and has provided the following feedback:
<user_feedback>{{FEEDBACK}}</user_feedback>

Your output should be a revised, full list of the entire set of Metro commands to scaffold the initial structure of the
project.

Remember your final output for the Metro commands should be enclosed in the `<metro_commands>` XML tags.
"""


def init_project_generator_commands(
    description: str, design_draft: str, feedback: list[tuple[list[str], str]] = None
) -> list[str]:
    prompt = PROMPT.replace("{{PROJECT_DESCRIPTION}}", description).replace(
        "{{DESIGN_DRAFT}}", design_draft
    )

    messages = [
        {"role": "user", "content": prompt},
    ]
    if feedback:
        for prev_commands, user_feedback in feedback:
            prev_commands_str = "\n".join(prev_commands)
            messages.append({"role": "assistant", "content": prev_commands_str})

            feedback_prompt = FEEDBACK_PROMPT.replace("{{FEEDBACK}}", user_feedback)
            messages.append({"role": "user", "content": feedback_prompt})

    completion_response = completion(
        model="claude-3-5-sonnet-20241022",
        messages=messages,
    )

    # Extract the completion content
    completion_content = completion_response.choices[0].message.content

    commands_str = extract_xml_content(completion_content, "metro_commands")
    commands = [
        c for c in commands_str.split("\n") if c.strip() and not c.startswith("#")
    ]

    return commands


def handle_feedback_loop(
    prompt: str, design_draft: str, initial_commands: list[str]
) -> list[str]:
    """Handle the feedback loop for generator commands"""
    feedback: list[tuple[list[str], str]] = []
    current_commands = initial_commands

    while True:
        click.echo("\nGenerated Metro commands:")
        for cmd in current_commands:
            click.echo(click.style(f"  {cmd}", fg="bright_blue"))

        if click.confirm("\nAccept these commands?", default=True):
            return current_commands

        feedback_text = click.prompt("Please provide specific feedback")
        feedback.append((current_commands, feedback_text))

        spinner = Spinner(message="Regenerating commands based on feedback")
        spinner.start()
        current_commands = init_project_generator_commands(
            prompt, design_draft, feedback
        )
        spinner.stop()


def main():
    description = "Twitter-like social media platform"
    design_draft = init_project_design_draft(description)
    print("Design Draft:")
    print(design_draft)
    print("-----------------")

    feedback = []
    while True:
        commands = init_project_generator_commands(description, design_draft, feedback)
        for c in commands:
            print(c)

        accept = input("Accept the generated commands? (y/n): ")
        if accept.strip().lower() == "n":
            specific_feedback = input("Provide feedback: ")
            feedback.append((commands, specific_feedback))
        else:
            break


if __name__ == "__main__":
    main()
