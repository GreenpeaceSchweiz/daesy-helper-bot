import logging

logger = logging.getLogger(__name__)

async def get_or_create_session(session_service, app_name: str, user_id: str, thread_ts: str):
    """Retrieves an existing session or initializes a new one based on the thread ID."""
    clean_thread_id = thread_ts.replace(".", "")
    target_session_id = f"thread_{clean_thread_id}"
    
    try:
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=target_session_id
        )
        logger.info(f"🔄 Resuming existing Vertex AI session: {target_session_id}")
        return session
    except Exception:
        logger.info(f"✨ Creating brand-new Vertex AI session: {target_session_id}")
        return await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=target_session_id
        )