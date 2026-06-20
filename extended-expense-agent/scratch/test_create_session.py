from expense_agent.agent_runtime_app import agent_runtime

def main():
    try:
        session_dict = agent_runtime.create_session(user_id="streamlit_user")
        session_id = session_dict["id"]
        print("Created session:", session_id)
        
        events = []
        message_dict = {"parts": [{"text": '{"amount": 150.0, "submitter": "alice@example.com", "category": "Meals", "description": "Lunch with client", "date": "2026-06-18"}'}], "role": "user"}
        print("--- SUBMITTING EXPENSE ---")
        for chunk in agent_runtime.stream_query(message=message_dict, user_id="streamlit_user", session_id=session_id):
            print("SUBMIT CHUNK:", chunk)
            
        print("--- APPROVING EXPENSE ---")
        message_dict2 = {
            "role": "tool",
            "parts": [{
                "function_response": {
                    "id": "approval_1",
                    "name": "adk_request_input",
                    "response": {"output": "Approve"}
                }
            }]
        }
        for chunk in agent_runtime.stream_query(message=message_dict2, user_id="streamlit_user", session_id=session_id):
            print("APPROVE CHUNK:", chunk)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
