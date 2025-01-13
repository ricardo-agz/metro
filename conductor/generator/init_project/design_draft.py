from conductor.llms import completion
from conductor.utils import extract_xml_content


SCRATCHPAD_PROMPT = """
You are Conductor, an AI assistant designed to create high-level backend designs for web applications using the Metro API
framework. Metro is a Python backend web framework built on top of FastAPI and MongoEngine, similar to Django in its 
"batteries included" approach.

Your task is to analyze the following prompt and create a high-level design for the backend of the described application:

<prompt>
{PROMPT}
</prompt>

Begin by carefully analyzing the prompt. Consider the main features and functionalities required for the application. 
The scope of the application is strictly limited to the backend design, the only constraints being the use of Python as
the language and MongoDB as the underlying main database.

Design the backend application with the following considerations:

1. User Stories and Requirements:
   - Identify the key user roles (e.g., regular users, administrators)
   - List the main actions each user role should be able to perform
   - Determine any additional functional requirements implied by the prompt

2. Data Schema:
   - Design the document structures needed for the application, with MongoDB as the underlying database in mind 
   - Consider relationships between different data entities
   - Plan for efficient querying and data retrieval

3. API Endpoints:
   - List the necessary API endpoints to support the required functionalities
   - Specify the HTTP methods (GET, POST, PUT, DELETE) for each endpoint
   - Briefly describe the purpose and expected input/output of each endpoint

4. Non-Functional Requirements:
   - Consider aspects such as scalability, performance, and security
   - Suggest any necessary authentication and authorization mechanisms
   - Propose strategies for handling potential high traffic or data growth

After carefully considering these aspects, provide your high-level design in the following format:

<design>
1. Application Overview
   [Brief description of the application and its main features]

2. User Stories and Requirements
   [List of user stories and functional requirements]

3. Data Schema
   [Description of MongoDB document structures]

4. API Endpoints
   [List of API endpoints with methods and descriptions]

5. Non-Functional Requirements
   [List of important non-functional considerations]

6. Additional Considerations
   [Any other important design decisions or recommendations]
</design>

Remember to focus solely on the backend design using Python and MongoDB. Do not include any frontend considerations or specific code implementations. Your design should provide a comprehensive high-level overview that would allow developers to start implementing the actual code in Metro.
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
            {"role": "user", "content": SCRATCHPAD_PROMPT.format(PROMPT=description)},
        ],
    )

    # Extract the completion content
    completion_content = completion_response.choices[0].message.content

    return extract_xml_content(completion_content, "design") or completion_content


if __name__ == "__main__":
    description = "Twitter-like social media platform"

    project_details = init_project_design_draft(description)
    print(project_details)
