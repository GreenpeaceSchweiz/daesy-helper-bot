from pathlib import Path
from google.adk.agents.llm_agent import Agent
from story_refiner.asana import create_asana_task


# Get the directory path where agent.py lives and read your long prompt
CURRENT_DIR = Path(__file__).parent
instruction_path = CURRENT_DIR / "instruction.md"
with open(instruction_path, "r", encoding="utf-8") as f:
    agent_instruction = f.read()


# Define the ADK Agent
root_agent = Agent(
    name="user_story_refiner",
    model="gemini-3.1-flash-lite",
    description="An expert Agile Product Owner that refines vague user inputs into strict User Stories.",
    instruction=agent_instruction,
    # Hand the python tool to the model
    tools=[create_asana_task] 
)