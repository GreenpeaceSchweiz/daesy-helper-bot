import os
import logging
import html
import re
from concurrent.futures import ThreadPoolExecutor
from google.adk.tools import ToolContext
import asana
from asana.rest import ApiException
from dotenv import load_dotenv
from urllib3.exceptions import HTTPError

logger = logging.getLogger(__name__)

load_dotenv()

def search_asana_tasks(search_terms: list[str]) -> dict:
    """Search the configured Asana project for up to four alternative terms.

    Results are candidates, not confirmed duplicates. Search is eventually
    consistent and may miss tasks; matched terms are not semantic scores.
    """
    if not search_terms or len(search_terms) > 4 or any(not term.strip() for term in search_terms):
        return {"status": "error", "error": "Provide 1 to 4 non-empty search terms."}
    token = os.getenv("ASANA_PERSONAL_ACCESS_TOKEN")
    project = os.getenv("ASANA_PROJECT_LOOKUP")
    workspace = os.getenv("ASANA_WORKSPACE")
    if not token or not project or not workspace:
        return {"status": "error", "error": "Set ASANA_PERSONAL_ACCESS_TOKEN, ASANA_PROJECT_LOOKUP and ASANA_WORKSPACE."}

    configuration = asana.Configuration()
    configuration.access_token = token
    configuration.return_page_iterator = False
    configuration.retry_strategy = False
    client = asana.ApiClient(configuration)
    tasks_api = asana.TasksApi(client)
    terms = list(dict.fromkeys(term.strip() for term in search_terms))

    def search(term):
        return tasks_api.search_tasks_for_workspace(workspace, {
            "text": term, "projects.any": project, "limit": 25, "sort_by": "relevance",
            "opt_fields": "name,notes,permalink_url,completed,modified_at",
        }, _request_timeout=10)["data"]

    try:
        with ThreadPoolExecutor(max_workers=len(terms)) as executor:
            results = list(executor.map(search, terms))
        tasks = {}
        for term, hits in zip(terms, results):
            for task in hits:
                gid = task["gid"]
                if gid not in tasks:
                    notes = task.get("notes") or ""
                    tasks[gid] = {
                        "gid": gid, "name": task.get("name"), "url": task.get("permalink_url"),
                        "completed": task.get("completed"), "modified_at": task.get("modified_at"),
                        "description_excerpt": notes[:800], "description_truncated": len(notes) > 800,
                        "matched_terms": [],
                    }
                tasks[gid]["matched_terms"].append(term)
        ranked = sorted(tasks.values(), key=lambda task: -len(task["matched_terms"]))
        return {
            "status": "ok", "tasks": ranked[:10],
            "results_truncated": len(ranked) > 10 or any(len(hits) >= 25 for hits in results),
        }
    except (ApiException, HTTPError, OSError, TimeoutError) as error:
        if isinstance(error, ApiException) and error.status == 0:
            message = "Asana search failed: TLS error. Check your trusted certificates and network connection."
        else:
            message = f"Asana search failed (HTTP {error.status})." if isinstance(error, ApiException) else "Asana search failed: connection error or timeout."
        logger.warning(message)
        return {"status": "error", "error": message}
    finally:
        if hasattr(client, "pool"):
            client.pool.close()
            client.pool.join()


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
    project_gid = os.getenv("ASANA_PROJECT_INTAKE")

    # Retrieve the user email from the session state
    # We use 'user:email' to scope it to this specific user across all their sessions
    creator_email = tool_context.state.get("user:email")
    if not creator_email:
        return "Error: Creator email was not found in the session context."

    # Parse each block into Asana XML
    fmt_story    = format_for_asana(user_story)
    fmt_priority = format_for_asana(priority_rationale)
    fmt_ac       = format_for_asana(acceptance_criteria)
    fmt_notes    = format_for_asana(refinement_notes)

    # Construct the HTML body using headers and native line breaks instead of <p>
    html_description = (
        f"<body>"
        f"<h1>User Story</h1>{fmt_story}\n"
        f"<h2>Priority Rationale</h2>{fmt_priority}\n"
        f"<h2>Acceptance Criteria</h2>{fmt_ac}\n"
        f"<em>Additionally, refer also to our <a href=\"https://greennet.elium.com/tile/view/6974#h.62bb66c469d5\">Definition of Done</a>.</em>\n"
        f"<h2>Refinement Notes</h2>{fmt_notes}"
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



# Helper functions for parsing Markdown to Asana HTML
def parse_inline_markdown(text: str) -> str:
    """Parses inline Markdown syntax into valid Asana XML/HTML tags."""
    if not text:
        return ""
    
    # 1. Escape HTML special characters
    text = html.escape(text, quote=False)

    tokens = {}
    token_counter = 0

    # 2. Extract Markdown links [Text](URL) and tokenize them
    def repl_md_link(match):
        nonlocal token_counter
        link_text = match.group(1)
        url = match.group(2)
        token = f"___LINK_TOKEN_{token_counter}___"
        token_counter += 1
        tokens[token] = f'<a href="{url}">{link_text}</a>'
        return token

    text = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', repl_md_link, text)

    # 3. Extract bare URLs (https://...) and tokenize them
    def repl_bare_url(match):
        nonlocal token_counter
        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in ".,;:!?":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]
        token = f"___LINK_TOKEN_{token_counter}___"
        token_counter += 1
        tokens[token] = f'<a href="{raw_url}">{raw_url}</a>{trailing}'
        return token

    text = re.sub(r'https?://[^\s<>"\'\(\)]+', repl_bare_url, text)

    # 4. Monospace Code: `code`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # 5. Bold: **text** or __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.*?)__', r'<strong>\1</strong>', text)

    # 6. Italics: *text* or _text_
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)

    # 7. Strikethrough: ~~text~~
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)

    # 8. Restore link tokens AFTER inline formatting to preserve href strings
    for token, replacement in tokens.items():
        text = text.replace(token, replacement)

    return text


def format_for_asana(text: str) -> str:
    """Converts multi-line Markdown into strict Asana-compliant HTML blocks."""
    if not text:
        return ""

    lines = text.strip().split('\n')
    formatted_lines = []

    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_ul:
                formatted_lines.append("</ul>")
                in_ul = False
            if in_ol:
                formatted_lines.append("</ol>")
                in_ol = False
            continue

        h_match = re.match(r'^(#{1,3})\s+(.*)$', stripped)
        ul_match = re.match(r'^(?:[\-\*])\s+(.*)$', stripped)
        ol_match = re.match(r'^\d+\.\s+(.*)$', stripped)

        if h_match:
            if in_ul:
                formatted_lines.append("</ul>")
                in_ul = False
            if in_ol:
                formatted_lines.append("</ol>")
                in_ol = False
            # Clamp headers to max h2 (Asana tasks only support h1 and h2)
            level = min(len(h_match.group(1)), 2)
            content = parse_inline_markdown(h_match.group(2))
            formatted_lines.append(f"<h{level}>{content}</h{level}>")

        elif ul_match:
            if in_ol:
                formatted_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                formatted_lines.append("<ul>")
                in_ul = True
            content = parse_inline_markdown(ul_match.group(1))
            formatted_lines.append(f"<li>{content}</li>")

        elif ol_match:
            if in_ul:
                formatted_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                formatted_lines.append("<ol>")
                in_ol = True
            content = parse_inline_markdown(ol_match.group(1))
            formatted_lines.append(f"<li>{content}</li>")

        else:
            if in_ul:
                formatted_lines.append("</ul>")
                in_ul = False
            if in_ol:
                formatted_lines.append("</ol>")
                in_ol = False

            content = parse_inline_markdown(stripped)
            # Output plain text without <p> wrappers
            formatted_lines.append(content)

    if in_ul:
        formatted_lines.append("</ul>")
    if in_ol:
        formatted_lines.append("</ol>")

    return "\n".join(formatted_lines)