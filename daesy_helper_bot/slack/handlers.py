import os
import logging
from typing import Any
from google.genai import types
from daesy_helper_bot.slack.middleware import ignore_timeout_retries
from daesy_helper_bot.slack.helpers import build_thread_context, get_loading_messages
from daesy_helper_bot.session_utils import get_or_create_session, ensure_user_email_cached, invalidate_session_cache

import time

logger = logging.getLogger(__name__)

def register_slack_handlers(slack_app, mention_runner, dm_runner, session_service):
    """
    Registers event handlers to the slack app routing table using Lazy Listeners
    to prevent 3-second timeout retries on Cloud Run.
    """

    # --- Register Global Middleware First ---
    # Every incoming event passes through this before routing kicks in
    slack_app.middleware(ignore_timeout_retries)
    
    # --- Shared Core Message Handler ---
    async def _handle_message(event: dict[str, Any], say: Any, runner: Any):
        text = event.get("text", "")
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")

        if not text or not user_id or not channel_id:
            return 
    
        # 1. Session Load
        session = await get_or_create_session(session_service, app_name=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"), event=event)

        # 2. Email Cache Check
        await ensure_user_email_cached(session=session, session_service=session_service, user_id=user_id, slack_client=slack_app.client)

        # 3. Message Prep
        new_message = types.Content(role="user", parts=[types.Part(text=text)])

        # 4. Runner Initialization & First Chunk
        try:
            first_chunk = True
            async for chunk in runner.run_async(user_id=user_id, session_id=session.id, new_message=new_message):
                if first_chunk:
                    first_chunk = False
                if chunk.content and chunk.content.parts:
                    for part in chunk.content.parts:
                        if part.text:
                            # Posting the message automatically clears the setStatus indicator in Slack
                            await say(text=part.text, thread_ts=thread_ts)
                
        except Exception as e:
            invalidate_session_cache(session.id)

            error_message = f"Sorry, I encountered an error: {str(e)}"
            logger.exception("Error running ADK agent for Slack:")
            await say(text=error_message, thread_ts=thread_ts)


    # --- Instant Acknowledgement Handler (Shared) ---
    async def instant_ack(ack):
        # This instantly sends HTTP 200 back to Slack, stopping all retries.
        await ack()

    # --- Route 0: Assistant Threads (do nothing) ---
    async def lazy_handle_assistant_thread_started():
        logger.info(f"✏️ Assistant Thread started, doing nothing")

    slack_app.event("assistant_thread_started")(ack=instant_ack, lazy=[lazy_handle_assistant_thread_started])


    # --- Route 1: App Mentions ---
    async def lazy_handle_app_mention(event, say, client):
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))

        # Set native Slack status loading state
        await client.assistant_threads_setStatus(
            channel_id=channel_id,
            thread_ts=thread_ts,
            status="is thinking...",
            loading_messages=get_loading_messages()
        )
        
        logger.info(f"🔄 Processing channel app_mention for thread {thread_ts}")

        context_text = await build_thread_context(client, channel_id, thread_ts)
        event["text"] = context_text  

        await _handle_message(event, say, mention_runner)

    # Register Route 1 using the split syntax
    slack_app.event("app_mention")(ack=instant_ack, lazy=[lazy_handle_app_mention])


    # --- Route 2: Direct Messages ---
    async def lazy_handle_direct_messages(event, say, client):
        if event.get("bot_id") or event.get("bot_profile"):
            return

        if event.get("channel_type") == "im":
            logger.info(f"💬 Processing 1-on-1 Direct Message from User: {event.get('user')}")

            channel_id = event.get("channel")
            thread_ts = event.get("thread_ts", event.get("ts"))

            # Set native Slack status loading state
            await client.assistant_threads_setStatus(
                channel_id=channel_id,
                thread_ts=thread_ts,
                status="thinking...",
                loading_messages=get_loading_messages()
            )
            
            await _handle_message(event, say, dm_runner)

    # Register Route 2 using the split syntax
    slack_app.event("message")(ack=instant_ack, lazy=[lazy_handle_direct_messages])