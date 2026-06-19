import streamlit as st
import json
import asyncio
from expense_agent.agent_runtime_app import agent_runtime

import uuid

st.set_page_config(page_title="Expense Agent Frontend", layout="centered")

if "session_id" not in st.session_state:
    session = agent_runtime.create_session(user_id="streamlit_user")
    st.session_state.session_id = session["id"]
if "waiting_for_input" not in st.session_state:
    st.session_state.waiting_for_input = False
if "interrupt_message" not in st.session_state:
    st.session_state.interrupt_message = ""
if "final_output" not in st.session_state:
    st.session_state.final_output = None
if "interrupt_id" not in st.session_state:
    st.session_state.interrupt_id = None
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = []

st.title("Expense Agent Frontend")
st.write("Submit your expense report in JSON format below:")

json_input = st.text_area("Expense JSON", value="", height=200, placeholder="Paste your expense JSON here...")

def run_agent(payload_dict):
    events = []
    for event in agent_runtime.stream_query(
        message=payload_dict, 
        user_id="streamlit_user", 
        session_id=st.session_state.session_id
    ):
        events.append(event)
    return events

def process_events(events):
    final_output = None
    paused = False
    
    for event in events:
        content = event.get("content")
        if content and "parts" in content:
            for part in content["parts"]:
                if "text" in part:
                    st.session_state.agent_messages.append(part["text"])
                if "function_call" in part:
                    fn_call = part["function_call"]
                    if fn_call.get("name") == "adk_request_input":
                        args = fn_call.get("args", {})
                        st.session_state.interrupt_message = args.get("message", "Agent paused for human input.")
                        st.session_state.interrupt_id = fn_call.get("id")
                        paused = True
                        
        if "output" in event:
            final_output = event["output"]
            
    st.session_state.waiting_for_input = paused
    if not paused and final_output:
        st.session_state.final_output = final_output

if st.button("Submit Expense"):
    try:
        # Reset state on new submission
        session = agent_runtime.create_session(user_id="streamlit_user")
        st.session_state.session_id = session["id"]
        st.session_state.waiting_for_input = False
        st.session_state.final_output = None
        st.session_state.agent_messages = []
        
        data = json.loads(json_input)
        with st.spinner("Processing expense..."):
            message_dict = {"parts": [{"text": json.dumps(data)}], "role": "user"}
            events = run_agent(message_dict)
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
                payload = {
                    "role": "tool",
                    "parts": [{
                        "function_response": {
                            "id": st.session_state.interrupt_id,
                            "name": "adk_request_input",
                            "response": {"output": "Approve"}
                        }
                    }]
                }
                events = run_agent(payload)
                process_events(events)
                st.rerun()
    with col2:
        if st.button("Reject Expense"):
            with st.spinner("Resuming workflow..."):
                payload = {
                    "role": "tool",
                    "parts": [{
                        "function_response": {
                            "id": st.session_state.interrupt_id,
                            "name": "adk_request_input",
                            "response": {"output": "Reject"}
                        }
                    }]
                }
                events = run_agent(payload)
                process_events(events)
                st.rerun()

    st.markdown("---")
    custom_message = st.text_input("Or enter a custom response:")
    if st.button("Submit Custom Response"):
        if custom_message.strip():
            with st.spinner("Resuming workflow..."):
                payload = {
                    "role": "tool",
                    "parts": [{
                        "function_response": {
                            "id": st.session_state.interrupt_id,
                            "name": "adk_request_input",
                            "response": {"output": custom_message}
                        }
                    }]
                }
                events = run_agent(payload)
                process_events(events)
                st.rerun()
        else:
            st.warning("Please enter a message before submitting.")

if st.session_state.agent_messages:
    st.subheader("Agent Output")
    for msg in st.session_state.agent_messages:
        st.markdown(msg)

# If finished after an interrupt, display the final output that was saved
if not st.session_state.waiting_for_input and st.session_state.final_output:
    st.success("Workflow completed!")
    st.subheader("Final State Output")
    st.json(st.session_state.final_output)
