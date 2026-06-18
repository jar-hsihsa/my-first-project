import streamlit as st
import json
import asyncio
from expense_agent.agent_runtime_app import agent_runtime

st.set_page_config(page_title="Expense Agent Frontend", layout="centered")

st.title("Expense Agent Frontend")
st.write("Submit your expense report in JSON format below:")

default_json = """{
  "amount": 50.0,
  "submitter": "alice@example.com",
  "category": "Meals",
  "description": "Lunch with client",
  "date": "2026-06-18"
}"""

json_input = st.text_area("Expense JSON", value=default_json, height=200)

def run_agent(data):
    events = []
    message_dict = {"parts": [{"text": json.dumps(data)}], "role": "user"}
    # Using agent_runtime.stream_query which accepts message and user_id
    for event in agent_runtime.stream_query(message=message_dict, user_id="streamlit_user"):
        events.append(event)
    return events

if st.button("Submit Expense"):
    try:
        data = json.loads(json_input)
        
        with st.spinner("Processing expense..."):
            # Run the synchronous agent loop
            events = run_agent(data)
            
            st.subheader("Agent Output")
            
            final_output = None
            for event in events:
                # Process text content
                content = event.get("content")
                if content and "parts" in content:
                    for part in content["parts"]:
                        if "text" in part:
                            st.markdown(part["text"])
                
                # Check for RequestInput which pauses the workflow
                if event.get("type") == 'RequestInput':
                    st.warning(event.get("message", "Agent paused for input."))
                    st.info(f"Agent paused and requires human input. Interrupt ID: {event.get('interrupt_id')}")
                    
                # Store the latest raw JSON output
                if "output" in event:
                    final_output = event["output"]
            
            if final_output:
                st.subheader("Final State Output")
                st.json(final_output)
                    
    except json.JSONDecodeError:
        st.error("Invalid JSON input. Please correct the JSON and try again.")
    except Exception as e:
        st.error(f"An error occurred: {e}")
