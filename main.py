import asyncio
import os
import logging
from dotenv import load_dotenv

from google.adk.integrations.slack import SlackRunner
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.sessions import VertexAiSessionService
from slack_bolt.app.async_app import AsyncApp

from story_refiner.agents import interactive_agent, oneoff_agent
from story_refiner.slack_handlers import register_slack_handlers
from story_refiner.session_utils import custom_vertex_session_id_generator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

async def main():

    # 1. Initialize State Frameworks
    session_service = VertexAiSessionService(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "eu"),
        agent_engine_id=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")
    )
    #session_service = InMemorySessionService()

    # 2. Setup ADK Runners
    interactive_runner = Runner(
        agent=interactive_agent,
        app_name=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"),
        session_service=session_service,
        auto_create_session=False,
    )

    oneoff_runner = Runner(
        agent=oneoff_agent,
        app_name=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"),
        session_service=session_service,
        auto_create_session=False,
    )

    # 3. Setup Engines & Register Split Modules
    slack_app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))
    register_slack_handlers(slack_app, mention_runner=oneoff_runner, dm_runner=interactive_runner, session_service=session_service)

    # 4. Bind and Start Application
    slack_runner = SlackRunner(runner=interactive_runner, slack_app=slack_app)

    app_token = os.environ.get("SLACK_APP_TOKEN")

    logger.info("⚡ Asana User Story Refiner Bot is launching via Socket Mode...")
    await slack_runner.start(app_token=app_token)

if __name__ == "__main__":
    asyncio.run(main())