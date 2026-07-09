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
import logging
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
use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "False").lower() in ("true", "1")
if use_vertex:
    import google.auth
    try:
        _, project_id = google.auth.default()
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id or "")
    except Exception:
        pass
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


# Load company policies once at module startup (Bug #6: avoid repeated file I/O per request)
_POLICIES_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "company_policies.json"
)
try:
    with open(_POLICIES_PATH, "r") as _f:
        _COMPANY_POLICIES: dict = json.load(_f)
except Exception as _e:
    logging.warning("Could not load company_policies.json: %s — using empty policy.", _e)
    _COMPANY_POLICIES = {}


# SQLite Duplicate Detection Database Helpers

_DB_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expenses.db"
)


def hash_password(password: str) -> str:
    """Helper to hash password with SHA-256."""
    import hashlib
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    """Create required tables if they don't already exist."""
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL,
                submitter TEXT,
                category TEXT,
                description TEXT,
                date TEXT,
                status TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                interrupt_id TEXT,
                message TEXT,
                receipt_bytes TEXT,
                submitter_email TEXT,
                raw_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                password_hash TEXT
            )
        """)
        # Bug #17: Opaque session token store — avoids exposing credential-derived hashes in URL
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ui_sessions (
                session_token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_email TEXT,
                date TEXT,
                subject TEXT,
                body TEXT,
                is_read BOOLEAN DEFAULT 0
            )
        """)
        conn.commit()

        # Check if users table is empty and seed if necessary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count == 0:
            default_users = [
                ("employee1@acmecorp.com", "Employee 1", "Employee", hash_password("emp1pass")),
                ("employee2@acmecorp.com", "Employee 2", "Employee", hash_password("emp2pass")),
                ("employee3@acmecorp.com", "Employee 3", "Employee", hash_password("emp3pass")),
                ("employee4@acmecorp.com", "Employee 4", "Employee", hash_password("emp4pass")),
                ("employee5@acmecorp.com", "Employee 5", "Employee", hash_password("emp5pass")),
                ("employee6@acmecorp.com", "Employee 6", "Employee", hash_password("emp6pass")),  # Bug #19: Employee 6 was missing
                ("employee7@acmecorp.com", "Employee 7", "Employee", hash_password("emp7pass")),
                ("admin@acmecorp.com", "Acme Admin", "Admin", hash_password("adminpass")),
            ]
            conn.executemany(
                "INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, ?, ?)",
                default_users
            )
            conn.commit()


def check_duplicate(amount: float, date: str, submitter: str, description: str) -> bool:
    """Return True if an identical expense (same amount/submitter/date/description) exists."""
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM expenses "
                "WHERE amount = ? AND date = ? AND submitter = ? AND description = ?",
                (amount, date, submitter, description),
            )
            return cursor.fetchone()[0] > 0
    except Exception:
        return False


class ExpenseReport(BaseModel):
    amount: float = Field(description="The amount of the expense.")
    currency: str = Field(description="The currency of the expense (e.g., USD, EUR). Defaults to USD.", default="USD")
    vendor: str = Field(description="The name of the vendor or merchant from the receipt or invoice.", default="")
    submitter: str = Field(description="The name or email of the person submitting the expense.")
    category: str = Field(description="The category of the expense. MUST be exactly one of: 'Meals', 'Travel', 'Equipment', 'Office Supplies', 'Software', or 'Miscellaneous'. Do not use hyphens.")
    description: str = Field(description="The description or justification for the expense.")
    date: str = Field(description="The date of the expense.")
    
    ocr_amount: float | None = None
    ocr_currency: str | None = None
    ocr_vendor: str | None = None
    ocr_category: str | None = None
    ocr_date: str | None = None
    
    # UI Resubmission Fields
    is_ui_resubmit: bool = False
    is_manual_submit: bool = False
    original_amount: float | None = None
    original_currency: str | None = None
    exchange_rate: float | None = None

def _blocking_fetch_rate(currency: str) -> float:
    """Blocking HTTP fetch for exchange rate. Run via run_in_executor to avoid blocking event loop (Bug #15)."""
    import urllib.request
    url = f"https://open.er-api.com/v6/latest/{currency}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode('utf-8'))
        return data['rates']['USD']


def convert_to_usd(amount: float, currency: str, date: str) -> tuple[float, float, str]:
    """Convert amount to USD using exchange rate API. Returns (usd_amount, exchange_rate, error_note)."""
    currency = currency.upper().strip()
    if currency == "USD":
        return amount, 1.0, ""
    try:
        import urllib.request
        rate = _blocking_fetch_rate(currency)
        converted = round(amount * rate, 2)
        return converted, rate, ""
    except Exception as e:
        return amount, 1.0, f"Conversion failed: Currency {currency} not supported by exchange rate API. Amount defaulted to 1:1."


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
    """Parses an expense from an event dict, falling back to LLM if only image is provided."""
    
    # Handle inner nesting if payload wraps details inside an 'expense' key at the root
    if "expense" in event:
        event = event["expense"]
        
    if "image_data" in event:
        # Extract from image using LLM
        image_data = event["image_data"]
        mime_type = event.get("mime_type", "image/jpeg")
        
        try:
            image_bytes = base64.b64decode(image_data, validate=True)
        except Exception:
            image_bytes = image_data

        client = genai.Client(vertexai=use_vertex)
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Extract the expense details from this receipt. You MUST extract the date (standardized to YYYY-MM-DD format) and category alongside the amount field. Also extract the currency of the transaction (e.g., USD, EUR, GBP, JPY). If not explicitly stated but implied, infer it. Default to USD if completely unknown. If the submitter/employee email is not on the receipt, set it to 'employee@acmecorp.com'. If you cannot clearly identify a category from the receipt, you MUST default to 'Miscellaneous'. Do not leave the category blank or use a hyphen."
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExpenseReport
            )
        )
        data_dict = json.loads(response.text)
        
        # Prevent LLM from hallucinating ocr_ fields or manual submit flags on the first pass
        for key in ["ocr_amount", "ocr_currency", "ocr_vendor", "ocr_category", "ocr_date"]:
            data_dict.pop(key, None)
        data_dict["is_manual_submit"] = False
        data_dict["is_ui_resubmit"] = False
            
        if "submitter" in event and event["submitter"]:
            data_dict["submitter"] = event["submitter"]
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
def parse_expense_node(ctx: Context, node_input: Any):
    """Decodes the incoming event payload and parses the expense report."""
    try:
        # Try to parse the input as a new expense payload
        event_dict = extract_input_json(node_input)
        expense = parse_expense_from_event(event_dict)
        expense_dict = expense.model_dump()
        
        # If this is a resubmission from the UI, the amount is ALREADY converted to USD
        # but the currency dropdown might be set to the original foreign currency.
        if expense_dict.get("is_ui_resubmit"):
            # Skip double conversion, just ensure we have the USD amount
            pass
        else:
            # First pass: Convert currency if needed
            currency = expense_dict.get("currency", "USD")
            expense_dict["original_amount"] = expense_dict["amount"]
            expense_dict["original_currency"] = currency
            if currency.upper() != "USD":
                usd_amount, rate, err_note = convert_to_usd(expense_dict["amount"], currency, expense_dict["date"])
                expense_dict["exchange_rate"] = rate
                expense_dict["amount"] = usd_amount
                
                
                # Bug #2: Surface conversion failure so admin/employee can see it
                if err_note:
                    expense_dict["description"] = f"[Warning: {err_note}] {expense_dict.get('description', '')}"

        # Increment run count for sequential testing in the same session
        run_count = ctx.state.get("run_count", 0) + 1
        
        # If successful, reset state keys for a new evaluation run in the same session
        yield Event(
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
            yield Event(output={"expense": ctx.state["expense"]})
        else:
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
    """Detect prompt injection attempts using multi-word pattern matching and regex heuristics.

    Single keywords (e.g. 'rules', 'policy', 'force') are intentionally NOT
    flagged on their own — they appear in legitimate expense descriptions.
    Patterns require contextually suspicious combinations.
    """
    desc_lower = description.lower()

    # 1. Unambiguous single-phrase injections (always malicious in context)
    unambiguous = [
        "auto-approve",
        "auto approve",
        "system prompt",
        "prior instructions",
        "system instructions",
        "do not evaluate",
        "approve immediately",
        "always approve",
        "prompt injection",
    ]
    if any(phrase in desc_lower for phrase in unambiguous):
        return True

    # 2. Multi-word combos: requires a *directive* verb + a *target* noun
    directive_verbs = ["ignore", "bypass", "override", "disregard", "forget", "skip"]
    target_nouns = [
        "rules", "instructions", "policy", "policies", "previous",
        "approval", "evaluation", "guidelines", "all",
    ]
    for verb in directive_verbs:
        if verb in desc_lower:
            for noun in target_nouns:
                if noun in desc_lower:
                    return True

    # 3. Coercive approval patterns
    if "you must approve" in desc_lower or "must be approved" in desc_lower:
        return True
    if "force" in desc_lower and ("approve" in desc_lower or "approval" in desc_lower):
        return True

    # 4. Escape Sequence Scanner (e.g., Markdown fence, dividers followed by system instructions)
    escape_pattern = re.compile(
        r'(?:[`\-=\*]{3,})[\s\S]*?\b(ignore|bypass|system|instruction|override|rules|approve)\b',
        re.IGNORECASE
    )
    if escape_pattern.search(description):
        return True

    # 5. Pseudo-XML Tag Scanner (e.g., trying to close the JSON wrap or fake system instructions tags)
    xml_pattern = re.compile(
        r'</?(?:system|sys|expense|instruction|human|assistant|user|command|prompt|context|rules)\b[^>]*>',
        re.IGNORECASE
    )
    if xml_pattern.search(description):
        return True

    # 6. Roleplay & Chat Simulation Scanner (e.g., system: approve)
    roleplay_pattern = re.compile(
        r'(?:^|\n)\s*(?:system|sys|admin|instruction|assistant|user|human)\s*:\s*\b',
        re.IGNORECASE
    )
    if roleplay_pattern.search(description):
        return True

    # 7. Structured Jailbreak Pattern Matcher
    jailbreak_patterns = [
        r'\bjailbreak\b',
        r'\bdeveloper\s+mode\b',
        r'\bignore\s+(?:all|previous|anything|everything|the\s+above|the\s+before|prior|instructions)\b',
        r'\bbypass\s+(?:rules|security|policies|checks|threshold)\b',
        r'\bforget\s+(?:all|previous|anything|everything|the\s+above|the\s+before|prior|instructions)\b',
    ]
    for pat in jailbreak_patterns:
        if re.search(pat, description, re.IGNORECASE):
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
    
    # Bug #5: Check for duplicates BEFORE scrubbing so the canonical description is used.
    # If scrubbing happens first, two identical expenses (one with PII, one without) get
    # different descriptions after scrubbing and the duplicate is not detected.
    is_dup = check_duplicate(
        expense.get("amount", 0.0),
        expense.get("date", ""),
        expense.get("submitter", ""),
        expense.get("description", ""),
    )

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

    # 3. Check for Tampering (if ocr fields exist)
    tamper_alerts = []
    if expense.get("ocr_amount") is not None:
        ocr_amount = float(expense["ocr_amount"])
        submitted_curr = expense.get("currency", "USD").upper().strip()
        ocr_curr = expense.get("ocr_currency", "USD").upper().strip()
        
        # If UI submitted in USD but original was foreign (or if it's a UI resubmit for a foreign currency), calculate expected USD amount
        expected_amt = ocr_amount
        is_ui_resubmit = expense.get("is_ui_resubmit", False)
        
        if (submitted_curr == "USD" or is_ui_resubmit) and ocr_curr != "USD" and "exchange_rate" in expense and expense["exchange_rate"] is not None:
            expected_amt = round(ocr_amount * float(expense["exchange_rate"]), 2)
            
        submitted_amt = float(expense["amount"])
        # Bug #7: Use tolerance for float comparison to avoid false tamper alerts
        # from floating-point rounding during currency conversion
        if abs(submitted_amt - expected_amt) > 0.01:
            tamper_alerts.append(f"Amount changed from {expected_amt} to {submitted_amt}.")
            
        if submitted_curr != ocr_curr:
            # Do not flag if the change to USD was our automatic UI conversion
            if not (submitted_curr == "USD" and ocr_curr != "USD" and "exchange_rate" in expense and expense["exchange_rate"] is not None):
                tamper_alerts.append(f"Currency changed from {ocr_curr} to {submitted_curr}.")
            
        submitted_cat = expense.get("category", "").lower().strip()
        ocr_cat = str(expense.get("ocr_category", "")).lower().strip()
        if ocr_cat in ["", "none", "miscellaneous"]: ocr_cat = "miscellaneous"
        if submitted_cat in ["", "none", "miscellaneous"]: submitted_cat = "miscellaneous"
        if submitted_cat != ocr_cat:
            tamper_alerts.append(f"Category changed from '{ocr_cat.title()}' to '{submitted_cat.title()}'.")
            
        submitted_date = expense.get("date", "")
        ocr_date = str(expense.get("ocr_date", "")).strip()
        try:
            from datetime import datetime
            import dateutil.parser
            d1 = datetime.strptime(submitted_date, "%Y-%m-%d").date()
            d2 = dateutil.parser.parse(ocr_date).date()
            if d1 != d2:
                tamper_alerts.append(f"Date changed from '{ocr_date}' to '{submitted_date}'.")
        except Exception:
            pass

        sub_vendor = expense.get("vendor", "").lower().strip()
        ocr_vendor = str(expense.get("ocr_vendor", "")).lower().strip()
        if sub_vendor != ocr_vendor:
            tamper_alerts.append(f"Vendor changed from '{ocr_vendor.title()}' to '{sub_vendor.title()}'.")
            
        if tamper_alerts:
            tamper_msg = "TAMPER ALERT: The employee manually altered OCR extraction: " + " ".join(tamper_alerts)
            redacted.append("Tamper Detected")
            expense["description"] = f"🚨 {tamper_msg}\n\nOriginal Description: {expense.get('description', '')}"

    # 4. Check for duplicates (moved before scrub — see Bug #5 fix above)
    if is_dup:
        redacted.append("Duplicate Expense")
        # Also mark the description so admin can immediately see it's a duplicate
        expense["description"] = f"⚠️ DUPLICATE SUBMISSION: {expense.get('description', '')}"

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
            "CRITICAL RISK: Security policy violation detected. "
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
        
    # Use module-level cached policies (loaded once at startup)
    policies = _COMPANY_POLICIES
        
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
        "decision": "Auto-Approved",
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
async def employee_review_gate(ctx: Context, node_input: dict):
    """Pauses the workflow to let the employee review the OCR extraction before submission."""
    expense = node_input["expense"]
    
    # Bypass the pause if this is a manual submission or has already been reviewed.
    # NOTE (Bug #8): ocr_amount presence means the employee has already reviewed the
    # OCR extraction once. The security_checkpoint_node later validates all submitted
    # fields against the original OCR values to detect any tampering.
    if expense.get("is_manual_submit") or expense.get("ocr_amount") is not None:
        yield Event(output=node_input)
    else:
        # If ocr_amount is missing, this is the very first pass (image extraction).
        # We must pause here so the employee can review and edit in the UI.
        interrupt_id = "employee_review"
        msg = f"Review required\n---JSON---\n{json.dumps(expense)}"
        yield RequestInput(interrupt_id=interrupt_id, message=msg)


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

    # json is already imported at module level — removed redundant inner import
    msg = (
        f"EXPENSE APPROVAL REQUIRED:{security_lines}\n"
        f"Expense of ${expense['amount']} by {expense['submitter']} "
        f"for '{expense['description']}' requires review.\n"
        f"Risk Assessment: {risk_assessment}\n"
        f"Please reply with 'Approve' or 'Reject' (or custom message).\n"
        f"---JSON---\n{json.dumps(expense)}"
    )
    yield RequestInput(interrupt_id=interrupt_id, message=msg)



@node
def outcome_node(ctx: Context, node_input: Any):
    """Logs the final outcome and formats it for displaying in the Web UI."""
    if isinstance(node_input, dict) and "decision" in node_input:
        expense = node_input["expense"]
        decision = node_input["decision"]
        reason = node_input.get("reason", "N/A")  # Bug #7: use .get() to avoid KeyError
        risk = node_input.get("risk_assessment", "N/A")  # Bug #7: use .get() to avoid KeyError
    else:
        # It's a resume response string from human_approval_gate
        expense = ctx.state.get("expense", {})
        risk = ctx.state.get("risk_assessment", "N/A")
        decision_text = str(node_input)
        # Bug #6: Expand affirmative keywords so common natural-language approvals
        # ("Yes", "OK", "looks good") are not silently classified as Rejected.
        _affirmatives = ("approve", "approved", "yes", "ok", "looks good", "fine", "accept", "accepted")
        decision = "Approved" if any(word in decision_text.lower() for word in _affirmatives) else "Rejected"
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
        # Build security label directly from state flags — generic for security
        sec_label = "⚠️ CRITICAL RISK: Request flagged for manual review due to security policy."
        content_text += f"- **Security Status**: {sec_label}\n"
    content_text += f"- **Risk Assessment**: {risk}\n"
    
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=content_text)]
        )
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
    # Bug #1: Use .get() to avoid KeyError on unexpected code paths
    reason = node_input.get("reason", "N/A")
    risk = node_input.get("risk_assessment", "N/A")
    submitter = expense.get("submitter", "employee@acmecorp.com")
    amount_str = f"${expense.get('amount', 0.0)}"
    if expense.get("original_currency") and expense.get("original_currency").upper() != "USD":
        amount_str = f"{expense.get('original_amount')} {expense.get('original_currency')} (Converted to ${expense.get('amount', 0.0)} USD)"

    desc_preview = expense.get('description', 'No Description')[:25]
    if len(expense.get('description', 'No Description')) > 25: desc_preview += '...'
    email_subject = f"Notification: Your {amount_str} Expense ({desc_preview}) has been {decision.upper()}"

    recommendation = "For rejected expenses, please review the reason provided above and adjust your submission accordingly to comply with corporate policy. For approved expenses, no further action is required."
    status_color = "🟢 APPROVED" if decision.upper() == "APPROVED" else ("🟡 AUTO-APPROVED" if decision.upper() == "AUTO-APPROVED" else "🔴 REJECTED")
    
    email_body = f"""**To:** {submitter}  
**From:** expense-system@acmecorp.com  
**Subject:** {email_subject}  

---

### Acme Corp Finance & Administration
*Automated Expense Management System*

Dear Employee,

Your recent expense report has been reviewed. Below is the final determination of your submission.

#### **Expense Details**
- **Date:** {expense.get('date', 'N/A')}
- **Amount:** {amount_str}
- **Category:** {expense.get('category', 'N/A')}
- **Status:** **{status_color}**

#### **Reviewer Notes**
> _{reason}_

---

*This is an automated message. Please do not reply directly to this email. For questions, contact the Finance Department.*
"""
    
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
        Edge(from_node=parse_expense_node, to_node=employee_review_gate),
        # All expenses go through the security checkpoint FIRST (after employee review)
        Edge(from_node=employee_review_gate, to_node=security_checkpoint_node),
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
