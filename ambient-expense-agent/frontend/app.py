import streamlit as st
import json
import asyncio
from expense_agent.agent_runtime_app import agent_runtime

import uuid

st.set_page_config(page_title="Expense Agent Frontend", layout="centered")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "waiting_for_input" not in st.session_state:
    st.session_state.waiting_for_input = False
if "interrupt_message" not in st.session_state:
    st.session_state.interrupt_message = ""
if "final_output" not in st.session_state:
    st.session_state.final_output = None

st.title("Expense Agent Frontend")
st.write("Submit your expense report in JSON format below:")

default_json = """{
  "amount": 150.0,
  "submitter": "alice@example.com",
  "category": "Meals",
  "description": "Lunch with client",
  "date": "2026-06-18"
}"""

json_input = st.text_area("Expense JSON", value=default_json, height=200)

def run_agent(message_text):
    events = []
    message_dict = {"parts": [{"text": message_text}], "role": "user"}
    for event in agent_runtime.stream_query(
        message=message_dict, 
        user_id="streamlit_user", 
        session_id=st.session_state.session_id
    ):
        events.append(event)
    return events

def process_events(events):
    st.subheader("Agent Output")
    final_output = None
    paused = False
    
    for event in events:
        content = event.get("content")
        if content and "parts" in content:
            for part in content["parts"]:
                if "text" in part:
                    st.markdown(part["text"])
                if "function_call" in part:
                    fn_call = part["function_call"]
                    if fn_call.get("name") == "adk_request_input":
                        args = fn_call.get("args", {})
                        st.session_state.interrupt_message = args.get("message", "Agent paused for human input.")
                        paused = True
                        
        if "output" in event:
            final_output = event["output"]
            
    st.session_state.waiting_for_input = paused
    if not paused and final_output:
        st.session_state.final_output = final_output
        st.subheader("Final State Output")
        st.json(final_output)

if st.button("Submit Expense"):
    try:
        # Reset state on new submission
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.waiting_for_input = False
        st.session_state.final_output = None
        
        data = json.loads(json_input)
        with st.spinner("Processing expense..."):
            events = run_agent(json.dumps(data))
            process_events(events)
            
    except json.JSONDecodeError:
        st.error("Invalid JSON input. Please correct the JSON and try again.")
    except Exception as e:
        st.error(f"An error occurred: {e}")

if st.session_state.waiting_for_input:
    st.warning(st.session_state.interrupt_message)
    st.info("The workflow has paused. Please provide your input below to resume.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve Expense", type="primary"):
            with st.spinner("Resuming workflow..."):
                events = run_agent("Approve")
                process_events(events)
                st.rerun()
    with col2:
        if st.button("Reject Expense"):
            with st.spinner("Resuming workflow..."):
                events = run_agent("Reject")
                process_events(events)
                st.rerun()

# If finished after an interrupt, display the final output that was saved
if not st.session_state.waiting_for_input and st.session_state.final_output:
    st.success("Workflow completed!")
