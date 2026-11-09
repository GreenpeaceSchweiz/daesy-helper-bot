from daesy_helper_bot.services.asana import search_asana_tasks

def test_task_search():
    print("Testing your `search_asana_tasks` function directly...\n")

    test_payload = [
        "streuwurf",
        "outhouse"
    ]

    # 3. Call your actual function
    result = search_asana_tasks(test_payload)
    print(f"Result returned by function:\n{result}")


if __name__ == "__main__":
    test_task_search()
