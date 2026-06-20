from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import json

from expense_agent.agent import root_agent

session_service = InMemorySessionService()
session = session_service.create_session_sync(user_id="test_user", app_name="test")
runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

# Send PII payload
pii_payload = {
    "amount": 150.0,
    "submitter": "alice@company.com",
    "category": "software",
    "description": "Purchased hardware using card 4242-4242-4242-4242 and SSN 000-12-3456",
    "date": "2026-06-06"
}
message = types.Content(role="user", parts=[types.Part.from_text(text=json.dumps(pii_payload))])

print("--- Running first turn ---")
events = list(runner.run(new_message=message, user_id="test_user", session_id=session.id))
for ev in events:
    # Print custom messages or text
    if hasattr(ev, 'message') and ev.message:
        print("Interrupt Message:", ev.message)

print("--- Resuming with Approve ---")
resume_msg = types.Content(role="user", parts=[types.Part.from_text(text="Approve")])
events2 = list(runner.run(new_message=resume_msg, user_id="test_user", session_id=session.id))
for ev in events2:
    if ev.content and ev.content.parts:
        for p in ev.content.parts:
            if p.text:
                print("Final Event Text:\n", p.text)
