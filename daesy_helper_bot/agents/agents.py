from pathlib import Path
from google.adk.agents.llm_agent import Agent
from daesy_helper_bot.services.asana import create_asana_task


# Get the directory path where agent.py lives and read your long prompt
CURRENT_DIR = Path(__file__).parent
instruction_path = CURRENT_DIR / "instruction_interactive.md"
with open(instruction_path, "r", encoding="utf-8") as f:
    instruction_interactive = f.read()
instruction_path = CURRENT_DIR / "instruction_oneoff.md"
with open(instruction_path, "r", encoding="utf-8") as f:
    instruction_oneoff = f.read()

# TO DO: Create subagents for new requests vs repeat/daily business tasks
interactive_agent = Agent(
    name="user_story_refiner",
    model="gemini-3.5-flash",
    description="An expert Agile Product Owner that refines vague user inputs into strict User Stories.",
    instruction=instruction_interactive,
    # Hand the python tool to the model
    tools=[create_asana_task] 
)

oneoff_agent = Agent(
    name="user_story_writer",
    model="gemini-3.5-flash",
    description="An expert Agile Product Owner that translates conversation history into strict User Stories.",
    instruction=instruction_oneoff,
    # Hand the python tool to the model
    tools=[create_asana_task] 
)