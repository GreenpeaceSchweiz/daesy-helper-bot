import os
import logging
from typing import Any
from google.genai import types
from story_refiner.slack.middleware import ignore_timeout_retries
from story_refiner.slack.helpers import build_thread_context
from story_refiner.session_utils import get_or_create_session

logger = logging.getLogger(__name__)

def register_slack_handlers(slack_app, mention_runner, dm_runner, session_service):
    """
    Registers event handlers using decoupled ack/lazy structures to guarantee
    sub-50ms user interface confirmation times.
    """

    # --- Register Global Middleware First ---
    slack_app.middleware(ignore_timeout_retries)
    
    # --- Shared Core Message Handler ---
    async def _handle_message(event: dict[str, Any], say: Any, runner: Any, thinking_ts: str):
        text = event.get("text", "")
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")

        if not text or not user_id or not channel_id:
            return 

        session_id = await get_or_create_session(
            session_service, 
            app_name=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"), 
            event=event
        )
        
        new_message = types.Content(role="user", parts=[types.Part(text=text)])
        
        try:
            async for chunk in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
            ):
                if chunk.content and chunk.content.parts:
                    for part in chunk.content.parts:
                        if part.text:
                            if thinking_ts:
                                await slack_app.client.chat_update(
                                    channel=channel_id,
                                    ts=thinking_ts,
                                    text=part.text,
                                )
                                thinking_ts = None
                            else:
                                await say(text=part.text, thread_ts=thread_ts)
                                
            if thinking_ts:
                await slack_app.client.chat_delete(channel=channel_id, ts=thinking_ts)
                
        except Exception as e:
            error_message = f"Sorry, I encountered an error: {str(e)}"
            logger.exception("Error running ADK agent for Slack:")
            if thinking_ts:
                await slack_app.client.chat_update(
                    channel=channel_id,
                    ts=thinking_ts,
                    text=error_message,
                )
            else:
                await say(text=error_message, thread_ts=thread_ts)


    # --- Pure Instant Acknowledgement Handler (Shared) ---
    async def standard_instant_ack(ack):
        # Keeps Route 0 clean and fast
        await ack()


    # --- Route 0: Assistant Threads (Does nothing silently) ---
    async def lazy_handle_assistant_thread_started():
        logger.info(f"✏️ Assistant Thread started, doing nothing")

    slack_app.event("assistant_thread_started")(ack=standard_instant_ack, lazy=[lazy_handle_assistant_thread_started])


    # --- Route 1: App Mentions ---
    async def ack_app_mention(ack, event, say):
        await ack()
        if event.get("bot_id") or event.get("bot_profile"):
            return
            
        thread_ts = event.get("thread_ts", event.get("ts"))
        thinking_response = await say(text="_Thinking..._", thread_ts=thread_ts)
        event["thinking_ts"] = thinking_response.get("ts")

    async def lazy_handle_app_mention(event, say, client):
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))
        
        logger.info(f"🔄 Processing channel app_mention for thread {thread_ts}")

        context_text = await build_thread_context(client, channel_id, thread_ts)
        event["text"] = context_text  
        thinking_ts = event.get("thinking_ts")

        await _handle_message(event, say, mention_runner, thinking_ts)

    slack_app.event("app_mention")(ack=ack_app_mention, lazy=[lazy_handle_app_mention])


    # --- Route 2: Direct Messages ---
    async def ack_direct_message(ack, event, say):
        await ack()
        # CRITICAL: Drop execution instantly if the text message came from our own bot
        if event.get("bot_id") or event.get("bot_profile"):
            return

        # Ensure we are inside a pure 1-on-1 direct message before posting placeholders
        if event.get("channel_type") == "im" and event.get("text"):
            thread_ts = event.get("thread_ts", event.get("ts"))
            thinking_response = await say(text="_Thinking..._", thread_ts=thread_ts)
            event["thinking_ts"] = thinking_response.get("ts")

    async def lazy_handle_direct_messages(event, say):
        if event.get("bot_id") or event.get("bot_profile"):
            return

        if event.get("channel_type") == "im" and event.get("text"):
            logger.info(f"💬 Processing 1-on-1 Direct Message from User: {event.get('user')}")
            thinking_ts = event.get("thinking_ts")

            await _handle_message(event, say, dm_runner, thinking_ts)

    slack_app.event("message")(ack=ack_direct_message, lazy=[lazy_handle_direct_messages])