import streamlit as st
import json
import base64
import os
import sqlite3
import asyncio
import threading
from datetime import date
from html import escape as html_escape

import nest_asyncio
nest_asyncio.apply()

from expense_agent.agent_runtime_app import agent_runtime
from expense_agent.agent import init_db

if "db_initialized" not in st.session_state:
  init_db()
  st.session_state.db_initialized = True

# Known-valid roles (Bug #8: prevent arbitrary role injection via query params)
_VALID_ROLES = {"Employee", "Admin"}

# ── Background pre-warm ───────────────────────────────────────
# Touch the lazy agent_runtime proxy in a daemon thread so the
# expensive Vertex AI / ADK initialisation runs while the user
# is still on the login screen — not during their first action.
if "runtime_prewarm_started" not in st.session_state:
  st.session_state.runtime_prewarm_started = True
  def _prewarm():
    try:
      agent_runtime._get()  # triggers AgentEngineApp.__init__ + set_up()
    except Exception:
      pass  # errors surface properly when the user actually calls the agent
  threading.Thread(target=_prewarm, daemon=True).start()

# ──────────────────────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────────────────────
st.set_page_config(
  page_title="Acme Corp Expense Portal",
  page_icon="acme_logo.png",
  layout="wide",
)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "acme_logo.png")

# ──────────────────────────────────────────────────────────────
# Custom CSS — matching the CorpTrack reference design
# ──────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Global ──────────────────────────────────────────────── */
html, body, .stApp {
  font-family: 'Inter', sans-serif;
}

/* Hide 'Press Enter to apply' text from text inputs */
div[data-testid="InputInstructions"] {
  display: none !important;
}
.block-container {
  padding-top: 1rem !important;
  max-width: 1200px;
}

/* ── Dark navy sidebar ───────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0F1B3D 0%, #162044 100%) !important;
  color: #FFFFFF !important;
  min-width: 240px !important;
  max-width: 240px !important;
}
section[data-testid="stSidebar"] * {
  color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
  color: #FFFFFF !important;
}
section[data-testid="stSidebar"] hr {
  border-color: rgba(255,255,255,0.12) !important;
}
section[data-testid="stSidebar"] .stButton > button {
  background: transparent !important;
  border: 1px solid rgba(255,255,255,0.2) !important;
  color: #CBD5E1 !important;
  text-align: left !important;
  width: 100% !important;
  justify-content: flex-start !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255,255,255,0.08) !important;
  border-color: rgba(255,255,255,0.3) !important;
}

/* sidebar active nav item */
.nav-active {
  background: rgba(37, 99, 235, 0.25) !important;
  border-left: 3px solid #2563EB;
  padding: 0.55rem 0.75rem;
  border-radius: 0 6px 6px 0;
  margin: 0.15rem 0;
  color: #FFFFFF !important;
  font-weight: 600;
  font-size: 0.92rem;
}
.nav-item {
  padding: 0.55rem 0.75rem 0.55rem 0.95rem;
  margin: 0.15rem 0;
  color: #94A3B8 !important;
  font-size: 0.92rem;
  cursor: pointer;
}
.nav-item:hover {
  color: #E2E8F0 !important;
}
.nav-badge {
  background: #2563EB;
  color: #FFF !important;
  border-radius: 10px;
  padding: 0.1rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  margin-left: 0.35rem;
}
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.25rem 1rem;
}
.sidebar-logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #2563EB, #7C3AED);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  color: #FFF !important;
}
.sidebar-logo-text {
  font-weight: 700;
  font-size: 1.05rem;
  color: #FFFFFF !important;
  line-height: 1.15;
}
.sidebar-logo-sub {
  font-size: 0.72rem;
  color: #94A3B8 !important;
  font-weight: 400;
}

/* ── Top header bar ──────────────────────────────────────── */
.top-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 0;
  margin-bottom: 0.25rem;
  border-bottom: 1px solid #E2E8F0;
}
.top-header h1 {
  font-size: 1.4rem;
  font-weight: 700;
  color: #1E293B;
  margin: 0;
}
.top-header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.9rem;
  color: #64748B;
}
.user-avatar {
  width: 36px;
  height: 36px;
  background: #2563EB;
  color: #FFF !important;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
}

/* ── Breadcrumb ──────────────────────────────────────────── */
.breadcrumb {
  font-size: 0.82rem;
  color: #94A3B8;
  margin-bottom: 1rem;
}
.breadcrumb a {
  color: #2563EB;
  text-decoration: none;
}

/* ── Section title ───────────────────────────────────────── */
.section-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #1E293B;
  margin-bottom: 1rem;
}

/* ── Expense table ───────────────────────────────────────── */
.expense-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  background: #FFFFFF;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.expense-table th {
  background: #F8FAFC;
  color: #64748B;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 2px solid #E2E8F0;
}
.expense-table td {
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
  color: #334155;
  border-bottom: 1px solid #F1F5F9;
  vertical-align: middle;
}
.expense-table tr:last-child td {
  border-bottom: none;
}
.expense-table tr.row-selected {
  background: #EFF6FF;
  border-left: 3px solid #2563EB;
}
.expense-table tr:hover {
  background: #F8FAFC;
}

/* ── Excel-like Filter ───────────────────────────────────── */
.excel-filter {
  width: 100%;
  box-sizing: border-box;
  font-size: 0.75rem;
  padding: 4px;
  margin-top: 6px;
  border: 1px solid #E2E8F0;
  border-radius: 4px;
  font-weight: normal;
  outline: none;
}
.excel-filter:focus {
  border-color: #3B5BDB;
  box-shadow: 0 0 0 2px rgba(59,91,219,0.1);
}

/* ── Employee chip ───────────────────────────────────────── */
.emp-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.emp-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #E0E7FF;
  color: #3B5BDB !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.7rem;
  flex-shrink: 0;
}
.emp-name {
  font-weight: 600;
  color: #1E293B;
  font-size: 0.88rem;
  line-height: 1.2;
}
.emp-role {
  color: #94A3B8;
  font-size: 0.75rem;
}

/* ── Status badges ───────────────────────────────────────── */
.status-badge {
  display: inline-block;
  padding: 0.25rem 0.7rem;
  border-radius: 5px;
  font-size: 0.78rem;
  font-weight: 600;
}
.status-awaiting {
  background: #FEF3C7;
  color: #D97706;
  border: 1px solid #FDE68A;
}
.status-approved {
  background: #D1FAE5;
  color: #059669;
  border: 1px solid #A7F3D0;
}
.status-auto-approved {
  background: #E0E7FF;
  color: #3B5BDB;
  border: 1px solid #C7D2FE;
}
.status-rejected {
  background: #FEE2E2;
  color: #DC2626;
  border: 1px solid #FECACA;
}

/* ── Expense detail card (expanded row) ──────────────────── */
.detail-card {
  background: #FFFFFF;
  border: 2px solid #2563EB;
  border-radius: 10px;
  padding: 1.5rem;
  margin: 0.75rem 0;
  box-shadow: 0 4px 12px rgba(37,99,235,0.08);
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #E2E8F0;
}
.detail-header h3 {
  font-size: 1.05rem;
  font-weight: 700;
  color: #1E293B;
  margin: 0;
}
.detail-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.detail-grid {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 0.45rem 1rem;
  margin-bottom: 1rem;
}
.detail-label {
  font-weight: 600;
  color: #475569;
  font-size: 0.88rem;
}
.detail-value {
  color: #1E293B;
  font-size: 0.88rem;
}

/* ── Receipt preview box ─────────────────────────────────── */
.receipt-preview-box {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.5rem;
}
.receipt-preview-box .receipt-info {
  font-size: 0.85rem;
  color: #475569;
}
.receipt-preview-box .receipt-title {
  font-weight: 600;
  color: #1E293B;
}
.receipt-preview-box .receipt-meta {
  color: #94A3B8;
  font-size: 0.78rem;
}

/* ── Approve / Reject buttons ────────────────────────────── */
.btn-approve {
  background: #059669 !important;
  color: #FFF !important;
  border: none !important;
  padding: 0.5rem 1.25rem !important;
  border-radius: 6px !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  cursor: pointer;
}
.btn-approve:hover {
  background: #047857 !important;
}
.btn-reject {
  background: #DC2626 !important;
  color: #FFF !important;
  border: none !important;
  padding: 0.5rem 1.25rem !important;
  border-radius: 6px !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  cursor: pointer;
}
.btn-reject:hover {
  background: #B91C1C !important;
}

/* ── Submit form card ────────────────────────────────────── */
.form-card {
  background: #FFFFFF;
  border-radius: 10px;
  padding: 1.5rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 1rem;
}

/* ── History rows ────────────────────────────────────────── */
.history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #F1F5F9;
}
.history-row:last-child {
  border-bottom: none;
}
.hr-left {
  display: flex;
  flex-direction: column;
}
.hr-cat {
  color: #94A3B8;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.hr-desc {
  color: #1E293B;
  font-size: 0.9rem;
  margin-top: 0.1rem;
}
.hr-date {
  color: #94A3B8;
  font-size: 0.78rem;
}
.hr-amount {
  font-weight: 700;
  color: #1E293B;
  font-size: 1rem;
  white-space: nowrap;
}

/* ── Hide default Streamlit stuff ────────────────────────── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stHeader"] {
  display: none !important;
}
/* Completely disable sidebar collapse/expand functionality */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {
  display: none !important;
}

/* Fix overlapping text in file uploader button */
[data-testid="stFileUploaderDropzone"] button {
  color: transparent !important;
  position: relative;
}
[data-testid="stFileUploaderDropzone"] button::after {
  content: "Browse files" !important;
  color: #334155 !important;
  position: absolute;
  left: 0;
  right: 0;
  text-align: center;
}

/* Fix expander arrow text bleed when material font fails */
.stExpander summary svg,
.stExpander summary .material-symbols-rounded,
.stExpander summary [data-testid="stExpanderToggleIcon"] {
  display: none !important;
}
.stExpander summary {
  color: transparent !important;
}
.stExpander summary p {
  color: #1E293B !important;
}
.stExpander summary p::before {
  content: "▼ ";
  color: #94A3B8;
  font-size: 0.8rem;
  margin-right: 8px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Session state defaults
# ──────────────────────────────────────────────────────────────
_defaults = {
  "session_id": None,
  "waiting_for_input": False,
  "interrupt_message": "",
  "final_output": None,
  "interrupt_id": None,
  "agent_messages": [],
  "logged_in": False,
  "email": "",
  "role": "",
  "submitted_receipt_image": None,
  "submitted_receipt_mime": "image/png",
  "active_nav": "pending",
  # Track which ADK session IDs have already been saved to the DB so that
  # Streamlit reruns never trigger a second INSERT for the same workflow run.
  "saved_session_ids": set(),
}
for k, v in _defaults.items():
  if k not in st.session_state:
    st.session_state[k] = v


# Restore session from query parameters
# Bug #8: validate role against known-good set to prevent URL-based privilege escalation
if not st.session_state.logged_in:
    if "email" in st.query_params and "role" in st.query_params:
        requested_role = st.query_params["role"]
        requested_email = st.query_params["email"]
        if requested_role in _VALID_ROLES and "@" in requested_email:
            st.session_state.logged_in = True
            st.session_state.email = requested_email
            st.session_state.role = requested_role
        else:
            # Tampered params — clear them and force re-login
            st.query_params.clear()

if st.session_state.session_id is None:
  # Bug #5: standardize on async session creation everywhere
  session = asyncio.run(agent_runtime.async_create_session(user_id="streamlit_user"))
  st.session_state.session_id = session["id"]


# ──────────────────────────────────────────────────────────────
# DB Helpers
# ──────────────────────────────────────────────────────────────
def _db_path():
  dir_path = os.path.dirname(os.path.abspath(__file__))
  return os.path.join(os.path.dirname(dir_path), "expenses.db")


def get_employee_expenses(email: str) -> list[dict]:
  """Return all past expenses for the given submitter email."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.row_factory = sqlite3.Row
      cur = conn.cursor()
      cur.execute(
        "SELECT id, amount, submitter, category, description, date, status FROM expenses WHERE submitter = ? ORDER BY id DESC",
        (email,),
      )
      return [dict(r) for r in cur.fetchall()]
  except Exception:
    return []


def get_all_expenses() -> list[dict]:
  """Return all expenses (for admin view)."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.row_factory = sqlite3.Row
      cur = conn.cursor()
      cur.execute(
        "SELECT id, amount, submitter, category, description, date, status FROM expenses ORDER BY id DESC"
      )
      return [dict(r) for r in cur.fetchall()]
  except Exception:
    return []


def save_expense(expense: dict, status: str):
  """Save a newly approved or rejected expense to the database.
  
  Includes a DB-level duplicate guard: if a row with the same amount,
  submitter, date, and description already exists, the insert is skipped.
  Uses a context manager to prevent connection leaks (Bug #4).
  """
  try:
    with sqlite3.connect(_db_path()) as conn:
      cur = conn.cursor()
      # Bug #12: align duplicate guard fields with agent.py check_duplicate
      # Uses (amount, submitter, date, description) — same four-field key.
      cur.execute(
        "SELECT COUNT(*) FROM expenses WHERE amount = ? AND submitter = ? AND date = ? AND description = ?",
        (
          expense.get("amount", 0.0),
          expense.get("submitter", ""),
          expense.get("date", ""),
          expense.get("description", ""),
        )
      )
      if cur.fetchone()[0] > 0:
        return  # Already saved — skip duplicate insert
      cur.execute(
        "INSERT INTO expenses (amount, submitter, category, description, date, status) VALUES (?, ?, ?, ?, ?, ?)",
        (
          expense.get("amount", 0.0),
          expense.get("submitter", ""),
          expense.get("category", ""),
          expense.get("description", ""),
          expense.get("date", ""),
          status
        )
      )
      conn.commit()
  except Exception as e:
    print(f"Error saving expense: {e}")


def save_pending_approval(session_id: str, interrupt_id: str, message: str, submitter_email: str, receipt_bytes: str = "", raw_json: str = ""):
  """Save a pending approval record. Uses context manager to prevent connection leaks (Bug #4)."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.execute(
        "INSERT INTO pending_approvals (session_id, interrupt_id, message, receipt_bytes, submitter_email, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, interrupt_id, message, receipt_bytes, submitter_email, raw_json)
      )
      conn.commit()
  except Exception as e:
    print(f"Error saving pending approval: {e}")

def get_all_pending_approvals() -> list[dict]:
  """Return all pending approvals ordered by id. Uses context manager (Bug #4)."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.row_factory = sqlite3.Row
      cur = conn.cursor()
      cur.execute("SELECT * FROM pending_approvals ORDER BY id ASC")
      return [dict(r) for r in cur.fetchall()]
  except Exception:
    return []

def delete_pending_approval(record_id: int):
  """Delete a pending approval by database row ID. Uses context manager."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.execute("DELETE FROM pending_approvals WHERE id = ?", (record_id,))
      conn.commit()
  except Exception:
    pass


def _esc(value: str) -> str:
  """HTML-escape a string for safe interpolation into unsafe_allow_html markup."""
  return html_escape(str(value)) if value else "—"


def _initials(email: str) -> str:
  """Generate initials from an email."""
  name_part = email.split("@")[0]
  parts = name_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
  if len(parts) >= 2:
    return (parts[0][0] + parts[1][0]).upper()
  return name_part[:2].upper()


def _display_name(email: str) -> str:
  """Generate a display name from an email."""
  name_part = email.split("@")[0]
  parts = name_part.replace(".", " ").replace("_", " ").replace("-", " ").split()
  return " ".join(p.capitalize() for p in parts)


# ──────────────────────────────────────────────────────────────
# Agent helpers
# ──────────────────────────────────────────────────────────────
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
            save_pending_approval(
              session_to_track,
              fn_call.get("id"),
              st.session_state.interrupt_message,
              st.session_state.email,
              receipt_bytes,
              raw_json
            )

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
        decision = final_output.get("decision") or "Approved"
        save_expense(final_output["expense"], decision)
        if session_to_track:
          st.session_state.saved_session_ids.add(session_to_track)


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


# ╔═══════════════════════════════════════════════════════════╗
# ║ LOGIN SCREEN                       ║
# ╚═══════════════════════════════════════════════════════════╝
if not st.session_state.logged_in:
  col_l, col_c, col_r = st.columns([1, 1.5, 1])
  with col_c:
    st.markdown(
      """<div style="text-align:center; margin-top:3rem;">
        <div style="display:inline-flex;align-items:center;justify-content:center;
          width:56px;height:56px;background:linear-gradient(135deg,#2563EB,#7C3AED);
          border-radius:14px;margin-bottom:1rem;">
          <span style="font-size:1.5rem;color:#FFF;font-weight:800;font-family:Inter,sans-serif;">A</span>
        </div>
        <h2 style="color:#1E293B;margin-bottom:0.25rem;">Acme Corp</h2>
        <p style="color:#94A3B8;font-size:0.92rem;margin-bottom:2rem;">Sign in to the Expense Approval Portal</p>
      </div>""",
      unsafe_allow_html=True,
    )

    with st.container():
      if "selected_login_role" not in st.session_state:
        st.session_state.selected_login_role = None

      if st.session_state.selected_login_role is None:
        st.markdown("<h3 style='text-align: center; color: #334155; margin-bottom: 2rem; font-size: 1.1rem;'>Select your role to continue</h3>", unsafe_allow_html=True)
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
          if st.button(" Login as Employee", use_container_width=True):
            st.session_state.selected_login_role = "Employee"
            st.rerun()
        with col_btn2:
          if st.button(" Login as Admin", use_container_width=True):
            st.session_state.selected_login_role = "Admin"
            st.rerun()
      
      elif st.session_state.selected_login_role == "Employee":
        employee_names = [f"Employee {i}" for i in [1, 2, 3, 4, 5, 7]]
        selected_employee = st.selectbox("Select Employee", options=employee_names)
        password = st.text_input("Password", type="password", value="password")
        
        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
          if st.button(" Back", use_container_width=True):
            st.session_state.selected_login_role = None
            st.rerun()
        with col_b2:
          if st.button("Sign In", type="primary", use_container_width=True):
            st.session_state.logged_in = True
            # Map Employee 1 to employee1@acmecorp.com
            emp_num = selected_employee.split(" ")[1]
            st.session_state.email = f"employee{emp_num}@acmecorp.com"
            st.session_state.role = "Employee"
            st.query_params["email"] = st.session_state.email
            st.query_params["role"] = st.session_state.role
            st.rerun()
            
      elif st.session_state.selected_login_role == "Admin":
        email = st.text_input("Corporate Email", value="admin@acmecorp.com")
        password = st.text_input("Password", type="password", value="password")

        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
          if st.button(" Back", use_container_width=True):
            st.session_state.selected_login_role = None
            st.rerun()
        with col_b2:
          if st.button("Sign In", type="primary", use_container_width=True):
            if email.strip():
              st.session_state.logged_in = True
              st.session_state.email = email
              st.session_state.role = "Admin"
              st.query_params["email"] = email
              st.query_params["role"] = "Admin"
              st.rerun()
            else:
              st.error("Please enter a valid email.")


  st.stop()


# ──────────────────────────────────────────────────────────────
# SIDEBAR — Dark navy navigation
# ──────────────────────────────────────────────────────────────
with st.sidebar:
  # Logo
  st.markdown(
    """<div class="sidebar-logo">
      <div class="sidebar-logo-icon"><span style="font-weight:800;font-family:Inter,sans-serif;">A</span></div>
      <div>
        <div class="sidebar-logo-text">Acme Corp</div>
        <div class="sidebar-logo-sub">Expenses</div>
      </div>
    </div>""",
    unsafe_allow_html=True,
  )
  st.markdown("---")

  # Navigation
  if st.session_state.role == "Admin":
    # Bug #10: show real count from DB, not a hardcoded max-1 boolean flag
    pending_count = len(get_all_pending_approvals())
    badge = f'<span class="nav-badge">{pending_count}</span>' if pending_count else ""
    st.markdown(
      f'<div class="nav-active">Pending Approvals {badge}</div>',
      unsafe_allow_html=True,
    )
    st.markdown('<div class="nav-item">All Expenses</div>', unsafe_allow_html=True)
  else:
    st.markdown('<div class="nav-active">Submit Expense</div>', unsafe_allow_html=True)

  st.markdown("---")

  if st.button(" Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.email = ""
    st.session_state.role = ""
    st.query_params.clear()
    st.rerun()


# ──────────────────────────────────────────────────────────────
# TOP HEADER BAR
# ──────────────────────────────────────────────────────────────
initials = _initials(st.session_state.email)
display = _display_name(st.session_state.email)
role_label = st.session_state.role

st.markdown(
  f"""<div class="top-header">
    <h1>Expense Approval Portal</h1>
    <div class="top-header-right">
      <span>Welcome, {_esc(display)} ({_esc(role_label)})</span>
      <span class="user-avatar">{_esc(initials)}</span>
    </div>
  </div>""",
  unsafe_allow_html=True,
)


# ╔═══════════════════════════════════════════════════════════╗
# ║ EMPLOYEE WORKSPACE                    ║
# ╚═══════════════════════════════════════════════════════════╝
if st.session_state.role == "Employee":
  

  # ── Submit New Expense ───────────────────────────────────
  st.markdown(
    '<div class="section-title">Submit New Expense</div>',
    unsafe_allow_html=True,
  )

  tab_receipt, tab_form = st.tabs(["Upload Receipt", "Fill Expense Form"])

  with tab_receipt:
    uploaded_file = st.file_uploader(
      "Upload Receipt Image",
      type=["png", "jpg", "jpeg"],
      label_visibility="collapsed",
    )

    has_demo = "demo_receipt_bytes" in st.session_state and st.session_state.demo_receipt_bytes

    col_d1, col_d2 = st.columns([1.5, 3])
    with col_d1:
      if not has_demo:
        if st.button("Load Demo Receipt"):
          try:
            import random
            receipts = ["dummy_receipt.png", "dummy_receipt_2.png", "dummy_receipt_3.png"]
            chosen_receipt = random.choice(receipts)
            demo_path = os.path.join(
              os.path.dirname(os.path.dirname(__file__)),
              chosen_receipt,
            )
            with open(demo_path, "rb") as f:
              st.session_state.demo_receipt_bytes = f.read()
            st.rerun()
          except Exception as e:
            st.error(f"Could not load demo receipt: {e}")
      else:
        if st.button("Remove Demo Receipt"):
          st.session_state.demo_receipt_bytes = None
          st.rerun()

    image_to_submit = None
    mime_type = "image/png"

    if uploaded_file is not None:
      image_to_submit = uploaded_file.getvalue()
      mime_type = uploaded_file.type
      st.image(image_to_submit, caption="Uploaded Receipt", width=500)
    elif (
      "demo_receipt_bytes" in st.session_state
      and st.session_state.demo_receipt_bytes
    ):
      image_to_submit = st.session_state.demo_receipt_bytes
      st.image(image_to_submit, caption="Demo Receipt", width=500)

    if st.button(
      "Submit Receipt",
      type="primary",
      use_container_width=True,
      key="submit_receipt",
    ):
      if image_to_submit is not None:
        try:
          # Bug #5: use async session creation consistently
          session = asyncio.run(agent_runtime.async_create_session(user_id="streamlit_user"))
          st.session_state.session_id = session["id"]
          st.session_state.waiting_for_input = False
          st.session_state.final_output = None
          st.session_state.agent_messages = []

          base64_image = base64.b64encode(image_to_submit).decode("utf-8")
          st.session_state.submitted_receipt_image = base64_image
          st.session_state.submitted_receipt_mime = mime_type

          payload_dict = {
            "image_data": base64_image,
            "mime_type": mime_type,
            "submitter": st.session_state.email,
          }
          with st.spinner("Processing receipt…"):
            message_dict = {
              "parts": [{"text": json.dumps(payload_dict)}],
              "role": "user",
            }
            events = run_agent(message_dict)
            process_events(events)
            st.rerun()
        except Exception as e:
          st.error(f"An error occurred: {e}")
      else:
        # Bug #2: error is now inside the button block — only shown when the
        # button is pressed without an image, never on passive page reruns.
        st.error("Please upload an image or load the demo receipt first.")


  with tab_form:
    with st.form("expense_form", clear_on_submit=False):
      col_a, col_b = st.columns(2)
      with col_a:
        exp_amount = st.number_input(
          "Amount ($)",
          min_value=0.01,
          step=0.01,
          value=50.00,
          format="%.2f",
        )
      with col_b:
        exp_category = st.selectbox(
          "Category",
          [
            "Meals",
            "Travel",
            "Equipment",
            "Office Supplies",
            "Software",
            "Other",
          ],
        )

      col_c, col_d = st.columns(2)
      with col_c:
        exp_submitter = st.text_input(
          "Submitter Email", value=st.session_state.email
        )
      with col_d:
        exp_date = st.date_input("Expense Date", value=date.today())

      exp_description = st.text_area(
        "Purpose / Justification",
        placeholder="Describe the purpose of this expense…",
        height=100,
      )

      submitted = st.form_submit_button(
        "Submit Expense",
        type="primary",
        use_container_width=True,
      )

    if submitted:
      if not exp_description.strip():
        st.error("Please provide a description for the expense.")
      else:
        try:
          session = asyncio.run(agent_runtime.async_create_session(user_id="streamlit_user"))
          st.session_state.session_id = session["id"]
          st.session_state.waiting_for_input = False
          st.session_state.final_output = None
          st.session_state.agent_messages = []
          st.session_state.submitted_receipt_image = None

          data = {
            "amount": float(exp_amount),
            "submitter": exp_submitter,
            "category": exp_category,
            "description": exp_description,
            "date": str(exp_date),
          }
          st.session_state.raw_json = json.dumps(data, indent=2)
          
          with st.spinner("Processing expense…"):
            message_dict = {
              "parts": [{"text": json.dumps(data)}],
              "role": "user",
            }
            events = run_agent(message_dict)
            process_events(events)
            st.rerun()
        except Exception as e:
          st.error(f"An error occurred: {e}")

  # ── Pending / Progress / Final output ────────────────────
  my_pending = [r for r in get_all_pending_approvals() if r.get("submitter_email") == st.session_state.email]
  if my_pending:
    st.warning(f" You have {len(my_pending)} expense(s) submitted — pending Admin approval.")

  if st.session_state.agent_messages:
    with st.expander(" Submission Progress", expanded=True):
      for msg in st.session_state.agent_messages:
        st.markdown(msg)

  # ── My Expenses Table ────────────────────────────────────
  my_pending = [r for r in get_all_pending_approvals() if r.get("submitter_email") == st.session_state.email]
  pending_expenses = []
  for p in my_pending:
      try:
          exp_data = json.loads(p.get("raw_json", "{}"))
      except Exception:
          exp_data = {}
      details = parse_interrupt_details(p.get("message", ""))
      try:
          amt = float(details.get("amount", "0"))
      except Exception:
          amt = 0.0
      pending_expenses.append({
          "id": f"PENDING-{p.get('id', '')}",
          "date": exp_data.get("date", date.today().strftime('%d %b %Y')),
          "category": exp_data.get("category", "—"),
          "amount": amt,
          "description": details.get("description", "—"),
          "status": "Pending"
      })

  my_expenses = get_employee_expenses(st.session_state.email)
  all_my_expenses = pending_expenses + my_expenses

  if all_my_expenses:
    avail_categories = sorted(list(set(str(e.get("category", "")) for e in all_my_expenses if e.get("category"))))
    avail_statuses = sorted(list(set(str(e.get("status", "")) for e in all_my_expenses if e.get("status"))))
    
    def is_active(*keys):
      for k in keys:
        val = st.session_state.get(k)
        if val is not None and val != "" and val != [] and val != ():
          return True
      return False

    def plabel(name, *keys):
      return f"🟢 {name}" if is_active(*keys) else f"🔽 {name}"

    col_title, col_btn = st.columns([8, 2])
    with col_title:
      st.markdown(f'<div class="section-title" style="margin-top:2rem;">My Expenses</div>', unsafe_allow_html=True)
    with col_btn:
      st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
      if st.button("Clear Filters", key="emp_clear_btn", use_container_width=True):
        for k in ["emp_f_id", "emp_f_date", "emp_f_cat", "emp_f_min", "emp_f_max", "emp_f_desc", "emp_f_stat"]:
          if k in st.session_state:
            del st.session_state[k]
        st.rerun()
    
    # Excel-like Filter Popovers
    f_col1, f_col2, f_col3, f_col4, f_col5, f_col6 = st.columns([1,1,1,1,2,1])
    with f_col1:
      with st.popover(plabel("ID", "emp_f_id"), use_container_width=True):
        filter_id = st.text_input("Search ID", key="emp_f_id")
    with f_col2:
      with st.popover(plabel("Date", "emp_f_date"), use_container_width=True):
        filter_date = st.date_input("Search Date Range", value=[], key="emp_f_date")
    with f_col3:
      with st.popover(plabel("Category", "emp_f_cat"), use_container_width=True):
        filter_category = st.multiselect("Select Category", options=avail_categories, key="emp_f_cat")
    with f_col4:
      with st.popover(plabel("Amount", "emp_f_min", "emp_f_max"), use_container_width=True):
        filter_min_amt = st.number_input("Min $", min_value=0.0, step=1.0, value=None, key="emp_f_min")
        filter_max_amt = st.number_input("Max $", min_value=0.0, step=1.0, value=None, key="emp_f_max")
    with f_col5:
      with st.popover(plabel("Description", "emp_f_desc"), use_container_width=True):
        filter_desc = st.text_input("Search Description", key="emp_f_desc")
    with f_col6:
      with st.popover(plabel("Status", "emp_f_stat"), use_container_width=True):
        filter_status = st.multiselect("Select Status", options=avail_statuses, key="emp_f_stat")

    filtered_my_expenses = []
    for exp in all_my_expenses:
      exp_id_raw = exp.get('id', 0)
      exp_id = str(exp_id_raw) if str(exp_id_raw).startswith("PENDING") else f"EX{int(exp_id_raw):04d}"
      if filter_id and filter_id.lower() not in exp_id.lower(): continue
      if filter_date:
        import pandas as pd
        row_dt = pd.to_datetime(exp.get("date", ""), errors="coerce")
        if pd.notna(row_dt):
          row_d = row_dt.date()
          if len(filter_date) == 1 and row_d != filter_date[0]: continue
          elif len(filter_date) == 2 and not (filter_date[0] <= row_d <= filter_date[1]): continue
        else:
          continue
      if filter_category and exp.get("category") not in filter_category: continue
      if filter_status and exp.get("status") not in filter_status: continue
      amt = float(exp.get("amount", 0.0))
      if filter_min_amt is not None and amt < filter_min_amt: continue
      if filter_max_amt is not None and amt > filter_max_amt: continue
      if filter_desc and filter_desc.lower() not in str(exp.get("description", "")).lower(): continue
      filtered_my_expenses.append(exp)

    if filtered_my_expenses:
      rows_html = ""
      for exp in filtered_my_expenses:
        exp_id_raw = exp.get('id', 0)
        exp_id = str(exp_id_raw) if str(exp_id_raw).startswith("PENDING") else f"EX{int(exp_id_raw):04d}"
        status = exp.get("status", "Approved")
        status_cls = "status-approved" if status == "Approved" else ("status-auto-approved" if status == "Auto-Approved" else ("status-rejected" if status == "Rejected" else "status-awaiting"))
        rows_html += f"""<tr>
          <td><strong>{_esc(exp_id)}</strong></td>
          <td>{_esc(exp.get('date','—'))}</td>
          <td>{_esc(exp.get('category','—'))}</td>
          <td><strong>${exp.get('amount',0):.2f}</strong></td>
          <td>{_esc(exp.get('description','—')[:40])}</td>
          <td><span class="status-badge {status_cls}">{_esc(status)}</span></td>
        </tr>"""

      st.markdown(
        f"""<table class="expense-table" style="margin-top: 0.5rem;">
          <thead><tr>
            <th>Expense ID</th>
            <th>Date</th>
            <th>Category</th>
            <th>Amount</th>
            <th>Description</th>
            <th>Status</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>""",
        unsafe_allow_html=True,
      )
    else:
      st.info("No expenses match the selected filters.")


# ╔═══════════════════════════════════════════════════════════╗
# ║ ADMIN DASHBOARD                     ║
# ╚═══════════════════════════════════════════════════════════╝
elif st.session_state.role == "Admin":
  

  # ── All Expenses Table ───────────────────────────────────
  all_expenses = get_all_expenses()
  @st.fragment(run_every="5s")
  def render_pending_approvals():
    pending_records = get_all_pending_approvals()
    pending_count = len(pending_records)
    total_label = f"Pending Approval Requests ({pending_count})" if pending_count else "All Expenses"
  
    st.markdown(
      f'<div class="section-title">{total_label}</div>',
      unsafe_allow_html=True,
    )
  
    # ── Pending expense detail card ──────────────────────────
    if pending_records:
      for record in pending_records:
        interrupt_message = record.get("message", "")
        session_id = record.get("session_id", "")
        interrupt_id = record.get("interrupt_id", "")
        submitter_email = record.get("submitter_email", "")
        receipt_bytes = record.get("receipt_bytes", "")
        db_id = record.get("id", "")
  
        details = parse_interrupt_details(interrupt_message)
        submitter_str = details.get("submitter", submitter_email)
        amount_str = details.get("amount", "0.00")
        description_str = details.get("description", "—")
        risk_str = details.get("risk", "N/A")
        has_security = details.get("security_flag", False)
        has_injection = details.get("injection", False)
        pii_info = details.get("pii", "")
        
        try:
          raw_json_str = record.get("raw_json", "{}")
          exp_data = json.loads(raw_json_str)
        except Exception:
          exp_data = {}
          
        exp_date = exp_data.get("date", date.today().strftime('%d %b %Y'))
        exp_category = exp_data.get("category", "—")
  
        sub_initials = _initials(submitter_str)
        sub_display = _display_name(submitter_str)
        # Bug #15: use first 8 chars of session_id instead of hash() % 9999
        # hash() has only ~9999 buckets so collisions are very likely with many sessions.
        exp_id = "EX" + session_id[:8].upper() if session_id else "EX0000"
  
        # Table row for the pending item
        st.markdown(
          f"""<table class="expense-table">
            <thead><tr>
              <th>Expense ID</th><th>Employee</th><th>Date</th>
              <th>Amount</th><th>Category</th><th>Status</th>
            </tr></thead>
            <tbody>
            <tr class="row-selected">
              <td><strong>{_esc(exp_id)}</strong></td>
              <td>
                <div class="emp-chip">
                  <span class="emp-avatar">{_esc(sub_initials)}</span>
                  <div>
                    <div class="emp-name">{_esc(sub_display)}</div>
                    <div class="emp-role">Employee</div>
                  </div>
                </div>
              </td>
              <td>{_esc(exp_date)}</td>
              <td><strong>${_esc(amount_str)}</strong></td>
              <td>{_esc(exp_category)}</td>
              <td><span class="status-badge status-awaiting">Awaiting Approval</span></td>
            </tr>
            </tbody>
          </table>""",
          unsafe_allow_html=True,
        )
  
        # Security badges HTML
        flags_html = ""
        if has_security:
          flags_html += '<span class="status-badge status-rejected" style="margin-right:0.4rem;">⚠️ Security Event</span>'
        if has_injection:
          flags_html += '<span class="status-badge status-rejected" style="margin-right:0.4rem;">🚨 Prompt Injection</span>'
        if pii_info:
          flags_html += f'<span class="status-badge status-awaiting" style="margin-right:0.4rem;">🔒 PII: {_esc(pii_info)}</span>'
  
        # Detail card
        st.markdown(
          f"""<div class="detail-card">
            <div class="detail-header">
              <h3>Expense Details: {_esc(exp_id)} ({_esc(sub_display)})</h3>
            </div>
            {f'<div style="margin-bottom:0.75rem;">{flags_html}</div>' if flags_html else ''}
            <div class="detail-grid">
              <div class="detail-label">Date:</div>
              <div class="detail-value">{_esc(exp_date)}</div>
              <div class="detail-label">Amount:</div>
              <div class="detail-value"><strong>${_esc(amount_str)}</strong></div>
              <div class="detail-label">Category:</div>
              <div class="detail-value">{_esc(exp_category)}</div>
              <div class="detail-label">Purpose:</div>
              <div class="detail-value">{_esc(description_str)}</div>
            </div>
          </div>""",
          unsafe_allow_html=True,
        )
  
        raw_json_str = record.get("raw_json", "{}")
        with st.expander(" Raw JSON Input", expanded=False):
          st.code(raw_json_str, language="json")
          
        with st.expander(" AI Insight Summary", expanded=True):
          st.markdown(f"**Risk Assessment:** {risk_str}")
          if pii_info:
            st.markdown(f"**PII Found:** {pii_info}")
          if has_security or has_injection:
            st.markdown("**Security:** Immediate attention required.")
  
        # ── Receipt image preview ────────────────────────────
        if receipt_bytes:
          with st.expander(" Invoice Attachment — View Receipt", expanded=True):
            try:
              img_bytes = base64.b64decode(receipt_bytes)
              st.image(
                img_bytes,
                caption="Submitted Receipt / Invoice",
                width=500,
              )
            except Exception:
              st.info("Unable to render receipt image.")
  
        # ── Approve / Reject ─────────────────────────────────
        st.markdown("---")
        rejection_reason = st.text_input(
          "Add Comment (required for rejection):",
          placeholder="e.g., Missing receipt, Out of budget…",
          key=f"rej_reason_{db_id}"
        )
  
        col1, col2 = st.columns(2)
        with col1:
          if st.button("Reject", use_container_width=True, key=f"btn_reject_{db_id}"):
            if not rejection_reason.strip():
              st.error("A rejection reason is mandatory.")
            else:
              with st.spinner("Resuming workflow to reject..."):
                payload = {
                  "role": "tool",
                  "parts": [{
                    "function_response": {
                      "id": interrupt_id,
                      "name": "adk_request_input",
                      "response": {"output": f"Reject: {rejection_reason}"}
                    }
                  }]
                }
                events = run_agent(payload, specific_session_id=session_id)
                process_events(events, run_session_id=session_id, submitter_email=submitter_email)
                delete_pending_approval(db_id)
                st.rerun()
        with col2:
          if st.button("Approve", type="primary", use_container_width=True, key=f"btn_approve_{db_id}"):
            with st.spinner("Resuming workflow to approve..."):
              payload = {
                "role": "tool",
                "parts": [{
                  "function_response": {
                    "id": interrupt_id,
                    "name": "adk_request_input",
                    "response": {"output": "Approve"}
                  }
                }]
              }
              events = run_agent(payload, specific_session_id=session_id)
              process_events(events, run_session_id=session_id, submitter_email=submitter_email)
              delete_pending_approval(db_id)
              st.rerun()
  
    else:
      # ── No pending — show last result + all expenses ─────
      if st.session_state.final_output:
        out = st.session_state.final_output
        if isinstance(out, dict):
          exp = out.get("expense", {})
          decision = out.get("decision", "N/A")
          reason = out.get("reason", "")
          status_cls = (
            "status-approved" if decision == "Approved" else ("status-auto-approved" if decision == "Auto-Approved" else "status-rejected")
          )
          st.markdown(
            f"""<div class="detail-card">
              <div class="detail-header">
                <h3>Last Reviewed Expense</h3>
                <span class="status-badge {status_cls}">{_esc(decision)}</span>
              </div>
              <div class="detail-grid">
                <div class="detail-label">Amount:</div>
                <div class="detail-value"><strong>${exp.get('amount',0):.2f}</strong></div>
                <div class="detail-label">Submitter:</div>
                <div class="detail-value">{_esc(exp.get('submitter','—'))}</div>
                <div class="detail-label">Category:</div>
                <div class="detail-value">{_esc(exp.get('category','—'))}</div>
                <div class="detail-label">Purpose:</div>
                <div class="detail-value">{_esc(exp.get('description','—'))}</div>
                <div class="detail-label">Reason:</div>
                <div class="detail-value">{_esc(reason)}</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
          )
          st.markdown("---")
      else:
        st.info("No pending expenses require review at this time.")

  render_pending_approvals()

  # ── All expenses table (always visible for admin) ────────
  if all_expenses:
    avail_categories = sorted(list(set(str(e.get("category", "")) for e in all_expenses if e.get("category"))))
    avail_statuses = sorted(list(set(str(e.get("status", "")) for e in all_expenses if e.get("status"))))
    
    def is_active(*keys):
      for k in keys:
        val = st.session_state.get(k)
        if val is not None and val != "" and val != [] and val != ():
          return True
      return False

    def plabel(name, *keys):
      return f"🟢 {name}" if is_active(*keys) else f"🔽 {name}"

    col_title, col_btn = st.columns([8, 2])
    with col_title:
      st.markdown(f'<div class="section-title" style="margin-top:1rem;">All Expenses</div>', unsafe_allow_html=True)
    with col_btn:
      st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
      if st.button("Clear Filters", key="adm_clear_btn", use_container_width=True):
        for k in ["adm_f_id", "adm_f_emp", "adm_f_date", "adm_f_cat", "adm_f_min", "adm_f_max", "adm_f_desc", "adm_f_stat"]:
          if k in st.session_state:
            del st.session_state[k]
        st.rerun()
    
    # Excel-like Filter Popovers
    f_col1, f_col2, f_col3, f_col4, f_col5, f_col6, f_col7 = st.columns([1,1,1,1,1,2,1])
    with f_col1:
      with st.popover(plabel("ID", "adm_f_id"), use_container_width=True):
        filter_id = st.text_input("Search ID", key="adm_f_id")
    with f_col2:
      with st.popover(plabel("Emp", "adm_f_emp"), use_container_width=True):
        filter_emp = st.text_input("Search Employee", key="adm_f_emp")
    with f_col3:
      with st.popover(plabel("Date", "adm_f_date"), use_container_width=True):
        filter_date = st.date_input("Search Date Range", value=[], key="adm_f_date")
    with f_col4:
      with st.popover(plabel("Category", "adm_f_cat"), use_container_width=True):
        filter_category = st.multiselect("Select Category", options=avail_categories, key="adm_f_cat")
    with f_col5:
      with st.popover(plabel("Amount", "adm_f_min", "adm_f_max"), use_container_width=True):
        filter_min_amt = st.number_input("Min $", min_value=0.0, step=1.0, value=None, key="adm_f_min")
        filter_max_amt = st.number_input("Max $", min_value=0.0, step=1.0, value=None, key="adm_f_max")
    with f_col6:
      with st.popover(plabel("Description", "adm_f_desc"), use_container_width=True):
        filter_desc = st.text_input("Search Description", key="adm_f_desc")
    with f_col7:
      with st.popover(plabel("Status", "adm_f_stat"), use_container_width=True):
        filter_status = st.multiselect("Select Status", options=avail_statuses, key="adm_f_stat")

    filtered_all_expenses = []
    for exp in all_expenses:
      exp_id = f"EX{exp.get('id', 0):04d}"
      emp_name = _display_name(exp.get("submitter", ""))
      emp_email = exp.get("submitter", "")
      
      if filter_id and filter_id.lower() not in exp_id.lower(): continue
      if filter_emp and (filter_emp.lower() not in emp_name.lower() and filter_emp.lower() not in emp_email.lower()): continue
      if filter_date:
        import pandas as pd
        row_dt = pd.to_datetime(exp.get("date", ""), errors="coerce")
        if pd.notna(row_dt):
          row_d = row_dt.date()
          if len(filter_date) == 1 and row_d != filter_date[0]: continue
          elif len(filter_date) == 2 and not (filter_date[0] <= row_d <= filter_date[1]): continue
        else:
          continue
      if filter_category and exp.get("category") not in filter_category: continue
      if filter_status and exp.get("status") not in filter_status: continue
      amt = float(exp.get("amount", 0.0))
      if filter_min_amt is not None and amt < filter_min_amt: continue
      if filter_max_amt is not None and amt > filter_max_amt: continue
      if filter_desc and filter_desc.lower() not in str(exp.get("description", "")).lower(): continue
      filtered_all_expenses.append(exp)

    if filtered_all_expenses:
      rows_html = ""
      for exp in filtered_all_expenses:
        exp_id = f"EX{exp.get('id', 0):04d}"
        emp_init = _initials(exp.get("submitter", ""))
        emp_name = _display_name(exp.get("submitter", ""))
        status = exp.get("status", "Approved")
        status_cls = "status-approved" if status == "Approved" else ("status-auto-approved" if status == "Auto-Approved" else ("status-rejected" if status == "Rejected" else "status-awaiting"))
        rows_html += f"""<tr>
          <td><strong>{_esc(exp_id)}</strong></td>
          <td>
            <div class="emp-chip">
              <span class="emp-avatar">{_esc(emp_init)}</span>
              <div>
                <div class="emp-name">{_esc(emp_name)}</div>
              </div>
            </div>
          </td>
          <td>{_esc(exp.get('date','—'))}</td>
          <td>{_esc(exp.get('category','—'))}</td>
          <td><strong>${exp.get('amount',0):.2f}</strong></td>
          <td>{_esc(exp.get('description','—')[:40])}</td>
          <td><span class="status-badge {status_cls}">{_esc(status)}</span></td>
        </tr>"""

      st.markdown(
        f"""<table class="expense-table" style="margin-top: 0.5rem;">
          <thead><tr>
            <th>Expense ID</th>
            <th>Employee</th>
            <th>Date</th>
            <th>Category</th>
            <th>Amount</th>
            <th>Description</th>
            <th>Status</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>""",
        unsafe_allow_html=True,
      )
