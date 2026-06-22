import os

import logging
from typing import Any
from google.genai import types
from story_refiner.slack_helpers import build_thread_context
from story_refiner.session_utils import get_or_create_session

logger = logging.getLogger(__name__)

def register_slack_handlers(slack_app, mention_runner, dm_runner, session_service):
    """
    Registers event handlers to the slack app routing table.
    Supports distinct runners for public mentions vs. private DMs.
    """
    
    # --- Shared Core Message Handler ---
    async def _handle_message(event: dict[str, Any], say: Any, runner: Any, thinking_ts: str):
        """Processes the message payload and streams responses from the designated ADK runner."""
        text = event.get("text", "")
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")

        if not text or not user_id or not channel_id:
            return 

        # Create a unique session tracking key
        session_id = await get_or_create_session(
            session_service, 
            app_name=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"), 
            event=event
        )
        
        new_message = types.Content(role="user", parts=[types.Part(text=text)])
        
        try:
            # Stream chunks from whichever runner was provided to this call
            async for chunk in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
            ):
                if chunk.content and chunk.content.parts:
                    for part in chunk.content.parts:
                        if part.text:
                            if thinking_ts:
                                # Replace the "Thinking..." text with the first chunk of real output
                                await slack_app.client.chat_update(
                                    channel=channel_id,
                                    ts=thinking_ts,
                                    text=part.text,
                                )
                                thinking_ts = None
                            else:
                                # Stream subsequent chunks
                                await say(text=part.text, thread_ts=thread_ts)
                                
            # If the stream completed but nothing was written, clean up the placeholder
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


    # --- Route 1: App Mentions (@bot-name in Channels) ---
    @slack_app.event("app_mention")
    async def handle_app_mention(ack, event, say, client):
        await ack()
        
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))

        # Post a placeholder message so the user knows the agent is working
        thinking_response = await say(text="_Thinking..._", thread_ts=thread_ts)
        thinking_ts = thinking_response.get("ts")
        
        logger.info(f"🔄 Processing channel app_mention for thread {thread_ts}")

        # 1. Build complex thread context history for your user story refinement
        context_text = await build_thread_context(client, channel_id, thread_ts)
        event["text"] = context_text  

        # 2. Direct this to the mention-specific runner
        await _handle_message(event, say, mention_runner, thinking_ts)


    # --- Route 2: Direct Messages (1-on-1 DMs with Bot) ---
    @slack_app.event("message")
    async def handle_direct_messages(ack, event, say):
        await ack()
        
        # Skip bot messages to avoid infinite message loops
        if event.get("bot_id") or event.get("bot_profile"):
            return

        # Check if the message is happening inside an IM (Direct Message) channel
        if event.get("channel_type") == "im":
            logger.info(f"💬 Processing 1-on-1 Direct Message from User: {event.get('user')}")

            # Post a placeholder message so the user knows the agent is working
            thread_ts = event.get("thread_ts", event.get("ts"))
            thinking_response = await say(text="_Thinking..._", thread_ts=thread_ts)
            thinking_ts = thinking_response.get("ts")
            
            # Direct this to your separate DM runner (e.g. conversational/interactive agent)
            await _handle_message(event, say, dm_runner, thinking_ts)