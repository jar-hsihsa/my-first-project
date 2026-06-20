# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import base64
import re
import sqlite3
from typing import Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from google.adk.workflow import Workflow, node, START, Edge
from google.adk.apps import App, ResumabilityConfig
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google import genai
from google.genai import types

from expense_agent.config import EXPENSE_THRESHOLD, MODEL_NAME

# Load environmental variables from .env file
load_dotenv()

# Conditional authentication configuration
use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ("true", "1")
if use_vertex:
    import google.auth
    try:
        _, project_id = google.auth.default()
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id or "")
    except Exception:
        pass
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")


# SQLite Duplicate Detection Database Helpers
def get_db_connection():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(os.path.dirname(dir_path), "expenses.db")
    return sqlite3.connect(db_path)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Drop table to generate fresh invoices on restart
    cursor.execute("DROP TABLE IF EXISTS expenses")
    cursor.execute("""
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            submitter TEXT,
            category TEXT,
            description TEXT,
            date TEXT,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


def check_duplicate(amount: float, date: str, submitter: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM expenses WHERE amount = ? AND date = ? AND submitter = ?",
            (amount, date, submitter)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def insert_expense(amount: float, date: str, submitter: str, category: str, description: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (amount, date, submitter, category, description) VALUES (?, ?, ?, ?, ?)",
            (amount, date, submitter, category, description)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# Initialize database
init_db()


class ExpenseReport(BaseModel):
    amount: float = Field(description="The dollar amount of the expense.")
    submitter: str = Field(description="The name or email of the person submitting the expense.")
    category: str = Field(description="The category of the expense (e.g., travel, meals).")
    description: str = Field(description="The description or justification for the expense.")
    date: str = Field(description="The date of the expense.")


def extract_input_json(node_input: Any) -> dict:
    """Helper to extract a dictionary from the predecessor node input."""
    if isinstance(node_input, dict):
        return node_input

    def try_parse(text: str) -> dict | None:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_candidate = text[start:end+1]
            try:
                return json.loads(json_candidate)
            except Exception:
                pass
        return None

    if isinstance(node_input, str):
        res = try_parse(node_input)
        if res is not None:
            return res

    if hasattr(node_input, "parts"):
        for part in node_input.parts:
            if part.text:
                res = try_parse(part.text)
                if res is not None:
                    return res

    raise ValueError(f"Could not parse input as JSON: {node_input}")


def parse_expense_from_event(event: dict) -> ExpenseReport:
    """Helper to parse the expense from base64 data key or plain JSON."""
    if "image_data" in event:
        image_bytes = base64.b64decode(event["image_data"])
        mime_type = event.get("mime_type", "image/png")
        
        client = genai.Client(vertexai=use_vertex)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Extract the expense details from this receipt. If the submitter/employee email is not on the receipt, set it to 'employee@acmecorp.com'."
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExpenseReport
            )
        )
        data_dict = json.loads(response.text)
        return ExpenseReport.model_validate(data_dict)

    data = event.get("data")
    if not data:
        # Check if details are directly in the event
        return ExpenseReport.model_validate(event)

    if isinstance(data, str):
        # Handle possible base64 encoding
        try:
            decoded_bytes = base64.b64decode(data, validate=True)
            decoded_str = decoded_bytes.decode("utf-8")
            data_dict = json.loads(decoded_str)
        except Exception:
            # Fallback to plain JSON string
            try:
                data_dict = json.loads(data)
            except Exception:
                raise ValueError(f"Unable to parse data string: {data}")
    elif isinstance(data, dict):
        data_dict = data
    else:
        raise ValueError(f"Unsupported data format under 'data' key: {data}")

    # Handle inner nesting if payload wraps details inside an 'expense' key
    if "expense" in data_dict:
        data_dict = data_dict["expense"]

    return ExpenseReport.model_validate(data_dict)


@node
def parse_expense_node(ctx: Context, node_input: Any) -> Event:
    """Decodes the incoming event payload and parses the expense report."""
    try:
        # Try to parse the input as a new expense payload
        event_dict = extract_input_json(node_input)
        expense = parse_expense_from_event(event_dict)
        expense_dict = expense.model_dump()
        
        # Increment run count for sequential testing in the same session
        run_count = ctx.state.get("run_count", 0) + 1
        
        # If successful, reset state keys for a new evaluation run in the same session
        return Event(
            output={"expense": expense_dict},
            state={
                "expense": expense_dict,
                "risk_assessment": None,
                "redacted_categories": [],
                "is_security_event": False,
                "is_injection": False,
                "run_count": run_count
            }
        )
    except Exception as e:
        # If parsing fails, it's likely a resume input (e.g. "Approve"), fallback to cached state
        if ctx.state.get("expense"):
            return Event(output={"expense": ctx.state["expense"]})
            
        raise ValueError(f"Error parsing expense receipt/payload: {e}")

def is_luhn_valid(cc_str: str) -> bool:
    """Validate credit card number using Luhn algorithm."""
    digits = [int(c) for c in cc_str if c.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            double = digit * 2
            checksum += double - 9 if double > 9 else double
        else:
            checksum += digit
    return checksum % 10 == 0


def scrub_personal_data(description: str) -> tuple[str, list[str]]:
    """Scrub SSNs and Credit Card numbers from the description."""
    redacted_categories = []
    
    # 1. Scrub SSNs: standard XXX-XX-XXXX or XXX XX XXXX
    ssn_pattern = re.compile(r'\b\d{3}[- ]\d{2}[- ]\d{4}\b')
    cleaned = description
    if ssn_pattern.search(cleaned):
        cleaned = ssn_pattern.sub("[REDACTED SSN]", cleaned)
        redacted_categories.append("SSN")
        
    # 2. Scrub Credit Cards
    cc_candidate_pattern = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
    
    def cc_replacer(match):
        candidate = match.group(0)
        digits_only = re.sub(r'[^0-9]', '', candidate)
        if is_luhn_valid(digits_only):
            if "Credit Card" not in redacted_categories:
                redacted_categories.append("Credit Card")
            return "[REDACTED CREDIT CARD]"
        return candidate

    cleaned = cc_candidate_pattern.sub(cc_replacer, cleaned)
    
    return cleaned, redacted_categories


def detect_prompt_injection(description: str) -> bool:
    """Detect prompt injection attempts trying to force auto-approval or bypass rules."""
    desc_lower = description.lower()
    
    injection_keywords = [
        "ignore", "bypass", "override", "force", "auto-approve", "auto approve",
        "system prompt", "forget", "instructions", "rules", "policy", "prior instructions",
        "disregard", "do not evaluate", "approve immediately", "always approve", "system instructions",
        "prompt injection"
    ]
    
    for kw in injection_keywords:
        if kw in desc_lower:
            return True
            
    if "ignore all" in desc_lower or "ignore the" in desc_lower or "ignore previous" in desc_lower:
        return True
    if "you must approve" in desc_lower or "must be approved" in desc_lower:
        return True
        
    return False


@node
def security_checkpoint_node(ctx: Context, node_input: dict) -> Event:
    """Security checkpoint that scrubs personal data and checks for prompt injections.
    
    CRITICAL: Irrespective of the expense amount, if PII data is detected or a prompt
    injection attempt is identified, the request is immediately escalated to a human
    reviewer. It will never be auto-approved.
    """
    expense = node_input["expense"]
    desc = expense.get("description", "")
    
    # 1. Scrub personal data
    clean_desc, redacted = scrub_personal_data(desc)
    expense["description"] = clean_desc
    
    # Update state
    ctx.state["expense"] = expense
    ctx.state["redacted_categories"] = redacted
    
    # 2. Check prompt injection and add it to the violations list if detected
    is_injection = detect_prompt_injection(clean_desc)
    if is_injection:
        redacted.append("Prompt Injection")

    # 3. Check for duplicates
    is_dup = check_duplicate(expense.get("amount", 0.0), expense.get("date", ""), expense.get("submitter", ""))
    if is_dup:
        redacted.append("Duplicate Expense")

    # Update output with the final (possibly extended) violations list
    output_data = {
        "expense": expense,
        "redacted_categories": redacted
    }

    # CRITICAL RISK: Escalate to human review if PII detected OR injection attempted.
    # This check happens before dollar-threshold routing so that no amount can
    # bypass security controls via auto-approve.
    has_violations = len(redacted) > 0

    if has_violations:
        # redacted now contains ALL violations e.g. ["SSN", "Credit Card", "Prompt Injection"]
        risk_msg = (
            f"CRITICAL RISK: Violations detected — {', '.join(redacted)}. "
            "Escalated for human review."
        )

        ctx.state["is_security_event"] = True
        ctx.state["risk_assessment"] = risk_msg
        output_data["risk_assessment"] = risk_msg
        return Event(
            output=output_data,
            state={
                "expense": expense,
                "redacted_categories": redacted,
                "is_security_event": True,
                "is_injection": is_injection,
                "risk_assessment": risk_msg
            },
            route="security_escalation"
        )
    else:
        return Event(
            output=output_data,
            state={
                "expense": expense,
                "redacted_categories": redacted
            },
            route="amount_check"
        )



@node
def route_expense_node(node_input: dict) -> Event:
    """Routes the expense report based on the configured dollar threshold."""
    expense = node_input["expense"]
    amount = expense["amount"]
    submitter = expense.get("submitter", "")
    category = expense.get("category", "")
    
    # Extract domain
    domain = "default"
    if "@" in submitter:
        domain = submitter.split("@")[-1].lower()
        
    # Load policies
    try:
        dir_path = os.path.dirname(os.path.abspath(__file__))
        policies_path = os.path.join(os.path.dirname(dir_path), "company_policies.json")
        with open(policies_path, "r") as f:
            policies = json.load(f)
    except Exception:
        policies = {}
        
    company_policy = policies.get(domain, policies.get("default", {}))
    company_name = company_policy.get("company_name", "Generic Corporate")
    
    # Get threshold for category (case-insensitive key check or fallback to Default)
    threshold = company_policy.get("Default", 100.0)
    for cat_key, val in company_policy.items():
        if cat_key.lower() == category.lower() and cat_key != "company_name":
            threshold = val
            break
            
    node_input["applied_threshold"] = threshold
    node_input["company_name"] = company_name

    if amount < threshold:
        return Event(output=node_input, route="auto_approve")
    else:
        return Event(output=node_input, route="risk_review")


@node
def auto_approve_node(node_input: dict) -> dict:
    """Automatically approves expenses under the threshold without LLM intervention."""
    expense = node_input["expense"]
    threshold = node_input.get("applied_threshold", EXPENSE_THRESHOLD)
    company_name = node_input.get("company_name", "Generic Corporate")
    return {
        "expense": expense,
        "decision": "Approved",
        "reason": f"Amount ${expense['amount']} is under {company_name} threshold of ${threshold}. Auto-approved.",
        "risk_assessment": "Skipped (Auto-approved)"
    }


@node
async def risk_review_node(ctx: Context, node_input: dict) -> Event:
    """Uses LLM to evaluate risks/policy violations for expenses >= threshold."""
    expense = node_input["expense"]
    threshold = node_input.get("applied_threshold", EXPENSE_THRESHOLD)
    company_name = node_input.get("company_name", "Generic Corporate")
    
    if ctx.state.get("risk_assessment"):
        return Event(
            output={
                "expense": expense,
                "risk_assessment": ctx.state["risk_assessment"]
            }
        )
    
    prompt = f"""
    You are an AI risk analyst reviewing corporate expense reports for {company_name}.
    Please review the following expense report details for risk factors (e.g., potential policy violations, suspicious amounts or categories, duplicate-looking entries, or inappropriate descriptions).
    Note that the dynamic auto-approval threshold for this category ({expense.get('category', 'Default')}) is ${threshold}.
    
    Expense Details:
    - Amount: ${expense['amount']}
    - Submitter: {expense['submitter']}
    - Category: {expense['category']}
    - Description: {expense['description']}
    - Date: {expense['date']}
    
    Provide a concise risk assessment summary (max 3 sentences) outlining any risk factors or why it looks safe.
    """
    
    client = genai.Client(vertexai=use_vertex)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    
    risk_assessment = response.text or "No risk assessment generated."
    
    return Event(
        output={
            "expense": expense,
            "risk_assessment": risk_assessment
        },
        state={"risk_assessment": risk_assessment}
    )


@node
async def human_approval_gate(ctx: Context, node_input: dict):
    """Pauses workflow to await manual human approval or rejection."""
    expense = node_input["expense"]
    run_count = ctx.state.get("run_count", 1)
    interrupt_id = f"approval_{run_count}"

    # Build the header – include security context when present
    is_security = ctx.state.get("is_security_event", False)
    is_injection = ctx.state.get("is_injection", False)
    redacted = node_input.get("redacted_categories") or ctx.state.get("redacted_categories", [])
    risk_assessment = node_input.get("risk_assessment") or ctx.state.get("risk_assessment", "N/A")

    security_lines = ""
    if is_security:
        security_lines += "\n⚠️  SECURITY EVENT FLAGGED"
    if is_injection:
        security_lines += "\n🚨 Prompt Injection Detected"
    if redacted:
        security_lines += f"\n🔒 Redacted PII Categories: {', '.join(redacted)}"

    msg = (
        f"EXPENSE APPROVAL REQUIRED:{security_lines}\n"
        f"Expense of ${expense['amount']} by {expense['submitter']} "
        f"for '{expense['description']}' requires review.\n"
        f"Risk Assessment: {risk_assessment}\n"
        f"Please reply with 'Approve' or 'Reject' (or custom message)."
    )
    yield RequestInput(interrupt_id=interrupt_id, message=msg)



@node
def outcome_node(ctx: Context, node_input: Any):
    """Logs the final outcome and formats it for displaying in the Web UI."""
    if isinstance(node_input, dict) and "decision" in node_input:
        expense = node_input["expense"]
        decision = node_input["decision"]
        reason = node_input["reason"]
        risk = node_input["risk_assessment"]
    else:
        # It's a resume response string from human_approval_gate
        expense = ctx.state.get("expense", {})
        risk = ctx.state.get("risk_assessment", "N/A")
        decision_text = str(node_input)
        decision = "Approved" if "approve" in decision_text.lower() else "Rejected"
        reason = f"Decision made by human reviewer: {decision_text}"
    
    is_security_event = ctx.state.get("is_security_event", False)
    is_injection = ctx.state.get("is_injection", False)
    redacted = ctx.state.get("redacted_categories", [])
    has_pii = len(redacted) > 0
    
    content_text = (
        f"### Expense Report Summary\n"
        f"- **Submitter**: {expense.get('submitter', 'N/A')}\n"
        f"- **Amount**: ${expense.get('amount', 0.0)}\n"
        f"- **Category**: {expense.get('category', 'N/A')}\n"
        f"- **Description**: {expense.get('description', 'N/A')}\n"
        f"- **Date**: {expense.get('date', 'N/A')}\n"
        f"- **Status**: **{decision}**\n"
        f"- **Reason**: {reason}\n"
    )
    if redacted:
        content_text += f"- **Redacted Info**: {', '.join(redacted)}\n"
    if is_security_event:
        # Build security label directly from state flags — not from string parsing
        if is_injection and has_pii:
            sec_label = f"⚠️ CRITICAL RISK: PII Detected ({', '.join(redacted)}) AND Prompt Injection Attempted"
        elif is_injection:
            sec_label = "⚠️ CRITICAL RISK: Prompt Injection Attempted"
        elif has_pii:
            sec_label = f"⚠️ CRITICAL RISK: PII Data Detected ({', '.join(redacted)})"
        else:
            sec_label = "⚠️ FLAGGED SECURITY EVENT"
        content_text += f"- **Security Status**: {sec_label}\n"
    content_text += f"- **Risk Assessment**: {risk}\n"
    
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=content_text)]
        )
    )
    
    if decision == "Approved":
        insert_expense(
            expense.get("amount", 0.0),
            expense.get("date", ""),
            expense.get("submitter", ""),
            expense.get("category", ""),
            expense.get("description", "")
        )

    output_dict = {
        "expense": expense,
        "decision": decision,
        "reason": reason,
        "risk_assessment": risk
    }
    if redacted:
        output_dict["redacted_categories"] = redacted
    if is_security_event:
        output_dict["is_security_event"] = True
        
    yield Event(output=output_dict)


# Construct the ADK 2.0 Graph Workflow API
#
# Graph flow:
#   START -> parse_expense_node -> security_checkpoint_node
#                                          |
#              .---------------------------|---------------------------.
#              |                           |                           |
#     route="security_escalation"  route="amount_check"               |
#              |                           |                           |
#              v                    route_expense_node                 |
#    human_approval_gate (direct)    /           \                    |
#              |               auto_approve   risk_review             |
#              |                    |              |                  |
#              |              auto_approve_node  risk_review_node     |
#              |                    |              |                  |
#              '--------------------'--------------'------------------'
#                                          |
#                                    outcome_node
#                                          |
#                                  notification_node


@node
def notification_node(ctx: Context, node_input: dict) -> Event:
    """Mock node that formats and logs an email notification summarizing the outcome."""
    expense = node_input["expense"]
    decision = node_input["decision"]
    reason = node_input["reason"]
    risk = node_input["risk_assessment"]
    submitter = expense.get("submitter", "employee@acmecorp.com")
    
    email_subject = f"Notification: Your Expense Report has been {decision}"
    email_body = (
        f"To: {submitter}\n"
        f"From: expense-system@acmecorp.com\n"
        f"Subject: {email_subject}\n\n"
        f"Dear Employee,\n\n"
        f"Your expense report submitted on {expense.get('date', 'N/A')} for the amount of "
        f"${expense.get('amount', 0.0)} ({expense.get('category', 'N/A')}) has been {decision}.\n\n"
        f"Reason: {reason}\n"
        f"Risk Assessment Details: {risk}\n\n"
        f"Regards,\n"
        f"Corporate Expense Team"
    )
    
    # Store email body in state so frontend can fetch and display it
    ctx.state["notification_email"] = email_body
    node_input["notification_email"] = email_body
    
    # Yield a model response with the formatted email mock
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=f"### 📧 Mock Email Notification Sent\n```\n{email_body}\n```")]
        )
    )
    yield Event(output=node_input)


root_agent = Workflow(
    name="ambient_expense_agent",
    rerun_on_resume=False,
    edges=[
        Edge(from_node=START, to_node=parse_expense_node),
        # All expenses go through the security checkpoint FIRST
        Edge(from_node=parse_expense_node, to_node=security_checkpoint_node),
        # If security event (PII or injection): skip dollar check, go straight to human review
        Edge(from_node=security_checkpoint_node, to_node=human_approval_gate, route="security_escalation"),
        # If clean: proceed to dollar-threshold routing
        Edge(from_node=security_checkpoint_node, to_node=route_expense_node, route="amount_check"),
        Edge(from_node=route_expense_node, to_node=auto_approve_node, route="auto_approve"),
        Edge(from_node=route_expense_node, to_node=risk_review_node, route="risk_review"),
        Edge(from_node=risk_review_node, to_node=human_approval_gate),
        Edge(from_node=human_approval_gate, to_node=outcome_node),
        Edge(from_node=auto_approve_node, to_node=outcome_node),
        Edge(from_node=outcome_node, to_node=notification_node)
    ]
)


# App wrapping the workflow root agent
app = App(
    name="expense_agent",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True)
)
