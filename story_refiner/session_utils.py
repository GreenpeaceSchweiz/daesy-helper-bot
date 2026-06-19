import logging

logger = logging.getLogger(__name__)

async def get_or_create_session(session_service, app_name: str, user_id: str, thread_ts: str) -> str:
    """Retrieves or initializes a session, returning the validated session ID string."""
    clean_thread_id = thread_ts.replace(".", "")
    target_session_id = f"thread-{clean_thread_id}"
    
    try:
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=target_session_id
        )
        logger.info(f"✨ Creating brand-new Vertex AI session: {target_session_id}")
    except Exception:
        logger.info(f"🔄 Resuming existing Vertex AI session: {target_session_id}")
        await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=target_session_id
        )
        
    # Return the string explicitly so we don't care if the cloud methods return None
    return target_session_id


def custom_vertex_session_id_generator(event: dict) -> str:
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
    logger.info(f"🔮 Custom SlackRunner ID Generator mapped event to: {sanitized_id}")
    return sanitized_id