import sqlite3
import os
import json
import logging
from datetime import datetime
from expense_agent.agent import init_db

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
        "SELECT id, amount, submitter, category, description, date, status, original_amount, original_currency FROM expenses WHERE submitter = ? ORDER BY id DESC",
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
        "SELECT id, amount, submitter, category, description, date, status, original_amount, original_currency FROM expenses ORDER BY id DESC"
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
        "INSERT INTO expenses (amount, submitter, category, description, date, status, original_amount, original_currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
          expense.get("amount", 0.0),
          expense.get("submitter", ""),
          expense.get("category", ""),
          expense.get("description", ""),
          expense.get("date", ""),
          status,
          expense.get("original_amount"),
          expense.get("original_currency")
        )
      )
      conn.commit()
  except Exception as e:
    # Bug #18: use structured logging instead of print() so errors appear in server logs
    logging.error(f"Error saving expense: {e}")


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
    # Bug #18: use structured logging instead of print()
    logging.error(f"Error saving pending approval: {e}")


def get_pending_count() -> int:
  """Return count of pending approvals using COUNT(*) — avoids full table scan (Bug #14)."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      cur = conn.cursor()
      cur.execute("SELECT COUNT(*) FROM pending_approvals")
      return cur.fetchone()[0]
  except Exception:
    return 0


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


def get_employee_inbox(email: str) -> list[dict]:
  """Return all inbox messages for the given employee email."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.row_factory = sqlite3.Row
      cur = conn.cursor()
      cur.execute(
        "SELECT id, date, subject, body, is_read FROM inbox WHERE employee_email = ? ORDER BY id DESC",
        (email,),
      )
      return [dict(r) for r in cur.fetchall()]
  except Exception as e:
    logging.error(f"Error fetching inbox: {e}")
    return []

def mark_inbox_read(email: str):
  """Mark all messages for a given employee as read."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.execute(
        "UPDATE inbox SET is_read = 1 WHERE employee_email = ?",
        (email,)
      )
      conn.commit()
  except Exception as e:
    logging.error(f"Error marking inbox as read: {e}")

def save_inbox_message(employee_email: str, date: str, subject: str, body: str):
  """Save a notification email to the employee's inbox."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.execute(
        "INSERT INTO inbox (employee_email, date, subject, body, is_read) VALUES (?, ?, ?, ?, 0)",
        (employee_email, date, subject, body)
      )
      conn.commit()
  except Exception as e:
    logging.error(f"Error saving inbox message: {e}")
