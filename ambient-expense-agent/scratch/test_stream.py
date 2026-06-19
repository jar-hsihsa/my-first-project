import json
from expense_agent.agent_runtime_app import agent_runtime

def main():
    data = {
        "amount": 150.0,
        "submitter": "alice@example.com",
        "category": "Meals",
        "description": "Lunch with client",
        "date": "2026-06-18"
    }
    print("Testing stream_query with amount 150.0:")
    message_dict = {"parts": [{"text": json.dumps(data)}], "role": "user"}
    try:
        for chunk in agent_runtime.stream_query(message=message_dict, user_id="test_user"):
            print("CHUNK:", chunk)
    except Exception as e:
        print("Error stream_query:", e)

if __name__ == "__main__":
    main()
