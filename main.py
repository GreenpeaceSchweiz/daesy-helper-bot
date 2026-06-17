import asyncio
import os
from dotenv import load_dotenv

from story_refiner.agents import interactive_agent, oneoff_agent

from google.adk.integrations.slack import SlackRunner
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from slack_bolt.app.async_app import AsyncApp

from google.genai import types

load_dotenv()

async def main():
    # Create a SINGLE instance of the session service to share memory state
    shared_session_service = InMemorySessionService()

    # 1. Setup the ADK Runners using the shared service
    interactive_runner = Runner(
        agent=interactive_agent,
        app_name="interactive_story_refiner",
        session_service=shared_session_service,
        auto_create_session=True,
    )

    oneoff_runner = Runner(
        agent=oneoff_agent,
        app_name="oneoff_story_refiner",
        session_service=shared_session_service,
        auto_create_session=False,
    )

    # 2. Initialize the Slack Bolt App engine
    slack_app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))

    # 2: respond to app_mention event
    @slack_app.event("app_mention") 
    async def handle_app_mention(ack, event, client):
        await ack()
        
        user_id = event.get("user")
        channel_id = event.get("channel")
        # If the mention is in a thread, use thread_ts. Otherwise, fallback to the message ts.
        thread_ts = event.get("thread_ts", event.get("ts"))
        
        print(f"🔄 Converting thread {thread_ts} directly to ticket via mention")

        # Fetch the permalink to the thread
        try:
            permalink_response = await client.chat_getPermalink(
                channel=channel_id,
                message_ts=thread_ts
            )
            thread_url = permalink_response.get("permalink", "URL not found")
        except Exception as e:
            print(f"⚠️ Could not fetch permalink: {e}")
            thread_url = "URL not found"

        # Fetch the full history of that thread
        thread_history = await client.conversations_replies(
            channel=channel_id, 
            ts=thread_ts
        )
        messages = thread_history.get("messages", [])
        
        context_lines = []
        for msg in messages:
            msg_user = msg.get("user", "System")
            msg_text = msg.get("text", "")
            context_lines.append(f"User <@{msg_user}> said: {msg_text}")
            
        # Append the thread link to the context text passed to the agent
        context_lines.append(f"\nSource Thread Link: {thread_url}")
        
        context_text = "\n".join(context_lines)
        print(context_text)
        content = types.Content(role='user', parts=[types.Part(text=context_text)])

        # 💡 FIX 2: Use the shared session service to create the session
        session = await shared_session_service.create_session(
            app_name="oneoff_story_refiner",
            user_id=user_id
        )
        
        # Now oneoff_runner can find session.id because they share the same backend memory
        async for event in oneoff_runner.run_async(
            user_id=user_id, session_id=session.id, new_message=content):
            if event.is_final_response():
                final_response = event.content.parts[0].text
                print("Agent Response: ", final_response)

                # Paste the final response back into the thread
                await client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=final_response
                )

    # 3. Hand everything over to ADK's native Slack integration handler
    slack_runner = SlackRunner(runner=interactive_runner, slack_app=slack_app)

    # 4. Grab your new App Token for Socket Mode authorization
    app_token = os.environ.get("SLACK_APP_TOKEN")

    print("⚡ Asana User Story Refiner Bot is launching via Socket Mode...")
    await slack_runner.start(app_token=app_token)

if __name__ == "__main__":
    asyncio.run(main())