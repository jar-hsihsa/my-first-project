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

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception:
        return ""

logo_base64 = get_base64_image(LOGO_PATH)
logo_img_src = f"data:image/png;base64,{logo_base64}" if logo_base64 else ""

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

[data-testid="stAppViewContainer"] {
  background: linear-gradient(-45deg, #F0F9FF, #E0E7FF, #F3E8FF, #FDF4FF);
  background-size: 400% 400%;
  animation: loginBackground 15s ease infinite;
}

@keyframes loginBackground {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
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
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 1.75rem 1rem 1.25rem 1rem;
}
.sidebar-logo-img {
  height: 70px;
  max-width: 100%;
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.sidebar-logo-sub {
  font-size: 0.85rem;
  color: #94A3B8 !important;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-top: 0.35rem;
  text-align: center;
  width: 100%;
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

/* Ensure file uploader button icon is cleanly hidden if necessary, relying on native text */
[data-testid="stFileUploaderDropzone"] button svg {
  display: none !important;
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

.conversion-badge {
  color: #2563EB;
  background-color: rgba(37,99,235,0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.82rem;
  border: 1px solid rgba(37,99,235,0.15);
  display: inline-block;
  margin-top: 4px;
  font-weight: 600;
}
.conversion-warning-badge {
  color: #DC2626;
  background-color: rgba(220,38,38,0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.82rem;
  border: 1px solid rgba(220,38,38,0.15);
  display: inline-block;
  margin-top: 4px;
  font-weight: 600;
}

/* ── Dark Mode Overrides ─────────────────────────────────── */
body[data-theme="dark"] .conversion-badge {
  color: #60A5FA !important;
  background-color: rgba(96,165,250,0.1) !important;
  border-color: rgba(96,165,250,0.2) !important;
}
body[data-theme="dark"] .conversion-warning-badge {
  color: #F87171 !important;
  background-color: rgba(248,113,113,0.1) !important;
  border-color: rgba(248,113,113,0.2) !important;
}
body[data-theme="dark"] [data-testid="stAppViewContainer"] {
  background: linear-gradient(-45deg, #0f172a, #1e293b, #0f172a, #020617) !important;
}
body[data-theme="dark"] .stMarkdown, body[data-theme="dark"] .stText, body[data-theme="dark"] p, body[data-theme="dark"] h1, body[data-theme="dark"] h2, body[data-theme="dark"] h3 {
  color: #f8fafc !important;
}
body[data-theme="dark"] .expense-table, body[data-theme="dark"] .detail-card, body[data-theme="dark"] .form-card, body[data-theme="dark"] .receipt-preview-box {
  background: #1e293b !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] .expense-table th {
  background: #0f172a !important;
  color: #f8fafc !important;
  border-bottom-color: #334155 !important;
}
body[data-theme="dark"] .expense-table td {
  color: #e2e8f0 !important;
  border-bottom-color: #334155 !important;
}
body[data-theme="dark"] .expense-table tr:hover {
  background: #334155 !important;
}
body[data-theme="dark"] .expense-table tr.row-selected {
  background: #1e3a8a !important;
  border-left: 3px solid #60a5fa !important;
}
body[data-theme="dark"] .detail-header h3, body[data-theme="dark"] .detail-value, body[data-theme="dark"] .emp-name {
  color: #f8fafc !important;
}
body[data-theme="dark"] .detail-label, body[data-theme="dark"] .emp-role, body[data-theme="dark"] .receipt-meta {
  color: #94a3b8 !important;
}
body[data-theme="dark"] .excel-filter {
  background: #0f172a !important;
  color: #f8fafc !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] .top-header h1 {
  color: #f8fafc !important;
}
body[data-theme="dark"] .top-header-right {
  color: #cbd5e1 !important;
}
body[data-theme="dark"] .top-header {
  border-bottom-color: #334155 !important;
}
body[data-theme="dark"] .section-title {
  color: #f8fafc !important;
}
body[data-theme="dark"] .emp-avatar {
  background: #1e3a8a !important;
  color: #93c5fd !important;
}
body[data-theme="dark"] .receipt-title {
  color: #f8fafc !important;
}
body[data-theme="dark"] .receipt-info {
  color: #cbd5e1 !important;
}
body[data-theme="dark"] .status-awaiting {
  background: rgba(217, 119, 6, 0.2) !important;
  color: #fcd34d !important;
  border-color: rgba(217, 119, 6, 0.5) !important;
}
body[data-theme="dark"] .status-approved {
  background: rgba(5, 150, 105, 0.2) !important;
  color: #6ee7b7 !important;
  border-color: rgba(5, 150, 105, 0.5) !important;
}
body[data-theme="dark"] .status-auto-approved {
  background: rgba(59, 91, 219, 0.2) !important;
  color: #93c5fd !important;
  border-color: rgba(59, 91, 219, 0.5) !important;
}
body[data-theme="dark"] .status-rejected {
  background: rgba(220, 38, 38, 0.2) !important;
  color: #fca5a5 !important;
  border-color: rgba(220, 38, 38, 0.5) !important;
}
body[data-theme="dark"] .history-row {
  border-bottom-color: #334155 !important;
}
body[data-theme="dark"] .hr-desc, body[data-theme="dark"] .hr-amount {
  color: #f8fafc !important;
}
body[data-theme="dark"] .hr-cat, body[data-theme="dark"] .hr-date {
  color: #94a3b8 !important;
}

/* Dark Mode Form Inputs and Buttons */
body[data-theme="dark"] .stButton > button,
body[data-theme="dark"] .stFormSubmitButton > button,
body[data-theme="dark"] .stDownloadButton > button {
  background-color: #1e293b !important;
  color: #f8fafc !important;
  border-color: #475569 !important;
}
body[data-theme="dark"] .stButton > button:hover,
body[data-theme="dark"] .stFormSubmitButton > button:hover,
body[data-theme="dark"] .stDownloadButton > button:hover {
  background-color: #334155 !important;
  border-color: #94a3b8 !important;
  color: #ffffff !important;
}
/* Ensure primary buttons retain their primary color but with readable text */
body[data-theme="dark"] button[data-testid="baseButton-primary"] {
  background-color: #2563eb !important;
  color: #ffffff !important;
  border-color: #2563eb !important;
}
body[data-theme="dark"] button[data-testid="baseButton-primary"]:hover {
  background-color: #1d4ed8 !important;
  border-color: #1d4ed8 !important;
}

/* Comprehensive Dark Mode Overrides for Streamlit Components */

/* Fix ALL Secondary Buttons, including Popover Buttons (Excel-like Filters) */
body[data-theme="dark"] button[kind="secondary"],
body[data-theme="dark"] button[data-testid="baseButton-secondary"],
body[data-theme="dark"] [data-testid="stPopover"] button,
body[data-theme="dark"] .stPopover button,
body[data-theme="dark"] div[data-testid="stPopover"] > div > button {
  background-color: #1e293b !important;
  color: #f8fafc !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] button[kind="secondary"] *,
body[data-theme="dark"] button[data-testid="baseButton-secondary"] *,
body[data-theme="dark"] [data-testid="stPopover"] button *,
body[data-theme="dark"] .stPopover button * {
  color: #f8fafc !important;
  background-color: transparent !important;
}
body[data-theme="dark"] button[kind="secondary"]:hover,
body[data-theme="dark"] button[data-testid="baseButton-secondary"]:hover,
body[data-theme="dark"] [data-testid="stPopover"] button:hover,
body[data-theme="dark"] .stPopover button:hover {
  background-color: #334155 !important;
  border-color: #475569 !important;
}

body[data-theme="dark"] [data-testid="stPopoverBody"],
body[data-theme="dark"] [data-testid="stPopoverBody"] > div,
body[data-theme="dark"] div[data-baseweb="popover"] > div {
  background-color: #1e293b !important;
  border-color: #334155 !important;
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stPopoverBody"] * {
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stExpander"],
body[data-theme="dark"] [data-testid="stExpander"] > details,
body[data-theme="dark"] [data-testid="stExpander"] > details > summary,
body[data-theme="dark"] [data-testid="stExpanderDetails"] {
  background-color: #1e293b !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] .stExpander summary p {
  color: #f8fafc !important;
}

/* Fix File Uploader Dropzone and Button */
body[data-theme="dark"] [data-testid="stFileUploaderDropzone"] {
  background-color: #0f172a !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] [data-testid="stFileUploaderDropzone"] button {
  background-color: #1e293b !important;
  border-color: #475569 !important;
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stFileUploaderDropzone"] button * {
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stFileUploaderDropzone"] div,
body[data-theme="dark"] [data-testid="stFileUploaderDropzone"] span,
body[data-theme="dark"] [data-testid="stFileUploaderDropzone"] small {
  color: #94a3b8 !important;
}
body[data-theme="dark"] [data-testid="stAlert"],
body[data-theme="dark"] [data-testid="stAlert"] > div,
body[data-theme="dark"] [data-testid="stAlert"] > div > div {
  background-color: #1e293b !important;
  border-color: #334155 !important;
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stAlert"] * {
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
  background-color: #0f172a !important;
  color: #f8fafc !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] [data-baseweb="tag"] {
  background-color: #1e3a8a !important;
  color: #f8fafc !important;
}
body[data-theme="dark"] .stMultiSelect span {
  color: #f8fafc !important;
}
body[data-theme="dark"] .stMultiSelect div[data-baseweb="select"] ul {
  background-color: #1e293b !important;
}
body[data-theme="dark"] .stMultiSelect div[data-baseweb="select"] li {
  color: #f8fafc !important;
}

/* Fix Calendar Popover - Use CSS filter inversion to preserve native contrast ratios perfectly */
body[data-theme="dark"] [data-baseweb="calendar"],
body[data-theme="dark"] div:has(> [data-baseweb="calendar"]) {
  filter: invert(0.85) hue-rotate(180deg) brightness(1.2) contrast(1.1) !important;
}
/* Ensure the popover wrapper doesn't double-apply our dark theme backgrounds before inversion */
body[data-theme="dark"] div[data-baseweb="popover"]:has([data-baseweb="calendar"]) > div {
  background-color: transparent !important;
}
body[data-theme="dark"] [data-testid="stForm"] {
  background-color: #1e293b !important;
  border-color: #334155 !important;
}
body[data-theme="dark"] .expense-table td strong, body[data-theme="dark"] .detail-value strong {
  color: #f8fafc !important;
}
body[data-theme="dark"] [data-testid="stMarkdownContainer"] {
  color: #f8fafc !important;
}
body[data-theme="dark"] .stTextInput input,
body[data-theme="dark"] .stNumberInput input,
body[data-theme="dark"] .stSelectbox div[data-baseweb="select"] > div,
body[data-theme="dark"] .stTextArea textarea,
body[data-theme="dark"] .stDateInput input {
  background-color: #0f172a !important;
  color: #f8fafc !important;
  border-color: #334155 !important;
  -webkit-text-fill-color: #f8fafc !important;
  caret-color: #f8fafc !important;
}
/* Fix Choose Date Range placeholder visibility robustly */
body[data-theme="dark"] .stDateInput [data-baseweb="input"] *,
body[data-theme="dark"] .stDateInput input,
body[data-theme="dark"] .stDateInput input::placeholder {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
  opacity: 1 !important;
}
/* Fix invisible dropdown arrows in Selectbox, MultiSelect, and DateInput */
body[data-theme="dark"] .stSelectbox svg,
body[data-theme="dark"] .stSelectbox [data-testid="stIconMaterial"],
body[data-theme="dark"] .stMultiSelect svg,
body[data-theme="dark"] .stMultiSelect [data-testid="stIconMaterial"],
body[data-theme="dark"] .stDateInput svg,
body[data-theme="dark"] .stDateInput [data-testid="stIconMaterial"] {
  fill: #f8fafc !important;
  color: #f8fafc !important;
}
/* Fix Number Input Step Buttons (+/-) */
body[data-theme="dark"] .stNumberInput button {
  background-color: transparent !important;
  color: #f8fafc !important;
}
body[data-theme="dark"] .stNumberInput button svg,
body[data-theme="dark"] .stNumberInput button [data-testid="stIconMaterial"] {
  fill: #f8fafc !important;
  color: #f8fafc !important;
}
body[data-theme="dark"] .stNumberInput button:hover {
  background-color: #334155 !important;
}
body[data-theme="dark"] label,
body[data-theme="dark"] .stTextInput label,
body[data-theme="dark"] .stNumberInput label,
body[data-theme="dark"] .stSelectbox label,
body[data-theme="dark"] .stTextArea label,
body[data-theme="dark"] .stDateInput label {
  color: #cbd5e1 !important;
}
body[data-theme="dark"] .stSelectbox ul {
  background-color: #1e293b !important;
}
body[data-theme="dark"] .stSelectbox li {
  color: #f8fafc !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

import streamlit.components.v1 as components
theme_html = """
<style>
  html, body { margin: 0; padding: 0; overflow: hidden; }
  .theme-switch-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
  }
  .theme-switch {
    display: inline-block;
    height: 34px;
    position: relative;
    width: 60px;
  }
  .theme-switch input {
    display: none;
  }
  .slider {
    background-color: #cbd5e1;
    bottom: 0;
    cursor: pointer;
    left: 0;
    position: absolute;
    right: 0;
    top: 0;
    transition: .4s;
    border-radius: 34px;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.2);
  }
  .slider:before {
    background-color: #fff;
    bottom: 4px;
    content: "🌞";
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    height: 26px;
    left: 4px;
    position: absolute;
    transition: .4s;
    width: 26px;
    border-radius: 50%;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
  input:checked + .slider {
    background-color: #1e293b;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.5);
  }
  input:checked + .slider:before {
    transform: translateX(26px);
    content: "🌙";
    background-color: #334155;
  }
</style>
<div class="theme-switch-wrapper">
  <label class="theme-switch" for="checkbox">
    <input type="checkbox" id="checkbox" />
    <div class="slider round"></div>
  </label>
</div>
<script>
  const toggleSwitch = document.getElementById('checkbox');
  const parentBody = window.parent.document.body;
  const frameElement = window.frameElement;
  
  if (frameElement) {
      const getScrollTop = () => {
          const stMain = window.parent.document.querySelector('.stMain');
          const appView = window.parent.document.querySelector('.stAppViewContainer');
          return (stMain ? stMain.scrollTop : 0) || (appView ? appView.scrollTop : 0) || window.parent.scrollY || 0;
      };
      
      frameElement.style.position = 'fixed';
      frameElement.style.right = '15px';
      frameElement.style.zIndex = '999999';
      frameElement.style.border = 'none';
      frameElement.style.width = '80px';
      frameElement.style.height = '40px';
      frameElement.style.top = (15 - getScrollTop()) + 'px';
      
      const updateScroll = () => {
          frameElement.style.top = (15 - getScrollTop()) + 'px';
      };
      
      const stMain = window.parent.document.querySelector('.stMain');
      if (stMain) stMain.addEventListener('scroll', updateScroll);
      
      const appView = window.parent.document.querySelector('.stAppViewContainer');
      if (appView) appView.addEventListener('scroll', updateScroll);
      
      window.parent.addEventListener('scroll', updateScroll);
  }
  
  // Set initial state from existing body attribute
  if (parentBody.getAttribute('data-theme') === 'dark') {
      toggleSwitch.checked = true;
  }
  
  toggleSwitch.addEventListener('change', function(e) {
      if (e.target.checked) {
          parentBody.setAttribute('data-theme', 'dark');
      } else {
          parentBody.setAttribute('data-theme', 'light');
      }
  }, false);
</script>
"""
# Render the component transparently and allow it to float via CSS fixed positioning
st.iframe(theme_html, height=40)


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
  "demo_receipt_bytes": None,
  "demo_receipt_name": None,
  "uploader_key": 1,
  "manual_submit_success": False,
  "manual_amount": None,
  "manual_currency": None,
  "manual_category": None,
  "manual_submitter": "",
  "manual_date": None,
  "manual_description": ""
}
for k, v in _defaults.items():
  if k not in st.session_state:
    st.session_state[k] = v


# ──────────────────────────────────────────────────────────────
# DB Helpers
# ──────────────────────────────────────────────────────────────
def _db_path():
  dir_path = os.path.dirname(os.path.abspath(__file__))
  return os.path.join(os.path.dirname(dir_path), "expenses.db")


# Prevent URL privilege escalation bypass by verifying query parameter token if not logged in
if not st.session_state.logged_in:
    email = st.query_params.get("email")
    role = st.query_params.get("role")
    token = st.query_params.get("token")
    if email and role and token:
        import hashlib
        verified = False
        try:
            with sqlite3.connect(_db_path()) as conn:
                cur = conn.cursor()
                cur.execute("SELECT role, password_hash FROM users WHERE email = ?", (email.strip(),))
                row = cur.fetchone()
                if row:
                    db_role, password_hash = row
                    expected_token = hashlib.sha256((email + ":" + password_hash).encode("utf-8")).hexdigest()
                    if token == expected_token and db_role == role and db_role in _VALID_ROLES:
                        st.session_state.logged_in = True
                        st.session_state.email = email
                        st.session_state.role = role
                        verified = True
        except Exception:
            pass
        if not verified:
            st.query_params.clear()
    else:
        if "email" in st.query_params or "role" in st.query_params or "token" in st.query_params:
            st.query_params.clear()

if st.session_state.session_id is None:
  # Bug #5: standardize on async session creation everywhere
  session = asyncio.run(agent_runtime.async_create_session(user_id="streamlit_user"))
  st.session_state.session_id = session["id"]


def verify_credentials(email: str, password: str) -> bool:
  """Verify user credentials against SQLite database."""
  import hashlib
  try:
    hashed_pwd = hashlib.sha256(password.encode("utf-8")).hexdigest()
    with sqlite3.connect(_db_path()) as conn:
      cur = conn.cursor()
      cur.execute(
        "SELECT role FROM users WHERE email = ? AND password_hash = ?",
        (email.strip(), hashed_pwd),
      )
      row = cur.fetchone()
      return row is not None
  except Exception:
    return False


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
  
  Uses a context manager to prevent connection leaks (Bug #4).
  """
  try:
    with sqlite3.connect(_db_path()) as conn:
      cur = conn.cursor()
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


def _esc_description(value: str) -> str:
  """HTML-escape a description string, rendering [Original: ...] and [Warning: ...] notes in styled badges."""
  escaped = html_escape(str(value)) if value else "—"
  import re
  pattern = r'(\[Original:[^\]]+\])'
  def replacer(match):
    note = match.group(1)
    return f'<strong class="conversion-badge">{note}</strong>'
  
  pattern_warning = r'(\[Warning:[^\]]+\])'
  def warning_replacer(match):
    note = match.group(1)
    return f'<strong class="conversion-warning-badge">{note}</strong>'
    
  formatted = re.sub(pattern, replacer, escaped)
  formatted = re.sub(pattern_warning, warning_replacer, formatted)
  return formatted


def get_category_threshold(email: str, category: str) -> float:
  """Get the approval threshold for a category and email domain."""
  import os, json
  policies_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "company_policies.json"
  )
  try:
    with open(policies_path, "r") as f:
      policies = json.load(f)
  except Exception:
    policies = {}

  domain = "default"
  if email and "@" in email:
    domain = email.split("@")[-1].lower()

  company_policy = policies.get(domain, policies.get("default", {}))
  
  threshold = company_policy.get("Default", 100.0)
  for cat_key, val in company_policy.items():
    if cat_key.lower() == category.lower() and cat_key != "company_name":
      threshold = val
      break
  return threshold


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


# ╔═══════════════════════════════════════════════════════════╗
# ║ LOGIN SCREEN                       ║
# ╚═══════════════════════════════════════════════════════════╝
if not st.session_state.logged_in:
  col_l, col_c, col_r = st.columns([1, 1.2, 1])
  with col_c:
    st.markdown(
      """
      <style>
      .premium-login-card {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.8);
        box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.1), 0 10px 20px -5px rgba(0, 0, 0, 0.05);
        border-radius: 28px;
        padding: 2rem 2rem;
        text-align: center;
        margin-top: 0.5rem;
        margin-bottom: 1.5rem;
        transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      }
      .premium-login-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.15), 0 20px 30px -10px rgba(0, 0, 0, 0.1);
      }
      .logo-container {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 150px;
        height: 70px;
        border-radius: 12px;
        margin: 0 auto 1.5rem auto;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
      }
      @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }
      .app-title {
        color: #0F172A;
        font-size: 2.25rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.5rem;
      }
      .app-subtitle {
        color: #64748B;
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 0;
      }
      </style>
      
      <div class="premium-login-card">
        <div class="logo-container">
          <img src=\"""" + logo_img_src + """\" alt="AcmeCorp Logo" style="width: 100%; height: 100%; object-fit: contain;" />
        </div>
        <p class="app-subtitle">Sign in to the Expense Approval Portal</p>
      </div>
      """,
      unsafe_allow_html=True,
    )

    with st.container():
      if "selected_login_role" not in st.session_state:
        st.session_state.selected_login_role = None

      if st.session_state.selected_login_role is None:
        st.markdown("<div style='text-align: center; color: #334155; margin-bottom: 2rem; font-size: 1.1rem; font-weight: bold;'>Select your role to continue</div>", unsafe_allow_html=True)
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
        password = st.text_input("Password", type="password", value="")
        
        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
          if st.button(" Back", use_container_width=True):
            st.session_state.selected_login_role = None
            st.session_state.emp_prev_state = (None, "")
            st.rerun()
        with col_b2:
          signin_clicked = st.button("Sign In", type="primary", use_container_width=True)
          
        current_state = (selected_employee, password)
        previous_state = st.session_state.get("emp_prev_state", (None, ""))
        enter_pressed = (password != "") and (current_state != previous_state)
        
        if signin_clicked or enter_pressed:
          st.session_state.emp_prev_state = current_state
          emp_num = selected_employee.split(" ")[1]
          email = f"employee{emp_num}@acmecorp.com"
          if verify_credentials(email, password):
            st.session_state.logged_in = True
            st.session_state.email = email
            st.session_state.role = "Employee"
            st.query_params["email"] = st.session_state.email
            st.query_params["role"] = st.session_state.role
            
            # Calculate secure token to survive refreshes
            import hashlib
            try:
              with sqlite3.connect(_db_path()) as conn:
                cur = conn.cursor()
                cur.execute("SELECT password_hash FROM users WHERE email = ?", (email.strip(),))
                row = cur.fetchone()
                if row:
                  password_hash = row[0]
                  token = hashlib.sha256((email + ":" + password_hash).encode("utf-8")).hexdigest()
                  st.query_params["token"] = token
            except Exception:
              pass
              
            st.session_state.emp_prev_state = (None, "")
            st.rerun()
          else:
            st.error("Invalid password. Please try again.")
            
      elif st.session_state.selected_login_role == "Admin":
        email = st.text_input("Corporate Email", value="admin@acmecorp.com")
        password = st.text_input("Password", type="password", value="")

        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
          if st.button(" Back", use_container_width=True):
            st.session_state.selected_login_role = None
            st.session_state.admin_prev_state = (None, "")
            st.rerun()
        with col_b2:
          signin_clicked = st.button("Sign In", type="primary", use_container_width=True)

        current_state = (email, password)
        previous_state = st.session_state.get("admin_prev_state", (None, ""))
        enter_pressed = (password != "") and (current_state != previous_state)

        if signin_clicked or enter_pressed:
          st.session_state.admin_prev_state = current_state
          if email.strip():
            if verify_credentials(email, password):
              st.session_state.logged_in = True
              st.session_state.email = email
              st.session_state.role = "Admin"
              st.query_params["email"] = email
              st.query_params["role"] = "Admin"
              
              # Calculate secure token to survive refreshes
              import hashlib
              try:
                with sqlite3.connect(_db_path()) as conn:
                  cur = conn.cursor()
                  cur.execute("SELECT password_hash FROM users WHERE email = ?", (email.strip(),))
                  row = cur.fetchone()
                  if row:
                    password_hash = row[0]
                    token = hashlib.sha256((email + ":" + password_hash).encode("utf-8")).hexdigest()
                    st.query_params["token"] = token
              except Exception:
                pass
                
              st.session_state.admin_prev_state = (None, "")
              st.rerun()
            else:
              st.error("Invalid email or password.")
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
      <img src=\"""" + logo_img_src + """\" alt="AcmeCorp Logo" class="sidebar-logo-img" />
      <div class="sidebar-logo-sub">Expenses Management</div>
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
  else:
    st.markdown('<div class="nav-active">Submit Expense</div>', unsafe_allow_html=True)

  st.markdown("---")

  # Dynamic Policy Limits Display
  if st.session_state.email:
    meals_lim = get_category_threshold(st.session_state.email, "Meals")
    travel_lim = get_category_threshold(st.session_state.email, "Travel")
    equip_lim = get_category_threshold(st.session_state.email, "Equipment")
    other_lim = get_category_threshold(st.session_state.email, "Default")
    
    # Extract company name
    import os, json
    p_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "company_policies.json")
    try:
      with open(p_path, "r") as f:
        p_data = json.load(f)
    except Exception:
      p_data = {}
    
    domain = st.session_state.email.split("@")[-1].lower() if "@" in st.session_state.email else "default"
    company_name = p_data.get(domain, p_data.get("default", {})).get("company_name", "Corporate")

    st.markdown(
      f"""<div style="background-color: rgba(255,255,255,0.05); padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.1);">
        <div style="font-weight: 600; font-size: 1.1rem; color: #FFF; margin-bottom: 0.6rem;">{company_name} Limits</div>
        <div style="font-size: 0.9rem; color: #CBD5E1; line-height: 1.5;">
          <div>• Meals: <strong>${meals_lim:.2f}</strong></div>
          <div>• Travel: <strong>${travel_lim:.2f}</strong></div>
          <div>• Equipment: <strong>${equip_lim:.2f}</strong></div>
          <div>• Others / Miscellaneous: <strong>${other_lim:.2f}</strong></div>
        </div>
      </div>""",
      unsafe_allow_html=True,
    )

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
      key=f"receipt_uploader_{st.session_state.get('uploader_key', 1)}"
    )

    has_demo = "demo_receipt_bytes" in st.session_state and st.session_state.demo_receipt_bytes

    col_d1, col_d2 = st.columns([1.5, 3])
    with col_d1:
      if not has_demo:
        if st.button("Load Demo Receipt"):
          try:
            import random
            import json
            receipts = [
              "demo_receipt_eur.png",
              "demo_receipt_gbp.png",
              "demo_receipt_jpy.png",
              "demo_receipt_inr.png",
              "demo_receipt_cad.png",
            ]
            
            state_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".last_receipt.json")
            last_chosen = None
            try:
              if os.path.exists(state_file):
                with open(state_file, "r") as f:
                  last_chosen = json.load(f).get("last_receipt")
            except Exception:
              pass

            available = [r for r in receipts if r != last_chosen]
            chosen_receipt = random.choice(available if available else receipts)
            
            try:
              with open(state_file, "w") as f:
                json.dump({"last_receipt": chosen_receipt}, f)
            except Exception:
              pass
              
            st.session_state.last_chosen_receipt = chosen_receipt
            st.session_state.demo_receipt_name = chosen_receipt
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
          st.session_state.demo_receipt_name = None
          st.rerun()

    image_to_submit = None
    mime_type = "image/png"

    if uploaded_file is not None:
      image_to_submit = uploaded_file.getvalue()
      mime_type = uploaded_file.type
    elif (
      "demo_receipt_bytes" in st.session_state
      and st.session_state.demo_receipt_bytes
    ):
      image_to_submit = st.session_state.demo_receipt_bytes
      filename = st.session_state.get("demo_receipt_name", "Other.png")
      import re
      name_part, ext_part = os.path.splitext(filename)
      category_name = re.sub(r'_\d+$', '', name_part)
      category_name = category_name.replace('_', ' ')
      ext_lower = ext_part.replace(".", "").lower()
      formatted_caption = f"{category_name}.{ext_lower}"

    if image_to_submit is None:
        st.session_state.review_expense_data = None
        st.session_state.review_session_to_track = None
        st.session_state.review_is_paused = False
        st.session_state.uploaded_filename = None
        st.session_state.from_review_submit = False
        st.session_state.review_submitted_success = False

    if st.session_state.get("review_expense_data"):
      st.markdown('<div style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">Review & Confirm Details</div>', unsafe_allow_html=True)
      st.info("Please review the auto-extracted details below. Make any necessary corrections before submitting.")
      
      col_img, col_rev = st.columns([1, 1.2])
      
      with col_img:
        if image_to_submit:
            st.image(image_to_submit, caption="Uploaded Receipt", use_container_width=True)
            
      with col_rev:
        exp_data = st.session_state.review_expense_data
        
        orig_currency = exp_data.get("original_currency", exp_data.get("currency", "USD"))
        usd_amount = exp_data.get("amount", 0.0)

        is_success = st.session_state.get("review_submitted_success", False)
        with st.form("review_form"):
          rev_amount = st.number_input("Amount", value=float(usd_amount), disabled=is_success)
          
          if orig_currency.upper() != "USD" and "exchange_rate" in exp_data:
            st.caption(f"*(Converted to USD using live rate: 1 {orig_currency.upper()} = ${exp_data.get('exchange_rate')} USD)*")

          all_currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AWG", "AZN", "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL", "BSD", "BTN", "BWP", "BYN", "BZD", "CDF", "CLP", "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP", "ERN", "ETB", "FJD", "FKP", "FOK", "GEL", "GGP", "GHS", "GIP", "GMD", "GNF", "GTQ", "GYD", "HKD", "HNL", "HRK", "HTG", "HUF", "IDR", "ILS", "IMP", "IQD", "IRR", "ISK", "JEP", "JMD", "JOD", "KES", "KGS", "KHR", "KID", "KMF", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD", "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU", "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK", "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG", "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK", "SGD", "SHP", "SLE", "SLL", "SOS", "SRD", "SSP", "STN", "SYP", "SZL", "THB", "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TVD", "TWD", "TZS", "UAH", "UGX", "UYU", "UZS", "VES", "VND", "VUV", "WST", "XAF", "XCD", "XDR", "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL"]
          curr_val = orig_currency.upper()
          curr_idx = all_currencies.index(curr_val) if curr_val in all_currencies else 0
          rev_currency = st.selectbox("Currency", options=all_currencies, index=curr_idx, disabled=is_success)
          
          rev_vendor = st.text_input("Vendor", value=exp_data.get("vendor", ""), disabled=is_success)
          
          categories = ["Meals", "Travel", "Equipment", "Office Supplies", "Software", "Miscellaneous"]
          cat_val = exp_data.get("category", "Miscellaneous")
          cat_idx = categories.index(cat_val) if cat_val in categories else 5
          rev_category = st.selectbox("Category", options=categories, index=cat_idx, disabled=is_success)
          
          try:
            import datetime
            parsed_date = datetime.datetime.strptime(exp_data.get("date", ""), "%Y-%m-%d").date()
          except Exception:
            import datetime
            parsed_date = datetime.date.today()
            
          rev_date = st.date_input("Date on Receipt", value=parsed_date, disabled=is_success)
          rev_desc = st.text_area("Description", value=exp_data.get("description", ""), disabled=is_success)
          
          if not is_success:
            col_submit, col_cancel = st.columns(2)
            with col_submit:
              submitted = st.form_submit_button("Confirm & Submit", type="primary", use_container_width=True)
            with col_cancel:
              canceled = st.form_submit_button("Cancel", use_container_width=True)
          else:
            submitted = False
            canceled = False
            st.form_submit_button("Submitted", disabled=True, use_container_width=True)
            
          if submitted:
            resubmit_payload = {
                "amount": rev_amount,
                "currency": rev_currency,
                "vendor": rev_vendor,
                "category": rev_category,
                "date": rev_date.strftime("%Y-%m-%d"),
                "description": rev_desc,
                "submitter": st.session_state.email,
                "is_ui_resubmit": True,
                "original_amount": exp_data.get("original_amount"),
                "original_currency": exp_data.get("original_currency"),
                "exchange_rate": exp_data.get("exchange_rate"),
                "ocr_amount": float(exp_data.get("original_amount", exp_data.get("amount", 0.0))),
                "ocr_currency": exp_data.get("original_currency", exp_data.get("currency", "USD")),
                "ocr_vendor": exp_data.get("vendor", ""),
                "ocr_category": exp_data.get("category", ""),
                "ocr_date": exp_data.get("date", "")
            }
            
            with st.spinner("Applying Acme Corp policies to updated data..."):
                st.session_state.from_review_submit = True
                import json
                message_dict = {
                    "parts": [{"text": json.dumps({"expense": resubmit_payload})}],
                    "role": "user",
                }
                
                # We reuse the existing session_id that is already in st.session_state 
                # so we don't clutter the backend with multiple sessions for one expense.
                
                events = run_agent(message_dict)
                process_events(events)
                
            st.session_state.review_is_paused = False
            st.session_state.from_review_submit = False
            st.session_state.review_submitted_success = True
            st.rerun()
            
          if canceled:
            st.session_state.review_expense_data = None
            st.session_state.review_session_to_track = None
            st.session_state.demo_receipt_bytes = None
            st.session_state.demo_receipt_name = None
            st.session_state.uploader_key = st.session_state.get('uploader_key', 1) + 1
            st.rerun()
            
        if is_success:
            st.success("Expense processed successfully and routed to Admin if required!")
            if st.button("Submit Another Receipt", type="primary"):
                st.session_state.review_expense_data = None
                st.session_state.review_session_to_track = None
                st.session_state.demo_receipt_bytes = None
                st.session_state.demo_receipt_name = None
                st.session_state.uploader_key = st.session_state.get('uploader_key', 1) + 1
                st.session_state.review_submitted_success = False
                st.rerun()
            
    else:
      if image_to_submit is not None:
        st.image(image_to_submit, caption="Uploaded Receipt", width=500)



    if not st.session_state.get("review_expense_data"):
      if st.button(
        "Extract Details",
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
            st.session_state.from_review_submit = False

            base64_image = base64.b64encode(image_to_submit).decode("utf-8")
            st.session_state.submitted_receipt_image = base64_image
            st.session_state.submitted_receipt_mime = mime_type

            payload_dict = {
              "image_data": base64_image,
              "mime_type": mime_type,
              "submitter": st.session_state.email,
            }
            with st.spinner("Extracting details from receipt..."):
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
    def reset_manual_form():
      st.session_state.manual_amount = None
      st.session_state.manual_currency = None
      st.session_state.manual_category = None
      st.session_state.manual_submitter = st.session_state.email
      st.session_state.manual_date = date.today()
      st.session_state.manual_description = ""
      st.session_state.manual_submit_success = False
      st.session_state.agent_messages = []

    if not st.session_state.get("manual_submitter") and st.session_state.email:
      st.session_state.manual_submitter = st.session_state.email
    if not st.session_state.get("manual_date"):
      st.session_state.manual_date = date.today()

    if st.session_state.get("manual_submit_success"):
      st.success("Expense processed successfully and routed to Admin if required!")
      
    with st.form("expense_form", clear_on_submit=False):
      col_cur, col_a, col_conv, col_b = st.columns([1, 1, 1, 1.2])
      with col_cur:
        # Extensive list of global currencies
        all_currencies = [
            "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR",
            "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AWG", "AZN", 
            "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", 
            "BRL", "BSD", "BTN", "BWP", "BYN", "BZD", "CDF", "CLP", "COP", 
            "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP", 
            "ERN", "ETB", "FJD", "FKP", "GEL", "GHS", "GIP", "GMD", "GNF", 
            "GTQ", "GYD", "HKD", "HNL", "HRK", "HTG", "HUF", "IDR", "ILS", 
            "IQD", "IRR", "ISK", "JMD", "JOD", "KES", "KGS", "KHR", "KMF", 
            "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD", 
            "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", 
            "MRU", "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", 
            "NIO", "NOK", "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", 
            "PKR", "PLN", "PYG", "QAR", "RON", "RSD", "RUB", "RWF", "SAR", 
            "SBD", "SCR", "SDG", "SEK", "SGD", "SHP", "SLL", "SOS", "SRD", 
            "SSP", "STN", "SYP", "SZL", "THB", "TJS", "TMT", "TND", "TOP", 
            "TRY", "TTD", "TWD", "TZS", "UAH", "UGX", "UYU", "UZS", "VES", 
            "VND", "VUV", "WST", "XAF", "XCD", "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL"
        ]
        exp_currency = st.selectbox(
          "Currency",
          all_currencies,
          index=None,
          placeholder="Select Currency...",
          key="manual_currency",
        )
      with col_a:
        exp_amount = st.number_input(
          "Amount",
          min_value=0.01,
          step=0.01,
          format="%.2f",
          value=None,
          placeholder="0.00",
          key="manual_amount",
        )
      # Calculate converted USD value
      usd_val = None
      rate_str = ""
      if exp_amount and exp_currency:
        if exp_currency != "USD":
          from expense_agent.agent import convert_to_usd
          usd_val, rate, _ = convert_to_usd(float(exp_amount), exp_currency, str(date.today()))
          rate_str = f"*(Converted to USD using live rate: 1 {exp_currency.upper()} = ${rate} USD)*"
        else:
          usd_val = float(exp_amount)

      with col_conv:
        st.number_input(
          "Amount (USD)",
          value=usd_val,
          disabled=True,
          format="%.2f",
          placeholder="0.00",
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
          index=None,
          placeholder="Select Category...",
          key="manual_category",
        )

      if rate_str:
        st.caption(rate_str)

      col_c, col_d = st.columns(2)
      with col_c:
        exp_submitter = st.text_input(
          "Submitter Email", key="manual_submitter"
        )
      with col_d:
        exp_date = st.date_input("Expense Date", key="manual_date")

      exp_description = st.text_area(
        "Purpose / Justification",
        placeholder="Describe the purpose of this expense…",
        height=100,
        key="manual_description",
      )

      col_btn1, col_btn2 = st.columns(2)
      with col_btn1:
        submitted = st.form_submit_button(
          "Submit Expense",
          type="primary",
          use_container_width=True,
        )
      with col_btn2:
        cleared = st.form_submit_button(
          "Clear Form",
          use_container_width=True,
          on_click=reset_manual_form,
        )

    if submitted:
      if not exp_amount:
        st.error("Please enter a valid amount.")
      elif not exp_currency:
        st.error("Please select a currency.")
      elif not exp_category:
        st.error("Please select a category.")
      elif not exp_submitter.strip():
        st.error("Please enter the submitter email.")
      elif not exp_description.strip():
        st.error("Please provide a description for the expense.")
      else:
        try:
          session = asyncio.run(agent_runtime.async_create_session(user_id="streamlit_user"))
          st.session_state.session_id = session["id"]
          st.session_state.waiting_for_input = False
          st.session_state.final_output = None
          st.session_state.agent_messages = []
          st.session_state.submitted_receipt_image = None
          st.session_state.review_expense_data = None
          st.session_state.from_review_submit = False
          st.session_state.review_submitted_success = False
          st.session_state.manual_submit_success = False

          data = {
            "amount": float(exp_amount),
            "currency": exp_currency,
            "submitter": exp_submitter,
            "category": exp_category,
            "description": exp_description,
            "date": str(exp_date),
            "is_manual_submit": True,
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



  # ── Progress / Final output ────────────────────
  if st.session_state.agent_messages:
    with st.expander(" Submission Progress", expanded=True):
      for msg in st.session_state.agent_messages:
        st.markdown(msg)

  # ── My Expenses Table ────────────────────────────────────
  @st.fragment(run_every="5s")
  def render_employee_expenses():
    my_pending = [r for r in get_all_pending_approvals() if r.get("submitter_email") == st.session_state.email]
    
    if my_pending:
      st.warning(f" You have {len(my_pending)} expense(s) submitted — pending Admin approval.")
      
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
          
          # Extract original conversion note if present in description
          desc = exp.get('description', '—')
          amount_display = f"${exp.get('amount',0):.2f}"
          import re
          match = re.search(r'\[Original: ([\d.]+) ([A-Z]+) converted at', desc)
          if match:
              orig_amt = match.group(1)
              orig_cur = match.group(2)
              amount_display = f"{orig_amt} {orig_cur}<br><small style='color:gray'>≈ ${exp.get('amount',0):.2f} USD</small>"
              desc = re.sub(r' \[Original: .*?\]', '', desc)

          rows_html += f"""<tr>
            <td><strong>{_esc(exp_id)}</strong></td>
            <td>{_esc(exp.get('date','—'))}</td>
            <td>{_esc(exp.get('category','—'))}</td>
            <td><strong>{amount_display}</strong></td>
            <td>{_esc(desc[:60])}</td>
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

  render_employee_expenses()


# ╔═══════════════════════════════════════════════════════════╗
# ║ ADMIN DASHBOARD                     ║
# ╚═══════════════════════════════════════════════════════════╝
elif st.session_state.role == "Admin":
  @st.fragment(run_every="5s")
  def render_admin_dashboard():
    # ── All Expenses Table ───────────────────────────────────
    all_expenses = get_all_expenses()
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
  
        threshold = get_category_threshold(submitter_str, exp_category)

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
    <div class="detail-value">{_esc(exp_category)} (Threshold: ${threshold:.2f})</div>
    <div class="detail-label">Purpose:</div>
    <div class="detail-value">{_esc_description(description_str)}</div>
  </div>
</div>""",
          unsafe_allow_html=True,
        )

          
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
                try:
                  events = run_agent(payload, specific_session_id=session_id)
                  process_events(events, run_session_id=session_id, submitter_email=submitter_email)
                  delete_pending_approval(db_id)
                  st.rerun()
                except Exception as e:
                  if "Session not found" in str(e):
                    st.toast("Session expired (server restarted). Manually saving rejection.", icon="ℹ️")
                    fallback_exp = {
                      "amount": float(details.get("amount", 0.0)),
                      "submitter": submitter_str,
                      "category": exp_category,
                      "description": details.get("description", "—") + f" [Comment: {rejection_reason}]",
                      "date": exp_date
                    }
                    save_expense(fallback_exp, "Rejected")
                    delete_pending_approval(db_id)
                    st.rerun()
                  else:
                    st.error(f"Error resuming workflow: {e}")
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
              try:
                events = run_agent(payload, specific_session_id=session_id)
                process_events(events, run_session_id=session_id, submitter_email=submitter_email)
                delete_pending_approval(db_id)
                st.rerun()
              except Exception as e:
                if "Session not found" in str(e):
                  st.toast("Session expired (server restarted). Manually saving approval.", icon="ℹ️")
                  fallback_exp = {
                    "amount": float(details.get("amount", 0.0)),
                    "submitter": submitter_str,
                    "category": exp_category,
                    "description": details.get("description", "—"),
                    "date": exp_date
                  }
                  save_expense(fallback_exp, "Approved")
                  delete_pending_approval(db_id)
                  st.rerun()
                else:
                  st.error(f"Error resuming workflow: {e}")
  
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
    <div class="detail-value">{_esc_description(exp.get('description','—'))}</div>
    <div class="detail-label">Reason:</div>
    <div class="detail-value">{_esc(reason)}</div>
  </div>
</div>""",
            unsafe_allow_html=True,
          )
          st.markdown("---")
      else:
        st.info("No pending expenses require review at this time.")

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

  render_admin_dashboard()
