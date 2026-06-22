import os
import logging
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from google.adk.sessions import VertexAiSessionService
from slack_bolt.async_app import AsyncApp

from story_refiner.agents import interactive_agent, oneoff_agent
from story_refiner.slack_handlers import register_slack_handlers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


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

slack_app = AsyncApp(
token=os.environ.get("SLACK_BOT_TOKEN"),
signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

register_slack_handlers(slack_app, mention_runner=oneoff_runner, dm_runner=interactive_runner, session_service=session_service)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    logger.info(f"⚡ Asana User Story Refiner Bot launching via Webhooks on port {port}...")
    
    # This works flawlessly now without any clashing loops!
    slack_app.start(port=port)