import time
import sys

def test_import(module_name):
    t0 = time.time()
    print(f"Importing {module_name}...", end="", flush=True)
    try:
        __import__(module_name)
        print(f" done ({time.time() - t0:.3f}s)", flush=True)
    except Exception as e:
        print(f" failed ({time.time() - t0:.3f}s): {e}", flush=True)

test_import("dotenv")
test_import("google.auth")
test_import("google.auth.exceptions")
test_import("vertexai")
test_import("google.adk")
test_import("google.cloud.logging")
test_import("google.adk.workflow")
test_import("google.adk.apps")
test_import("google.adk.agents.context")
test_import("google.adk.events.event")
test_import("google.adk.events.request_input")
test_import("google.genai")
test_import("google.genai.types")

print("All imports tested.", flush=True)
# Aditya Test Push Access

