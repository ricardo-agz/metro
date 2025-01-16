import click
import os

from conductor.generator.init_project.design_draft import init_project_design_draft
from conductor.llms import completion
from conductor.utils import extract_xml_content, Spinner


curr_path = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(curr_path, "metro_docs/generator_commands.md"), "r") as file:
    METRO_GENERATOR_COMMANDS_DOCS = file.read()

with open(os.path.join(curr_path, "./metro_docs/base_model_examples.md"), "r") as file:
    METRO_BASE_MODEL_EXAMPLES = file.read()

with open(os.path.join(curr_path, "metro_docs/controller_lifecycle.md"), "r") as file:
    METRO_CONTROLLER_LIFECYCLE_DOCS = file.read()


PROMPT = """
You are Conductor, an expert AI in designing backend APIs for projects using Metro API, a batteries-included Python web 
framework, similar to Django. Your task is to generate Metro commands to implement the starting scaffold for a given 
project based on a project description and a technical design doc.

You will be provided with two inputs:
1. <project_description>{{PROJECT_DESCRIPTION}}</project_description>
This is a brief description of the project's main purpose and features.

2. <design_draft>{{DESIGN_DRAFT}}</design_draft>
This is a detailed design draft that includes information about the application overview, user stories, data schema, 
API endpoints, and other considerations.

Read through the provided Metro documentation which will be required to generate the output commands

<metro_documentation_and_features>
Metro Framework Documentation and Features

1. Generator Commands Documentation
This documentation describes the available Metro generator commands and their options. Your task is to:
- Use these commands to create the project scaffold
- Follow the syntax exactly as shown
- Choose the appropriate generator type for each resource

<metro_generator_documentation>
{{METRO_GENERATOR_COMMANDS_DOCS}}
</metro_generator_documentation>

The above documentation outlines the core generator commands available in Metro. When generating your commands:
- Pay attention to the field type syntax and modifiers
- Note the available options for each generator type
- Review the examples for proper command structure
- Understand how scaffolds differ from individual generators

Remember to adhere to Metro syntax and best practices:
- Use `metro generate model` for creating models
- Use `metro generate controller` for creating controllers
- Use `metro generate scaffold` for creating both models and controllers for a resource
- Specify field types correctly (str, int, bool, datetime, etc.)
- Use `ref:` for relationships between models
- Use `list:` for array fields
- Use `^` for unique fields
- Use `?` for optional fields
- Use `hashed_str` for password fields
- Use `file` or `list:file` for file upload fields
- Timestamp fields for creation and last update like created_at and updated_at are automatically added and are not 
required in the model definition.
- All custom, non-crud routes in controllers or scaffolds must contain an action name and a brief description using the 
  appropriate syntax:
    * Format: `http_method:path (query: params) (body: params) (desc: description) (action_name: action_name)`
    * Example: `-a "get:search (query: term:str) (desc: Search users) (action_name: search_users)"`

2. Controller Lifecycle Management
<metro_controller_lifecycle>
{{METRO_CONTROLLER_LIFECYCLE_DOCS}}
</metro_controller_lifecycle>

The controller lifecycle documentation above is crucial for:
- Understanding how before_request and after_request hooks work
- Planning your controller inheritance hierarchy
- Implementing authentication and authorization efficiently
- Avoiding code duplication across controllers

Key Pattern: If you find yourself repeating the same hooks (like authentication checks) across multiple controllers:
1. Create a base controller with the shared functionality
2. Use meaningful names for base controllers (e.g., "AuthenticatedController" not "BaseController")
3. Have specific controllers inherit from this base
4. Remember that inherited hooks run on EVERY request to controllers that inherit them

3. Built-in Base Models
<metro_base_model_examples>
{{METRO_BASE_MODEL_EXAMPLES}}
</metro_base_model_examples>

Metro provides built-in base models to reduce boilerplate code. Currently available:
* UserBase - For user authentication and management

UserBase Model Details:
```python
class UserBase(BaseModel):
    username = StringField(required=True, unique=True, max_length=150)
    email = EmailField(required=True, unique=True)
    password_hash = HashedField(required=True)
    is_staff = BooleanField(default=False)  # Can access admin site
    is_superuser = BooleanField(default=False)  # Has all permissions
    last_login = DateTimeField()
    
    @classmethod
    def find_by_username(cls, username: str) -> Optional["UserBase"]:
        '''Find a user by username'''
        ...

    @classmethod
    def authenticate(cls, identifier: str, password: str) -> Optional["UserBase"]:
        '''Authenticate a user by username or email and password'''
        ...

    def get_auth_token(self, expires_in: int = 3600, secret_key: str = None) -> str:
        '''
        Generate a JWT token for the user

        Args:
            expires_in: Token expiration time in seconds (default: 1 hour)
            secret_key: The secret key to sign the token (default: config.JWT_SECRET_KEY)
        '''
        ...

    @classmethod
    def verify_auth_token(cls, token: str, secret_key: str = None) -> Optional["UserBase"]:
        '''
        Verify a JWT token and return the corresponding user

        Args:
            token: The JWT token to verify
            secret_key: The secret key used to sign the token

        Returns:
            The user object if token is valid, None otherwise
        '''
        ...
```

When using UserBase:

Inherit from it using --model-inherits UserBase
Do NOT redefine fields already provided by UserBase (username, email, password_hash, etc.)
Only add fields specific to your application's user requirements
UserBase automatically provides authentication and token management methods

Example Usage:
# Correct: Only adding fields not in UserBase
`metro generate scaffold User additional_field:str --model-inherits UserBase`

# Incorrect: Redefining UserBase fields
`metro generate scaffold User username:str email:str password:str  # Don't do this!`

Inheritance Rules:

You can ONLY inherit from:
* Models provided by the Metro framework (currently only UserBase)
* Models you have already generated in your command sequence


Never inherit from models that haven't been generated yet or aren't part of the Metro framework.
</metro_documentation_and_features>

Provide your response in the following format:

<initial_thoughts>

1. High-level Generation strategy
    <required_models> (all models, not just non-scaffolded ones)
    [List all models defined in the technical design doc and their respective fields]
    </required_models>
    
    <api_routes_by_controller> (all API routes and all controllers, not just non-scaffolded ones)
    [Map each of the api endpoints defined in the technical design doc to an appropriate associated controller and 
    give an action name for each endpoint. The API endpoints in the technical design doc should closely align to their 
    controller route defined here, minor changes are allowed only if they improve code structure or readability or 
    best practices. Listing each api route, write the controller it belongs to, the http method, the route, any query
    or body parameters, the action name, and a very brief description of what the action does. 
    For example:
    GET /api/posts -> PostsController, get, /posts, get_posts, List all Posts
    GET /api/posts/{id} -> PostsController, get, /posts/{id}, get_post, Get a specific Post by ID]
    </api_routes_by_controller>

    <scaffolds> (list of names of resources where their model and controller should be generated together as a scaffold)
    [resource for resource in required_models if ResourceNameController exists in api_routes_by_controller]
    </scaffolds>
    
2. Additional Functionality
    <before_request_hooks> (optional)
    [For each controller defined in api_routes_by_controller, think about any checks or middleware that would be needed
    before the request is handled]
    </before_request_hooks>
    
    <after_request_hooks> (optional)
    [For each controller defined in api_routes_by_controller, think about any cleanup or logic that would need to be 
    executed synchronously after the request is handled but before it is returned to the client]
    </after_request_hooks>
    
3. Best Practices
    <DRY_check> (optional)
    [Think about any shared functionality that is repeated across multiple controllers, could this be abstracted into an
    appropriate base controller that the other controllers inherit from? If this was already accounted for in the 
    sections above, you can just mention that here]
    </DRY_check>
    
4. Reflection
    <revisions>
    [If you discovered any repeated shared functionality in the DRY check that was solved by a new base controller you 
    haven't generated yet, include that here, along with any changes that would happen to the existing controllers.
    Carefully look at what you've thought of so far in this initial thoughts section and carefully re-read the design 
    doc. Does your current plan cover all the requirements? Are there any changes you'd like to make?]
    </revisions>    
</initial_thoughts>

Things to consider in your commands:


<rough_draft_commands>
# Commands should be ordered by dependencies, with base/auth controllers first if needed
# Include brief comments explaining key decisions
[List your Metro generation commands here, one per line]
</rough_draft_commands>

<reflection>
Carefully re-read and analyze the technical design doc. 
Go over all required functionalities, are they all handled by an endpoint included in the generated commands?
Go over every API route, are they all covered in the generated commands? [Explicitly write out each route in the design
doc and check if it's covered in the generated commands like this: GET /api/posts -> Post scaffold (get_posts), 
GET /api/posts/{id} -> Post scaffold (get_post), etc.]
Go over every model in the data schema of the design doc, are they all generated? Are all the fields correct? Are all:
    - unique fields marked with the `^` suffix?
    - optional fields marked with the `?` suffix?
    - indexes defined correctly?
    - relationships between models defined correctly?
    - file fields handled by the `file` or `list:file` field type instead of an individual url string field? (unless specifically specified otherwise in the <project_description>
Go over each of the generated commands, do they all:
    - follow the Metro conventions and syntax?
    - have descriptive names?
    - not reference models or controllers that haven't been generated yet or aren't part of the Metro framework?
Go over the order of the commands, are they generated in the correct order based on dependencies?
Re-read the Metro documentation, are we making use of all the features that Metro provides? For example:
    - hashed_str for password fields
    - file or list:file for file upload fields
    - user authentication is logic is inherited from the UserBase model (unless specifically specified otherwise in the <project_description>
Re-read the Metro documentation and each of the generated commands. Do they all follow the correct syntax?
</reflection>

<optimizations>
[If you have any suggestions for optimizations or improvements that can be achieved through changes to the Metro 
generation commands (and not through external logic outside of the scope of Metro commands), list them here.
Write the bottleneck, how it can be optimized, and what the changes required to the Metro commands are.]
</optimizations>

<metro_commands>
[Your final, validated Metro commands here, one per line. If no changes are needed, copy the rough draft commands here]
</metro_commands>

<user_message>
[Your final message to the user explaining the commands you have generated and any design decisions you made.]
</user_message>

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


def extract_commands(commands_str: str) -> list[str] | None:
    """
    Extract commands from a string, properly handling multi-line commands using backslash.

    Args:
        commands_str: String containing Metro commands, potentially multi-line

    Returns:
        List of complete commands
    """
    commands = []
    current_command = []

    # Split into lines and clean each line
    lines = [line.strip() for line in commands_str.split("\n")]

    if not any(["metro generate" in line for line in lines]):
        return None

    for line in lines:
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # If line ends with backslash, accumulate into current command
        if line.endswith("\\"):
            current_command.append(line[:-1].strip())  # Remove backslash and whitespace
        else:
            # Add this line to current command and complete it
            current_command.append(line)

            # Join the accumulated command parts with spaces
            full_command = " ".join(current_command).strip()
            if full_command:  # Only add non-empty commands
                commands.append(full_command)
            current_command = []  # Reset for next command

    # Handle case where last command ends with backslash
    if current_command:
        full_command = " ".join(current_command).strip()
        if full_command:
            commands.append(full_command)

    return commands


def init_project_generator_commands(
    description: str, design_draft: str, feedback: list[tuple[list[str], str]] = None
) -> list[str]:
    prompt = (
        PROMPT.replace("{{PROJECT_DESCRIPTION}}", description)
        .replace("{{DESIGN_DRAFT}}", design_draft)
        .replace("{{METRO_GENERATOR_COMMANDS_DOCS}}", METRO_GENERATOR_COMMANDS_DOCS)
        .replace("{{METRO_BASE_MODEL_EXAMPLES}}", METRO_BASE_MODEL_EXAMPLES)
        .replace("{{METRO_CONTROLLER_LIFECYCLE_DOCS}}", METRO_CONTROLLER_LIFECYCLE_DOCS)
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
        temperature=1,
        max_tokens=8192,
    )

    # Extract the completion content
    completion_content = completion_response.choices[0].message.content

    print("$$$$$$ COMPLETION CONTENT $$$$$$")
    print(completion_content)
    print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")

    commands_str = extract_xml_content(completion_content, "metro_commands")
    commands = extract_commands(commands_str) if commands_str else None

    if not commands:
        commands_str = extract_xml_content(completion_content, "rough_draft_commands")
        commands = extract_commands(commands_str)

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
            click.echo(click.style(f"  >> {cmd}\n", fg="bright_blue"))

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
