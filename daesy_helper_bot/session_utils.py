import logging
import time
from typing import Any

from cachetools import TTLCache
from google.adk.events import Event, EventActions
from google.adk.sessions import VertexAiSessionService

logger = logging.getLogger(__name__)

# Active session RAM cache (max 200 active threads for 30 minutes)
_SESSION_CACHE = TTLCache(maxsize=200, ttl=1800)


class CachedVertexAiSessionService(VertexAiSessionService):
    """
    Wraps VertexAiSessionService to serve get_session reads directly from RAM.
    This intercepts both custom calls and internal ADK runner calls.
    """

    async def get_session(
        self, app_name: str, user_id: str, session_id: str, **kwargs: Any
    ) -> Any:
        # 1. RAM HIT (0ms latency, zero network calls)
        if session_id in _SESSION_CACHE:
            logger.info(f"⚡ Loaded session from RAM cache: {session_id}")
            return _SESSION_CACHE[session_id]

        # 2. RAM MISS (Fetch from Vertex AI)
        try:
            session = await super().get_session(
                app_name=app_name, user_id=user_id, session_id=session_id, **kwargs
            )
            if session:
                _SESSION_CACHE[session_id] = session
                logger.info(f"🔄 Hydrated existing session from Vertex AI: {session_id}")
            return session
        except Exception:
            return None

    async def create_session(
        self, app_name: str, user_id: str, session_id: str, **kwargs: Any
    ) -> Any:
        session = await super().create_session(
            app_name=app_name, user_id=user_id, session_id=session_id, **kwargs
        )
        if session:
            _SESSION_CACHE[session_id] = session
            logger.info(f"✨ Created brand-new Vertex AI session: {session_id}")
        return session


def generate_clean_session_id(event: dict[str, Any]) -> str:
    """
    Replaces default ADK session ID logic.
    Extracts Slack timestamp, strips periods, and ensures URL-compliance.
    """
    thread_ts = event.get("thread_ts", event.get("ts", "default-session"))
    clean_ts = thread_ts.replace(".", "")

    channel = event.get("channel", "")
    prefix = "dm" if channel.startswith("D") else "thread"

    return f"{prefix}-{clean_ts}"


async def get_or_create_session(
    session_service: Any, app_name: str, event: dict[str, Any]
) -> Any:
    """
    Retrieves or initializes a session.
    Delegates fetching and caching to the CachedVertexAiSessionService instance.
    """
    target_session_id = generate_clean_session_id(event)
    user_id = event.get("user")

    # Attempt fetch (automatically hits RAM cache via service)
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=target_session_id
    )

    # Create new session if missing
    if not session:
        try:
            session = await session_service.create_session(
                app_name=app_name, user_id=user_id, session_id=target_session_id
            )
        except Exception as e:
            logger.error(f"❌ Error creating session {target_session_id}: {e}")
            raise e

    return session


async def ensure_user_email_cached(
    session: Any, session_service: Any, user_id: str, slack_client: Any
) -> str | None:
    """
    Checks if user's email is cached in session state.
    If missing, fetches it from Slack, updates local RAM state,
    and syncs the delta event to Vertex AI.
    """
    creator_email = (
        session.state.get("user:email")
        if hasattr(session, "state") and session.state
        else None
    )

    if not creator_email:
        try:
            user_info = await slack_client.users_info(user=user_id)
            creator_email = user_info.get("user", {}).get("profile", {}).get("email")

            if creator_email:
                # 1. Update in-memory state immediately
                if hasattr(session, "state") and session.state is not None:
                    session.state["user:email"] = creator_email

                # 2. Build and send state delta event to Vertex AI
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
    """Removes a session from local RAM cache if execution fails."""
    _SESSION_CACHE.pop(session_id, None)
    logger.info(f"🗑️ Invalidated RAM cache for session: {session_id}")