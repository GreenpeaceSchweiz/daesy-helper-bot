import os

import logging
from google.genai import types
from story_refiner.slack_helpers import build_thread_context
from story_refiner.session_utils import get_or_create_session

logger = logging.getLogger(__name__)

def register_slack_handlers(slack_app, mention_runner, dm_runner, session_service):
    """Registers event handlers to the slack app routing table."""
    
    @slack_app.event("app_mention")
    async def handle_app_mention(ack, event, client):
        await ack()
        
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))
        
        logger.info(f"🔄 Processing mention for thread {thread_ts}")

        placeholder_response = await client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="⏳ *Thinking...* One moment while I review this."
        )
        # Capture the unique timestamp of the placeholder message
        message_ts = placeholder_response["ts"]
    
        # 1. Build structured context from Slack
        context_text = await build_thread_context(client, channel_id, thread_ts)
        content = types.Content(role='user', parts=[types.Part(text=context_text)])

        # 2. Manage ADK/Vertex AI Session
        session_id = await get_or_create_session(
            session_service, 
            app_name=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"), 
            user_id=user_id, 
            thread_ts=thread_ts
        )
        
        # 3. Stream Runner output & reply back
        async for runner_event in mention_runner.run_async(
            user_id=user_id, 
            session_id=session_id, 
            new_message=content
        ):
            if runner_event.is_final_response():
                final_response = runner_event.content.parts[0].text
                logger.info(f"Agent Response completed for user {user_id}")

                await client.chat_postMessage(
                    channel=channel_id,
                    ts=message_ts,
                    text=final_response
                )


    @slack_app.event("message")
    async def handle_direct_messages(ack, event, client):
        await ack()
        
        # Guard: Only process if it's a DM (channel starts with 'D') and NOT a bot message
        channel_id = event.get("channel", "")
        if not channel_id.startswith("D") or event.get("bot_id"):
            return

        user_id = event.get("user")
        text_content = event.get("text", "")
        thread_ts = event.get("thread_ts", event.get("ts"))

        logger.info(f"💬 Processing Direct Message context for session {thread_ts}")

        placeholder_response = await client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="⏳ *Thinking...* One moment while I review this."
        )
        # Capture the unique timestamp of the placeholder message
        message_ts = placeholder_response["ts"]

        # 1. Standardize text structure for Vertex AI payload
        content = types.Content(role='user', parts=[types.Part(text=text_content)])

        # 2. Enforce strict URL-safe characters for Vertex AI constraints
        clean_ts = thread_ts.replace(".", "")
        target_session_id = f"dm-{clean_ts}" # URL-safe format: letters and hyphens only
        app_name_id = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")

        # 3. Stream & execute via your runner framework (mirroring your mention handler)
        try:
            async for runner_event in dm_runner.run_async(
                user_id=user_id, 
                session_id=target_session_id, 
                new_message=content
            ):
                if runner_event.is_final_response():
                    final_response = runner_event.content.parts[0].text
                    await client.chat_postMessage(channel=channel_id, ts=message_ts, text=final_response)
        except Exception: # Catching SessionNotFoundError
            logger.info(f"✨ Provisioning new backend DM session: {target_session_id}")
            await session_service.create_session(
                app_name=app_name_id,
                user_id=user_id,
                session_id=target_session_id
            )
            async for runner_event in dm_runner.run_async(
                user_id=user_id, 
                session_id=target_session_id, 
                new_message=content
            ):
                if runner_event.is_final_response():
                    final_response = runner_event.content.parts[0].text
                    await client.chat_postMessage(channel=channel_id, ts=message_ts, text=final_response)