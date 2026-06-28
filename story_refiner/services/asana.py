import os
import asana
from asana.rest import ApiException
from dotenv import load_dotenv

load_dotenv()

def create_asana_task(title: str, user_story: str, priority_rationale: str, acceptance_criteria: str, refinement_notes: str) -> str:
    """
    Creates a new user story task in Asana using the flat ApiClient syntax,
    formatting the elements into the HTML description (html_notes).
    """
    # 1. Configure the Token
    configuration = asana.Configuration()
    configuration.access_token = os.getenv("ASANA_PERSONAL_ACCESS_TOKEN")
    
    # 2. Instantiate the ApiClient without a 'with' context manager
    api_client = asana.ApiClient(configuration)
    
    # 3. Instantiate API classes
    tasks_api_instance = asana.TasksApi(api_client)
    
    project_gid = os.getenv("ASANA_PROJECT_GID") 

    # Construct the HTML body for the description
    # Asana requires valid, clean HTML tags for html_notes
    html_description = (
        f"<body>"
        f"<h1>User Story</h1><p>{user_story}</p>"
        f"<h2>Priority Rationale</h2><p>{priority_rationale}</p>"
        f"<h2>Acceptance Criteria</h2><p>{acceptance_criteria}</p>"
        f"<h2>Refinement Notes</h2><p>{refinement_notes}</p>"
        f"</body>"
    )
    
    # Build the payload body using 'html_notes' instead of 'custom_fields'
    body = {
        "data": {
            "name": title,
            "projects": [project_gid],
            "html_notes": html_description
        }
    }

    opts = {}
    
    try:
        # Send the request
        result = tasks_api_instance.create_task(body, opts)
        # Access nested key safely from dictionary response
        task_gid = result.get('data', {}).get('gid') if isinstance(result, dict) else getattr(result, 'gid', None)
        
        if not task_gid:
            # Fallback handling depending on how your specific SDK version deserializes responses
            task_gid = result.get('gid') if isinstance(result, dict) else None

        task_url = f"https://app.asana.com/0/{project_gid}/{task_gid}"
        return f"Success! Task created in Asana. Task URL: {task_url}"
    except ApiException as e:
        return f"Exception when calling TasksApi->create_task: {e}\n"
    
