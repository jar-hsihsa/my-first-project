import sqlite3
import uuid as _uuid
import logging
import hashlib
from frontend.database import _db_path

def create_ui_session(email: str, role: str, hours: int = 8) -> str:
  """Bug #17: Create an opaque, time-limited session token in the DB.
  
  Returns a random UUID string. The URL stores only this token — never the
  credential-derived hash — so the URL cannot be used to derive passwords.
  Token expires after `hours` hours (default 8h, a standard work day).
  """
  import datetime
  token = str(_uuid.uuid4())
  now = datetime.datetime.utcnow()
  expires = now + datetime.timedelta(hours=hours)
  try:
    with sqlite3.connect(_db_path()) as conn:
      # Clean up expired sessions for this user before inserting
      conn.execute(
        "DELETE FROM ui_sessions WHERE email = ? OR expires_at < ?",
        (email, now.isoformat())
      )
      conn.execute(
        "INSERT INTO ui_sessions (session_token, email, role, expires_at) VALUES (?, ?, ?, ?)",
        (token, email, role, expires.isoformat())
      )
      conn.commit()
  except Exception as e:
    logging.error(f"create_ui_session error: {e}")
  return token


def verify_ui_session(token: str) -> tuple[str, str] | None:
  """Bug #17: Verify an opaque session token. Returns (email, role) or None if invalid/expired."""
  import datetime
  try:
    now = datetime.datetime.utcnow().isoformat()
    with sqlite3.connect(_db_path()) as conn:
      cur = conn.cursor()
      cur.execute(
        "SELECT email, role FROM ui_sessions WHERE session_token = ? AND expires_at > ?",
        (token, now)
      )
      row = cur.fetchone()
      if row:
        return row[0], row[1]  # (email, role)
  except Exception as e:
    logging.error(f"verify_ui_session error: {e}")
  return None


def delete_ui_session(token: str) -> None:
  """Bug #17: Delete a session token on logout."""
  try:
    with sqlite3.connect(_db_path()) as conn:
      conn.execute("DELETE FROM ui_sessions WHERE session_token = ?", (token,))
      conn.commit()
  except Exception as e:
    logging.error(f"delete_ui_session error: {e}")


def verify_credentials(email: str, password: str) -> bool:
  """Verify user credentials against SQLite database."""
  try:
    hashed_pwd = hashlib.sha256(password.encode("utf-8")).hexdigest()  # Bug #10: hashlib now at module level
    with sqlite3.connect(_db_path()) as conn:
      cur = conn.cursor()
      cur.execute(
        "SELECT role FROM users WHERE email = ? AND password_hash = ?",
        (email.strip(), hashed_pwd),
      )
      row = cur.fetchone()
      return row is not None
  except Exception as e:
    # Bug #4: Log the real error so DB/infra issues are not silently swallowed
    logging.exception(f"verify_credentials error for {email}: {e}")
    return False


