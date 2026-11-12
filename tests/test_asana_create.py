import json
from unittest.mock import Mock

# 1. Import your existing function from your tools file
from daesy_helper_bot.services.asana import create_asana_task

def test_task_creation():
    print("Testing your `create_asana_task` function directly...\n")

    # 2. Create a mock ToolContext with a state that has the creator email
    mock_context = Mock()
    mock_context.state.get.return_value = "dch@greenpeace.org"

    # 3. Define standard test inputs (including rich characters like '&' and newlines)
    test_payload = {
        "title": "DEBUG: Test Task via Unit Test",
        "user_story": "As a developer, I want to test this function locally & catch raw errors.",
        "priority_rationale": "High priority because debugging through agents is slow.",
        "acceptance_criteria": "1. Task must be created.\n2. Formatting must render correctly.",
        "refinement_notes": "No extra configuration needed. Tested via unit-test.py script.",
        "tool_context": mock_context
    }

    # 4. Call your actual function
    result = create_asana_task(**test_payload)
    print(f"Result returned by function:\n{result}")



if __name__ == "__main__":
    test_task_creation()