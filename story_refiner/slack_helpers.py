import logging

logger = logging.getLogger(__name__)

async def get_thread_url(client, channel_id: str, thread_ts: str) -> str:
    """Fetches the permalink for a specific thread."""
    try:
        response = await client.chat_getPermalink(channel=channel_id, message_ts=thread_ts)
        return response.get("permalink", "URL not found")
    except Exception as e:
        logger.warning(f"Could not fetch permalink: {e}")
        return "URL not found"

async def build_thread_context(client, channel_id: str, thread_ts: str) -> str:
    """Fetches full thread history and formats it into a single context string."""
    thread_history = await client.conversations_replies(channel=channel_id, ts=thread_ts)
    messages = thread_history.get("messages", [])
    
    context_lines = []
    for msg in messages:
        msg_user = msg.get("user", "System")
        msg_text = msg.get("text", "")
        context_lines.append(f"User <@{msg_user}> said: {msg_text}")
        
    thread_url = await get_thread_url(client, channel_id, thread_ts)
    context_lines.append(f"\nSource Thread Link: {thread_url}")
    
    return "\n".join(context_lines)