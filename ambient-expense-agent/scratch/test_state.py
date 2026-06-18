from google.adk.workflow import Workflow, node, START, Edge
from google.adk.apps import App
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import json

from typing import Any

@node
def first_node(ctx: Context, node_input: Any):
    return Event(output="ok", state={"key1": "val1"})

@node
def second_node(ctx: Context, node_input: Any):
    return Event(output="ok", state={"key2": "val2"})

@node
def third_node(ctx: Context, node_input: Any):
    print("DIR OF STATE:", dir(ctx.state))
    print("REPR OF STATE:", repr(ctx.state))
    print("KEY1:", ctx.state.get("key1"))
    print("KEY2:", ctx.state.get("key2"))
    return Event(output="ok")

w = Workflow(
    name="test_wf",
    edges=[
        Edge(from_node=START, to_node=first_node),
        Edge(from_node=first_node, to_node=second_node),
        Edge(from_node=second_node, to_node=third_node)
    ]
)

session_service = InMemorySessionService()
session = session_service.create_session_sync(user_id="test_user", app_name="test")
runner = Runner(agent=w, session_service=session_service, app_name="test")

msg = types.Content(role="user", parts=[types.Part.from_text(text="hello")])
list(runner.run(new_message=msg, user_id="test_user", session_id=session.id))
