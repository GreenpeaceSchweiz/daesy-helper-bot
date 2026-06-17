import os
import asana
from asana.rest import ApiException
from dotenv import load_dotenv

load_dotenv()

# Define the Asana integration function
def create_asana_task(title: str, user_story: str, priority_rationale: str, acceptance_criteria: str, refinement_notes: str) -> str:
    """
    Creates a new user story task in Asana using the flat ApiClient syntax.
    """
    # 1. Configure the Token
    configuration = asana.Configuration()
    configuration.access_token = os.getenv("ASANA_PERSONAL_ACCESS_TOKEN")
    
    # 2. Instantiate the ApiClient without a 'with' context manager
    api_client = asana.ApiClient(configuration)
    
    # 3. Instantiate API classes
    tasks_api_instance = asana.TasksApi(api_client)
    
    project_gid = os.getenv("ASANA_PROJECT_GID") 

    custom_fields_payload = {
            os.getenv("ASANA_FIELD_GID_USER_STORY"): user_story,
            os.getenv("ASANA_FIELD_GID_PRIORITY_RATIONALE"): priority_rationale,
            os.getenv("ASANA_FIELD_GID_ACCEPTANCE_CRITERIA"): acceptance_criteria,
            os.getenv("ASANA_FIELD_GID_REFINEMENT_NOTES"): refinement_notes
        }
    
    # Build the payload body
    body = {
        "data": {
            "name": title,
            "projects": [project_gid],
            "custom_fields": custom_fields_payload
        }
    }

    opts = {}
    
    try:
        # Send the request
        result = tasks_api_instance.create_task(body, opts)
        # Access nested key safely from dictionary response
        task_gid = result.get('gid')
        task_url = f"https://app.asana.com/0/{project_gid}/{task_gid}"
        return f"Success! Task created in Asana. Task ID: {task_url}"
    except ApiException as e:
        return f"Exception when calling TasksApi->create_task: {e}\n"
