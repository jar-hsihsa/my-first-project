import base64
import json
import os
import re
from html import escape as html_escape
import logging

_FRONTEND_POLICIES = {}
try:
    _pol_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "company_policies.json")
    with open(_pol_path) as _f:
        _FRONTEND_POLICIES = json.load(_f)
except Exception:
    pass


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception:
        return ""


def _esc(value: str) -> str:
  """HTML-escape a string for safe interpolation into unsafe_allow_html markup."""
  return html_escape(str(value)) if value else "—"


def _esc_description(value: str) -> str:
  """HTML-escape a description string, rendering [Original: ...] and [Warning: ...] notes in styled badges."""
  escaped = html_escape(str(value)) if value else "—"
  import re
  pattern = r'\s*\[Original:[^\]]+\]\s*'
  
  pattern_warning = r'(\[Warning:[^\]]+\])'
  def warning_replacer(match):
    note = match.group(1)
    return f'<strong class="conversion-warning-badge">{note}</strong>'
    
  formatted = re.sub(pattern, ' ', escaped).strip()
  formatted = re.sub(pattern_warning, warning_replacer, formatted)
  return formatted


def get_category_threshold(email: str, category: str) -> float:
  """Get the approval threshold for a category and email domain."""
  # Bug #3: Use module-level cached policies instead of re-reading file per call
  # Bug #10: os and json are now at module level, removed inner import
  policies = _FRONTEND_POLICIES

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


