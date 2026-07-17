import os
import logging
import html
from google.adk.tools import ToolContext
import asana
from asana.rest import ApiException
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

def create_asana_task(title: str, user_story: str, priority_rationale: str, acceptance_criteria: str, refinement_notes: str, tool_context: ToolContext) -> str:
    """
    Creates a new user story task in Asana using the flat ApiClient syntax,
    formatting the elements into the HTML description (html_notes).
    """
    # Configure the Token
    configuration = asana.Configuration()
    configuration.access_token = os.getenv("ASANA_PERSONAL_ACCESS_TOKEN")
    
    # Instantiate the ApiClient
    api_client = asana.ApiClient(configuration)
    tasks_api_instance = asana.TasksApi(api_client)
    project_gid = os.getenv("ASANA_PROJECT")

    # Retrieve the user email from the session state
    # We use 'user:email' to scope it to this specific user across all their sessions
    creator_email = tool_context.state.get("user:email")
    if not creator_email:
        return "Error: Creator email was not found in the session context."

    # Escape all dynamic strings to ensure perfectly safe XML
    esc_user_story = html.escape(user_story)
    esc_priority_rationale = html.escape(priority_rationale)
    esc_acceptance_criteria = html.escape(acceptance_criteria)
    esc_refinement_notes = html.escape(refinement_notes)

    # Construct the HTML body using headers and native line breaks instead of <p>
    html_description = (
        f"<body>"
        f"<h1>User Story</h1>{esc_user_story}\n"
        f"<h2>Priority Rationale</h2>{esc_priority_rationale}\n"
        f"<h2>Acceptance Criteria</h2>{esc_acceptance_criteria}\n"
        f"<h2>Refinement Notes</h2>{esc_refinement_notes}"
        f"</body>"
    )

    custom_fields_payload = {
        os.getenv("ASANA_FIELD_CREATOR"): creator_email
    }
    
    # Build the payload body
    body = {
        "data": {
            "name": title,
            "projects": [project_gid],
            "html_notes": html_description,
            "custom_fields": custom_fields_payload
        }
    }

    opts = {}
    
    try:
        # Send the request
        result = tasks_api_instance.create_task(body, opts)
        task_gid = result.get('data', {}).get('gid') if isinstance(result, dict) else getattr(result, 'gid', None)
        
        if not task_gid:
            task_gid = result.get('gid') if isinstance(result, dict) else None

        task_url = f"https://app.asana.com/0/{project_gid}/{task_gid}"
        return f"Success! Task created in Asana. Task URL: {task_url}"
    except ApiException as e:
        logger.error(f"Asana API Error Payload: {e.body}")
        logger.exception("Failed to create task")
        return f"Exception when calling TasksApi->create_task: {e}\n"