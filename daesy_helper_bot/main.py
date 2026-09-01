import os
import logging
from dotenv import load_dotenv

from google.adk.runners import Runner


from daesy_helper_bot.session_utils import CachedVertexAiSessionService
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.asgi.async_handler import AsyncSlackRequestHandler
from daesy_helper_bot.agents.agents import interactive_agent, oneoff_agent
from daesy_helper_bot.slack.handlers import register_slack_handlers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


# 1. Initialize State Frameworks
session_service = CachedVertexAiSessionService(
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

# Function to launch the server locally during development
def dev():
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"⚡ Daesy Helper Bot launching via Uvicorn on port {port}...")
    
    # Point Uvicorn to the absolute import path of the ASGI 'api' application
    uvicorn.run("daesy_helper_bot.main:api", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    dev()