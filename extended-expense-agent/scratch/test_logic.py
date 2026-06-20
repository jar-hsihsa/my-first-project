import json

events = [
    {'content': {'parts': [{'function_call': {'id': 'approval_1', 'args': {'interruptId': 'approval_1', 'payload': None, 'message': "...", 'response_schema': None}, 'name': 'adk_request_input'}}]}, 'invocation_id': '...', 'author': 'ambient_expense_agent', 'actions': {'state_delta': {}, 'artifact_delta': {}, 'requested_auth_configs': {}, 'requested_tool_confirmations': {}}, 'node_info': {'path': 'ambient_expense_agent@1/human_approval_gate@1'}, 'long_running_tool_ids': ['approval_1'], 'id': '...', 'timestamp': 123}
]

paused = False
final_output = None
for event in events:
    content = event.get("content")
    if content and "parts" in content:
        for part in content["parts"]:
            if "text" in part:
                print("Got text")
            if "function_call" in part:
                fn_call = part["function_call"]
                print("Found function_call with name:", fn_call.get("name"))
                if fn_call.get("name") == "adk_request_input":
                    args = fn_call.get("args", {})
                    interrupt_message = args.get("message", "Agent paused for human input.")
                    paused = True
    if "output" in event:
        final_output = event["output"]

print(f"Paused: {paused}, Final output: {final_output}")
