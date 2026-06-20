import time
import os
import sys

# Set NO_GCE_CHECK to disable GCE metadata server check
os.environ["NO_GCE_CHECK"] = "True"
os.environ["GCE_METADATA_TIMEOUT"] = "1"

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("1. Loading dotenv...", flush=True)
from dotenv import load_dotenv
load_dotenv()

print("2. Importing os, logging, etc...", flush=True)
import logging
from typing import Any
from unittest.mock import MagicMock

print("3. Importing google.auth...", flush=True)
import google.auth
import google.auth.exceptions

print("4. Mocking google.auth.default...", flush=True)
google.auth.default = MagicMock(return_value=(MagicMock(), "dummy-gcp-project"))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "dummy-gcp-project")

print("5. Mocking resource_manager_utils...", flush=True)
try:
    from google.cloud.aiplatform.utils import resource_manager_utils
    resource_manager_utils.get_project_id = lambda *args, **kwargs: "dummy-gcp-project"
except ImportError:
    print("No google.cloud.aiplatform.utils found")

print("6. Importing vertexai...", flush=True)
import vertexai

print("7. Importing google.adk.artifacts...", flush=True)
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService

print("8. Importing google.cloud.logging...", flush=True)
from google.cloud import logging as google_cloud_logging

print("9. Importing AdkApp...", flush=True)
from vertexai.agent_engines.templates.adk import AdkApp

print("10. Importing expense_agent.agent...", flush=True)
from expense_agent.agent import app as adk_app

print("11. Importing app_utils...", flush=True)
from expense_agent.app_utils.telemetry import setup_telemetry
from expense_agent.app_utils.typing import Feedback

print("All done!", flush=True)
