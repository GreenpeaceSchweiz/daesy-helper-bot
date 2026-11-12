import logging
import time

from typing import Any
from daesy_helper_bot.services.peerdom import PeerdomClient

logger = logging.getLogger(__name__)

# State key constants
USER_EMAIL_KEY = "user:email"
USER_FIRST_NAME_KEY = "user_first_name"
USER_LAST_NAME_KEY = "user_last_name"
USER_DISPLAY_NAME_KEY = "user_display_name"
ROLES_CONTEXT_KEY = "roles_context"

async def get_or_create_session(session_service, app_name: str, event: dict[str, Any]) -> tuple[Any, str]:
    """
    Retrieves or initializes a session.
    Returns a tuple of (session_object, session_id_string).
    """
    target_session_id = generate_clean_session_id(event)
    user_id = event.get("user")
    session = None
    
    try:
        session = await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=target_session_id
        )
        logger.info(f"✨ Creating brand-new Vertex AI session: {target_session_id}")
    except Exception:
        logger.info(f"🔄 Resuming existing Vertex AI session: {target_session_id}")
        try:
            session = await session_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=target_session_id
            )
        except Exception as e:
            logger.error(f"❌ Error retrieving existing session {target_session_id}: {e}")
            
    # Return both the session object (for state modification) and the string ID (for the runner)
    return session


def generate_clean_session_id(event: dict) -> str:
    """
    Replaces the default ADK session ID logic.
    Extracts the Slack timestamp, strips periods, and ensures URL-compliance.
    """
    # Fallback to standard message ts or thread ts
    thread_ts = event.get("thread_ts", event.get("ts", "default-session"))
    
    # Vertex AI constraints: lowercase, alphanumeric, and hyphens only
    clean_ts = thread_ts.replace(".", "")
    
    # Differentiate prefixes so you can tell DMs and Threads apart in your GCP console
    channel = event.get("channel", "")
    prefix = "dm" if channel.startswith("D") else "thread"
    
    sanitized_id = f"{prefix}-{clean_ts}"
    return sanitized_id

from google.adk.events import Event, EventActions


async def ensure_user_slack_info_cached(
    session: Any,
    session_service: Any,
    user_id: str,
    slack_client: Any
) -> tuple[str | None, str | None]:
    """
    Checks if the user's email and first_name are cached in the session state.
    If not, fetches them from Slack in a single API call, safely updates the session state
    with email, first_name, last_name, and display_name, and returns email and first_name.
    """
    creator_email = session.state.get(USER_EMAIL_KEY) if hasattr(session, "state") else None
    user_first_name = session.state.get(USER_FIRST_NAME_KEY) if hasattr(session, "state") else None

    # If either is missing, fetch all name fields from Slack
    if not creator_email or not user_first_name:
        try:
            user_info = await slack_client.users_info(user=user_id)
            user_data = user_info.get("user", {})
            profile = user_data.get("profile", {})
            
            if not creator_email:
                creator_email = profile.get("email")
            if not user_first_name:
                user_first_name = profile.get("first_name")
            
            user_last_name = profile.get("last_name")
            user_display_name = profile.get("display_name")
            
            # Store all newly fetched values in session state
            state_changes = {}
            if creator_email:
                state_changes[USER_EMAIL_KEY] = creator_email
            if user_first_name:
                state_changes[USER_FIRST_NAME_KEY] = user_first_name
            if user_last_name:
                state_changes[USER_LAST_NAME_KEY] = user_last_name
            if user_display_name:
                state_changes[USER_DISPLAY_NAME_KEY] = user_display_name
            
            if state_changes:
                actions_with_update = EventActions(state_delta=state_changes)
                
                system_event = Event(
                    invocation_id=f"slack_info_{user_id}_{int(time.time())}",
                    author="slack-app",
                    actions=actions_with_update,
                    timestamp=time.time()
                )
                
                await session_service.append_event(session, system_event)
                logger.info(f"💾 Safely cached Slack user info in session.")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve or cache Slack user info: {e}")
            
    return creator_email, user_first_name


async def ensure_user_roles_cached(
    session: Any,
    session_service: Any,
    user_email: str,
    peerdom_api_key: str
) -> str | None:
    """
    Checks if the user's organizational roles are already cached in the session state.
    If not, fetches them from Peerdom API, and stores them as context.
    
    Args:
        session: The Vertex AI session object
        session_service: The session service for appending events
        user_email: The user's email address
        peerdom_api_key: The Peerdom API key from environment
        
    Returns:
        The roles summary string if found, None otherwise
    """
    if not peerdom_api_key:
        logger.debug("PEERDOM_API_KEY not configured, skipping role lookup")
        return None
    
    if not user_email:
        logger.debug("No user email available for Peerdom role lookup")
        return None

    # Check if roles are already cached in session state
    roles_summary = session.state.get(ROLES_CONTEXT_KEY) if hasattr(session, "state") else None
    
    if roles_summary:
        logger.info(f"✓ User roles already cached in session")
        return roles_summary
    
    try:
        # Initialize Peerdom client
        peerdom_client = PeerdomClient(api_key=peerdom_api_key)
        
        # Fetch roles summary
        roles_summary = await peerdom_client.get_peer_roles_summary(user_email)
        
        if roles_summary:
            # Store in session state
            state_changes = {ROLES_CONTEXT_KEY: roles_summary}
            actions_with_update = EventActions(state_delta=state_changes)
            
            system_event = Event(
                invocation_id=f"peerdom_init_{user_email}_{int(time.time())}",
                author="peerdom-service",
                actions=actions_with_update,
                timestamp=time.time()
            )
            
            await session_service.append_event(session, system_event)
            logger.info(f"💾 Cached user roles context in session for {user_email}")
            
            return roles_summary
        else:
            logger.info(f"No roles found in Peerdom for {user_email}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to fetch or cache user roles from Peerdom: {e}")
        return None