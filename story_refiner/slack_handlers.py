import logging
from google.genai import types
from story_refiner.slack_helpers import build_thread_context
from story_refiner.session_utils import get_or_create_session

logger = logging.getLogger(__name__)

def register_slack_handlers(slack_app, oneoff_runner, session_service):
    """Registers event handlers to the slack app routing table."""
    
    @slack_app.event("app_mention")
    async def handle_app_mention(ack, event, client):
        await ack()
        
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))
        
        logger.info(f"🔄 Processing mention for thread {thread_ts}")

        # 1. Build structured context from Slack
        context_text = await build_thread_context(client, channel_id, thread_ts)
        content = types.Content(role='user', parts=[types.Part(text=context_text)])

        # 2. Manage ADK/Vertex AI Session
        session = await get_or_create_session(
            session_service, 
            app_name="oneoff_story_refiner", 
            user_id=user_id, 
            thread_ts=thread_ts
        )
        
        # 3. Stream Runner output & reply back
        async for runner_event in oneoff_runner.run_async(
            user_id=user_id, 
            session_id=session.id, 
            new_message=content
        ):
            if runner_event.is_final_response():
                final_response = runner_event.content.parts[0].text
                logger.info(f"Agent Response completed for user {user_id}")

                await client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=final_response
                )

    @slack_app.event("assistant_thread_started")
    async def handle_assistant_thread_started(ack, event, client):
        await ack()
        
        # Grab the context of the new assistant thread
        assistant_thread = event.get("assistant_thread", {})
        channel_id = assistant_thread.get("channel_id")
        context = assistant_thread.get("context", {})
        user_id = context.get("user_id")
        
        if channel_id:
            welcome_text = (
                f"👋 Hi! How can I help you today?\n\n"
                "Feel free to message in any language you'd like."
            )
            
            # Post a friendly greeting directly into the new chat window
            await client.chat_postMessage(
                channel=channel_id,
                text=welcome_text
            )