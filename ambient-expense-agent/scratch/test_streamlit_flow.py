class DummySt:
    def __init__(self):
        self.session_state = {}
        self.output = []
    
    def markdown(self, text):
        self.output.append(("markdown", text))
    def subheader(self, text):
        self.output.append(("subheader", text))
    def json(self, obj):
        self.output.append(("json", obj))
    def rerun(self):
        self.output.append(("rerun", True))
    def success(self, text):
        self.output.append(("success", text))

st = DummySt()

def simulate_run(action="submit"):
    st.output = []
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = "123"
    if "waiting_for_input" not in st.session_state:
        st.session_state["waiting_for_input"] = False
    if "final_output" not in st.session_state:
        st.session_state["final_output"] = None
    if "agent_messages" not in st.session_state:
        st.session_state["agent_messages"] = []

    def process_events(events):
        final_output = None
        paused = False
        
        for event in events:
            content = event.get("content")
            if content and "parts" in content:
                for part in content["parts"]:
                    if "text" in part:
                        st.session_state["agent_messages"].append(part["text"])
                    if "function_call" in part:
                        fn_call = part["function_call"]
                        if fn_call.get("name") == "adk_request_input":
                            paused = True
                            
            if "output" in event:
                final_output = event["output"]
                
        st.session_state["waiting_for_input"] = paused
        if not paused and final_output:
            st.session_state["final_output"] = final_output

    if action == "submit":
        st.session_state["waiting_for_input"] = False
        st.session_state["final_output"] = None
        st.session_state["agent_messages"] = []
        
        events = [
            {"content": {"parts": [{"text": "Checking expense..."}]}},
            {"content": {"parts": [{"function_call": {"name": "adk_request_input"}}]}}
        ]
        process_events(events)

    if action == "approve" and st.session_state["waiting_for_input"]:
        events = [
            {"content": {"parts": [{"text": "Expense approved."}]}},
            {"output": {"status": "approved"}}
        ]
        process_events(events)
        st.rerun()

    if st.session_state.get("agent_messages"):
        st.subheader("Agent Output")
        for msg in st.session_state["agent_messages"]:
            st.markdown(msg)

    if not st.session_state["waiting_for_input"] and st.session_state.get("final_output"):
        st.success("Workflow completed!")
        st.subheader("Final State Output")
        st.json(st.session_state["final_output"])

    return st.output

print("--- RUN 1: Submit ---")
out1 = simulate_run("submit")
for o in out1: print(o)

print("--- RUN 2: Approve ---")
out2 = simulate_run("approve")
for o in out2: print(o)

print("--- RUN 3: After rerun ---")
out3 = simulate_run("none")
for o in out3: print(o)
