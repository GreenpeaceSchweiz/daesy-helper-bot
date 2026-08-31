import logging
import random

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

import random

LOADING_MESSAGES_POOL = [
    # Daisy & Floral Motifs
    "Watering the daisies",
    "Planting a thought",
    "Chasing the sunshine",

    # Relatable & Cozy
    "Sipping coffee",
    "Putting on reading glasses",
    "Finding a good pen",
    "Adjusting the thinking cap",
    "Grabbing a notebook",
    
    # Thoughtful & Focused
    "Connecting the dots",
    "Leafing through notes",
    "Double-checking details",
    "Reading between the lines",
    "Gathering context",
    
    # Light & Precise
    "Pruning the options",
    "Untangling the wires",
    "Checking the blueprint",
]

FINAL_MESSAGE = "Polishing the response"

def get_loading_messages(count: int = 5) -> list[str]:
    """
    Returns a randomized list from the pool, guaranteed to end with
    'Polishing the response'. Total list length will equal `count` (max 10).
    """
    # Enforce Slack limit (max 10) and ensure count is at least 1
    total_count = max(1, min(count, len(LOADING_MESSAGES_POOL) + 1, 10))
    
    # Sample (total_count - 1) messages from the pool
    sampled = random.sample(LOADING_MESSAGES_POOL, k=total_count - 1)
    
    # Append the guaranteed final step
    return sampled + [FINAL_MESSAGE]