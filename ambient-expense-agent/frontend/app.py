import streamlit as st
import json
import asyncio
from expense_agent.agent import app as adk_app

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

async def run_agent(data):
    events = []
    # Using adk_app.stream
    async for event in adk_app.stream(input=data):
        events.append(event)
    return events

if st.button("Submit Expense"):
    try:
        data = json.loads(json_input)
        
        with st.spinner("Processing expense..."):
            # Run the asynchronous agent loop
            events = asyncio.run(run_agent(data))
            
            st.subheader("Agent Output")
            
            for event in events:
                if getattr(event, "content", None) and event.content:
                    for part in event.content.parts:
                        st.markdown(part.text)
                
                # Check for RequestInput which pauses the workflow
                if type(event).__name__ == 'RequestInput':
                    st.warning(event.message)
                    st.info(f"Agent paused and requires human input. Interrupt ID: {event.interrupt_id}")
                    
                if getattr(event, "output", None):
                    st.json(event.output)
                    
    except json.JSONDecodeError:
        st.error("Invalid JSON input. Please correct the JSON and try again.")
    except Exception as e:
        st.error(f"An error occurred: {e}")
