import logging
import time
from typing import Any

from cachetools import TTLCache
from google.adk.events import Event, EventActions

logger = logging.getLogger(__name__)

# Active session RAM cache (max 200 active threads for 30 minutes)
# Since Cloud Run max-instances=1, this cache persists across requests on warm containers.
_SESSION_CACHE = TTLCache(maxsize=200, ttl=1800)


def generate_clean_session_id(event: dict[str, Any]) -> str:
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

    return f"{prefix}-{clean_ts}"


async def get_or_create_session(
    session_service: Any, app_name: str, event: dict[str, Any]
) -> Any:
    """
    Retrieves or initializes a session using process-level RAM caching.
    Returns a tuple of (session_object, session_id_string).
    """
    target_session_id = generate_clean_session_id(event)
    user_id = event.get("user")

    # 1. RAM HIT (0ms latency, zero network calls)
    if target_session_id in _SESSION_CACHE:
        logger.info(f"⚡ Loaded session from RAM cache: {target_session_id}")
        return _SESSION_CACHE[target_session_id]

    # 2. RAM MISS (Attempt fetch from Vertex AI)
    session = None
    try:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=target_session_id
        )
    except Exception:
        session = None

    if session:
        logger.info(f"🔄 Hydrated existing session from Vertex AI: {target_session_id}")
    # 3. CREATE NEW SESSION (If get_session returned None or failed)
    else:
        try:
            session = await session_service.create_session(
                app_name=app_name, user_id=user_id, session_id=target_session_id
            )
            logger.info(f"✨ Created brand-new Vertex AI session: {target_session_id}")
        except Exception as e:
            logger.error(f"❌ Error creating session {target_session_id}: {e}")
            raise e

    # 4. Store valid session in RAM
    if session:
        _SESSION_CACHE[target_session_id] = session

    return session


async def ensure_user_email_cached(
    session: Any, session_service: Any, user_id: str, slack_client: Any
) -> str | None:
    """
    Checks if the user's email is already cached in session state.
    If not, fetches it from Slack, updates in-memory RAM state directly,
    and syncs the event to Vertex AI.
    """
    # Read the 'user:email' from session state if present
    creator_email = (
        session.state.get("user:email")
        if hasattr(session, "state") and session.state
        else None
    )

    if not creator_email:
        try:
            # Fetch profile details directly from Slack API
            user_info = await slack_client.users_info(user=user_id)
            creator_email = user_info.get("user", {}).get("profile", {}).get("email")

            if creator_email:
                # 1. Update in-memory state immediately for local tool/runner access
                if hasattr(session, "state") and session.state is not None:
                    session.state["user:email"] = creator_email

                # 2. Build and persist state delta event to Vertex AI
                state_changes = {"user:email": creator_email}
                actions_with_update = EventActions(state_delta=state_changes)

                system_event = Event(
                    invocation_id=f"slack_init_{user_id}_{int(time.time())}",
                    author="slack-app",
                    actions=actions_with_update,
                    timestamp=time.time(),
                )

                await session_service.append_event(session, system_event)
                logger.info(f"💾 Cached user:email ({creator_email}) in RAM and Vertex AI.")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve or cache Slack user email: {e}")

    return creator_email


def invalidate_session_cache(session_id: str) -> None:
    """Removes a session from local RAM cache if runner execution fails."""
    _SESSION_CACHE.pop(session_id, None)
    logger.info(f"🗑️ Invalidated RAM cache for session: {session_id}")