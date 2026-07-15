import os
import logging
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from google.adk.sessions import VertexAiSessionService
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.asgi.async_handler import AsyncSlackRequestHandler
from agents import interactive_agent, oneoff_agent
from slack.handlers import register_slack_handlers

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

# 1. This is what Uvicorn looks for in production (via main:api)
api = AsyncSlackRequestHandler(slack_app)

# 2. This is ONLY triggered if you manually run `python main.py` locally
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"⚡ Asana User Story Refiner Bot launching via Uvicorn on port {port}...")
    
    # Run Uvicorn programmatically for local dev
    uvicorn.run("main:api", host="0.0.0.0", port=port, reload=True)