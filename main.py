import asyncio
import os
from dotenv import load_dotenv

# Import your real, working agent from your package
from story_refiner.agents import interactive_agent

# Import the modern ADK components from the example you found
from google.adk.integrations.slack import SlackRunner
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from slack_bolt.app.async_app import AsyncApp

load_dotenv()

async def main():
    # 1. Setup the ADK Runner wrapping your existing User Story Refiner agent
    runner = Runner(
        agent=interactive_agent,
        app_name="asana_story_refiner",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    # 2. Initialize the Slack Bolt App engine using your standard xoxb- bot token
    slack_app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))

    # 3. Hand everything over to ADK's native Slack integration handler
    slack_runner = SlackRunner(runner=runner, slack_app=slack_app)

    # 4. Grab your new App Token for Socket Mode authorization
    app_token = os.environ.get("SLACK_APP_TOKEN")

    print("⚡ Asana User Story Refiner Bot is launching via Socket Mode...")
    # This keeps the script running, listening natively to your Slack workspace
    await slack_runner.start(app_token=app_token)

if __name__ == "__main__":
    asyncio.run(main())