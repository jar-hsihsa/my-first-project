import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"API Key starts with: {api_key[:6]}...")

from google import genai

try:
    print("Initializing client with explicit API Key...")
    client = genai.Client(api_key=api_key)
    print("Client initialized. Testing generate_content with gemini-2.5-flash...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello, this is a test prompt."
    )
    print("Success with gemini-2.5-flash! Response:")
    print(response.text)
except Exception as e:
    print(f"Failed with gemini-2.5-flash: {e}")

try:
    print("Testing generate_content with gemini-1.5-flash...")
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Hello, this is a test prompt."
    )
    print("Success with gemini-1.5-flash! Response:")
    print(response.text)
except Exception as e:
    print(f"Failed with gemini-1.5-flash: {e}")

try:
    print("Testing generate_content with gemini-3.1-flash-lite...")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents="Hello, this is a test prompt."
    )
    print("Success with gemini-3.1-flash-lite! Response:")
    print(response.text)
except Exception as e:
    print(f"Failed with gemini-3.1-flash-lite: {e}")
