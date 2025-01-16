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

* Think about each functionality and the required API endpoints to enable it. Think about whether it maps to a single 
endpoint or multiple endpoints. For example, for a post like/unlike feature, you could use either:
    - Single toggle endpoint: POST /api/posts/{postId}/toggle-like
    - Separate endpoints: POST /api/posts/{postId}/like and DELETE /api/posts/{postId}/like
    
    In cases where either approach could work, think through the tradeoffs. Consider factors like:
    - API clarity and intent
    - State management requirements
    - Performance implications
    - Handling of race conditions
    - Audit/logging needs
    
* Define the API endpoints for each feature. Make sure to consider security and best practices in your API design. 
Some common bad patterns to avoid:
    - If the user is making a request, don't pass the user ID in the request body since this creates opportunities for
    attackers to manipulate the user ID and it is redundant since we can get the user ID from the authentication token.
    
* Authentication Security Requirements:
    For login, registration, and password reset endpoints, you MUST implement these rate limit policies:
    - Primary rate limit by username/email: 
        - 3 failed attempts per minute
        - 20 failed attempts per hour
        - Successful login resets the counters
    - Secondary rate limit by IP: Maximum 1000 requests per hour to handle extreme abuse cases

* For each endpoint, specify:
    - HTTP method (GET, POST, PUT, DELETE)
    - Route pattern
    - Request parameters (path, query, body)
    - If the endpoint requires authentication/authorization
    - If the endpoint should be rate-limited. If so, specify the rate limit policy:
        - Note: Authentication endpoints MUST implement both username and IP-based rate limiting as defined above
        - For non-auth endpoints:
            - Number of requests per time period
            - If the rate limit is global or dynamic
            - How the key for the rate limit is determined
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
