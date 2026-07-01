import asyncio
import nest_asyncio
import logging
import json
from expense_agent.agent_runtime_app import agent_runtime
from frontend.database import save_expense, save_pending_approval
import streamlit as st

def run_agent(payload_dict, specific_session_id=None):
  session_id_to_use = specific_session_id if specific_session_id else st.session_state.session_id
  
  async def _run():
    events = []
    async for event in agent_runtime.async_stream_query(
      message=payload_dict,
      user_id="streamlit_user",
      session_id=session_id_to_use,
    ):
      events.append(event)
    return events
    
  return asyncio.run(_run())


def process_events(events, run_session_id=None, submitter_email=None):
  final_output = None
  paused = False
  session_to_track = run_session_id if run_session_id else st.session_state.session_id

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
            st.session_state.interrupt_message = args.get(
              "message", "Agent paused for human input."
            )
            st.session_state.interrupt_id = fn_call.get("id")
            paused = True
            
            receipt_bytes = st.session_state.get("submitted_receipt_image", "")
            raw_json = st.session_state.get("raw_json", "")
            if "---JSON---" in st.session_state.interrupt_message:
              parts = st.session_state.interrupt_message.split("---JSON---")
              st.session_state.interrupt_message = parts[0].strip()
              raw_json = parts[1].strip()
              # Update session state with parsed values for future use if needed
              st.session_state.raw_json = raw_json


            if (
              st.session_state.role == "Employee"
              and not st.session_state.get("from_review_submit", False)
              and (
                args.get("interruptId") == "employee_review"
                or args.get("interrupt_id") == "employee_review"
                or fn_call.get("id") == "employee_review"
              )
            ):
              import json
              try:
                st.session_state.review_expense_data = json.loads(raw_json)
                st.session_state.review_session_to_track = session_to_track
                st.session_state.review_is_paused = True
                st.session_state.review_interrupt_id = fn_call.get("id")
              except Exception:
                pass
            else:
              save_pending_approval(
                session_to_track,
                fn_call.get("id"),
                st.session_state.interrupt_message,
                st.session_state.email,
                receipt_bytes,
                raw_json
              )
              try:
                raw_json_data = json.loads(raw_json)
                if raw_json_data.get("is_manual_submit"):
                  st.session_state.manual_submit_success = True
              except Exception:
                pass

    if "output" in event:
      final_output = event["output"]

  st.session_state.waiting_for_input = paused
  if not paused and final_output:
    st.session_state.final_output = final_output
    if isinstance(final_output, dict) and "expense" in final_output:
      # Session-level guard: only save once per ADK session to prevent
      # duplicate inserts caused by Streamlit reruns re-executing this block.
      already_saved = session_to_track in st.session_state.get("saved_session_ids", set())
      if not already_saved:
        if submitter_email:
          final_output["expense"]["submitter"] = submitter_email
        elif not final_output["expense"].get("submitter") or final_output["expense"]["submitter"] == "employee@acmecorp.com":
          final_output["expense"]["submitter"] = st.session_state.email
          
        if (
          st.session_state.role == "Employee"
          and not st.session_state.get("from_review_submit", False)
          and not final_output["expense"].get("is_manual_submit")
        ):
          st.session_state.review_expense_data = final_output["expense"]
          st.session_state.review_session_to_track = session_to_track
        else:
          decision = final_output.get("decision") or "Approved"
          save_expense(final_output["expense"], decision)
          if session_to_track:
            st.session_state.saved_session_ids.add(session_to_track)
          if final_output["expense"].get("is_manual_submit"):
            st.session_state.manual_submit_success = True


def parse_interrupt_details(msg: str) -> dict:
  """Best-effort extraction of structured data from the interrupt message."""
  details = {}
  for line in msg.splitlines():
    line = line.strip()
    if line.startswith("Expense of $"):
      try:
        rest = line[len("Expense of $"):]
        amt_str, rest2 = rest.split(" by ", 1)
        details["amount"] = amt_str.strip()
        sub_str, rest3 = rest2.split(" for '", 1)
        details["submitter"] = sub_str.strip()
        desc_str = rest3.rsplit("' requires review", 1)[0]
        details["description"] = desc_str.strip()
      except Exception:
        pass
    if "Risk Assessment:" in line:
      details["risk"] = line.split("Risk Assessment:", 1)[1].strip()
    if "SECURITY EVENT FLAGGED" in line:
      details["security_flag"] = True
    if "Prompt Injection Detected" in line:
      details["injection"] = True
    if "Redacted PII Categories:" in line:
      details["pii"] = line.split("Redacted PII Categories:", 1)[1].strip()
  return details


