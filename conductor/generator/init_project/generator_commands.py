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
project based on a project description and a high-level design draft.

You will be provided with two inputs:
1. <project_description>{{PROJECT_DESCRIPTION}}</project_description>
This is a brief description of the project's main purpose and features.

2. <design_draft>{{DESIGN_DRAFT}}</design_draft>
This is a detailed design draft that includes information about the application overview, user stories, data schema, 
API endpoints, and other considerations.

Project Analysis Guidelines:

1. Data Model Architecture
   - Map out all models and their relationships from the data schema
   - Identify model dependencies through ref: and list:ref: fields
   - Plan generation order to ensure dependent models are created after their dependencies
   - Example: If Comment has author:ref:User and post:ref:Post, generate User first, then Post, then Comment

2. Controller Architecture
   - Analyze API endpoints to identify authentication requirements:
     * Public endpoints (no auth)
     * User endpoints (require authentication)
     * Admin endpoints (require elevated privileges)
   - Identify shared behaviors across endpoints that suggest need for base controllers
   - Plan controller inheritance hierarchy before generating specific controllers

3. Resource Generation Strategy
   Choose the appropriate generation approach for each component:

   Use metro generate scaffold when:
   - The resource needs full CRUD operations
   - The model and controller are tightly coupled
   - The resource is a primary entity in your system
   Example: A Post resource that needs create, read, update, delete endpoints

   Use metro generate model when:
   - The model is primarily referenced by other models
   - No direct API endpoints are needed
   - The model represents supporting data
   Example: A Category model that's only referenced by other models

   Use metro generate controller when:
   - The controller handles auth or utility endpoints
   - The endpoints don't map to a single model
   - The controller implements shared behavior
   Example: An Auth controller for login/register endpoints

4. Authentication Implementation (if needed)
   When the project requires user authentication:
   - Create an Auth controller first for login/register endpoints (or if the project description outlines a specific implementation strategy, follow that)
   - Use UserBase inheritance for the User model (skip defining fields already in UserBase) (unless specified otherwise)
   - Create an Authenticated controller or Protected controller that controllers with protected routes inherit from (unless specified otherwise)
   - Consider admin base controllers for privileged operations (if needed)

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
- Use `^` for unique fields and `_` for optional fields
- Use `hashed_str` for password fields
- Use `file` or `list:file` for file upload fields
- Timestamp fields for creation and last update like created_at and updated_at are automatically added and are not 
required in the model definition.

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
Your analysis should address:
1. Model Dependency Analysis
   - Complete list of models needed
   - Dependencies between models
   - Generation order considering dependencies

2. Controller Strategy
   - Required base controllers
   - Controller inheritance hierarchy
   - Authentication/authorization requirements

3. Resource Generation Plan
   - Which resources need full scaffolds
   - Which need only models
   - Which need only controllers

4. Generation Sequence
   - Ordered list of generations
   - Reasoning for the order
   - Handling of dependencies
</initial_thoughts>

<rough_draft_commands>
# Commands should be ordered by dependencies, with base/auth controllers first if needed
# Include brief comments explaining key decisions
[List your initial Metro commands here, one per line]
</rough_draft_commands>

<reflection>
Analyze your generated commands:
1. Best Practices
    - Do all controllers, resources, and models follow Metro conventions?
    - Do all controllers, resources, and models have descriptive names? Overly generic names like (BaseController) 
    should be avoided unless they contain necessary shared functionality that is required by EVERY controller in the 
    project. 

2. Dependency Correctness
   - Are models generated in correct order?
   - Are all relationships properly defined?

3. Controller Structure
   - Is the controller hierarchy logical?
   - Are shared behaviors properly abstracted?
   
4. Authentication Integration (if needed)
   - Is UserBase properly leveraged if authentication is required?
   - Are auth checks implemented efficiently?
   - Does the auth implementation match any specific requirements from the project description?
   - Are protected routes properly secured through controller inheritance?

5. Completeness Check
   - Do commands cover all functional requirements?
   - Are all necessary relationships defined?
   - Is the implementation DRY (Don't Repeat Yourself)?
</reflection>

<metro_commands>
[Your final, validated Metro commands here, one per line]
</metro_commands>

[Rest of the documentation sections remain the same, but move the UserBase example to after the basic syntax rules for better flow]

Remember:
1. Order matters - generate models before they're referenced
2. Don't duplicate auth logic - use base controllers
3. Only include fields not provided by UserBase when inheriting
4. Follow Metro syntax exactly
5. Consider each resource's full lifecycle
6. Think carefully about controller inheritance
7. Use appropriate field types and modifiers
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


def extract_commands(commands_str: str) -> list[str]:
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
    )

    # Extract the completion content
    completion_content = completion_response.choices[0].message.content

    print("$$$$$$ COMPLETION CONTENT $$$$$$")
    print(completion_content)
    print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")

    commands_str = extract_xml_content(completion_content, "metro_commands")
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
