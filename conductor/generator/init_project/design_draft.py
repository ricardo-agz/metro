from conductor.llms import completion
from conductor.utils import extract_xml_content


SCRATCHPAD_PROMPT = """
You are Conductor, an AI assistant designed to create high-level backend designs for web applications using the Metro 
API framework. Metro is a Python backend web framework built on top of FastAPI and MongoEngine, similar to Django in 
its "batteries included" approach.

Your task is to analyze the following prompt and create a detailed technical design for the backend application:

<prompt>
{{PROMPT}}
</prompt>

Provide your technical design in the following structured format:

<design>
1. Explicit Functionality Analysis

* List every feature/functionality explicitly mentioned in the prompt
* For each feature, identify:
    - What actions can users take?
    - What data needs to be stored?
    - What are the relationships between entities?
    - What are the access patterns?
    - What are potential performance bottlenecks?


2. Implicit Functionality Analysis

* Based on the type of application, identify standard features not explicitly mentioned
* Common features that are typically expected:
    - User authentication and authorization
    - Profile management
    - Notification systems
    - Search functionality
    - Content moderation capabilities
    - Analytics and metrics tracking
* For each implicit feature:
    - Justify why it's necessary
    - Define its scope and limitations
    - Identify integration points with explicit features

3. Data Model Design

* Create a detailed data model for the application:
    - List all entities and their fields and types
    - For each field, mark it as required, optional, or unique 
    - Any indexes needed for efficient querying, both individual fields indexes or compound indexes
    - Define relationships between entities (one-to-one, one-to-many, many-to-many) 

4. API Design

* Define the API endpoints for each feature. For each endpoint, specify:
    - HTTP method (GET, POST, PUT, DELETE)
    - Route pattern
    - Request parameters (path, query, body)
    - If the endpoint requires authentication/authorization
</design>

Your design must be wrapped in the <design> tag and should be structured according to the provided outline.
"""


def init_project_design_draft(description: str) -> str:
    """
    Initialize a new project based on the given description.

    Args:
        description (str): The description of the project.

    Returns:
        dict: The initialized project details.
    """
    # Generate the completion for the scratchpad prompt

    completion_response = completion(
        model="claude-3-5-sonnet-20241022",
        messages=[
            {
                "role": "user",
                "content": SCRATCHPAD_PROMPT.replace("{{PROMPT}}", description),
            }
        ],
        temperature=1,
        max_tokens=8192,
    )

    # Extract the completion content
    completion_content = completion_response.choices[0].message.content

    return extract_xml_content(completion_content, "design") or completion_content


if __name__ == "__main__":
    description = "Twitter-like social media platform"

    project_details = init_project_design_draft(description)
    print(project_details)
