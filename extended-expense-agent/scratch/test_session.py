import json
import uuid
from expense_agent.agent_runtime_app import agent_runtime

def main():
    session_id = str(uuid.uuid4())
    data = {
        "amount": 150.0,
        "submitter": "alice@example.com",
        "category": "Meals",
        "description": "Lunch with client",
        "date": "2026-06-18"
    }
    print(f"Testing stream_query with session_id={session_id}")
    message_dict = {"parts": [{"text": json.dumps(data)}], "role": "user"}
    try:
        events = []
        for chunk in agent_runtime.stream_query(message=message_dict, user_id="test_user", session_id=session_id):
            print("CHUNK:", chunk)
            events.append(chunk)
            
        print("Now sending Approve...")
        message_dict_2 = {"parts": [{"text": "Approve"}], "role": "user"}
        for chunk in agent_runtime.stream_query(message=message_dict_2, user_id="test_user", session_id=session_id):
            print("CHUNK 2:", chunk)
            
    except Exception as e:
        print("Error stream_query:", e)

if __name__ == "__main__":
    main()
