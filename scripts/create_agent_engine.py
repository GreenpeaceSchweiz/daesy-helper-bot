import os

import vertexai
from dotenv import load_dotenv


# Initialize the Vertex client using your project variables
client = vertexai.Client(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "eu")
    )

# Create a session storage engine bucket in the cloud
agent_engine = client.agent_engines.create(
    config={
        "display_name": "DaESy Helper Container",
        "description": "Used for the DaESy Helper Slackbot",
    }
)

# This will print an ID string (e.g., "789123456789123456")
print("YOUR_AGENT_ENGINE_ID =", agent_engine.api_resource.name.split("/")[-1])


# For cleanup
#agent_engine.delete(force=True)