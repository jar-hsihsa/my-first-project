import base64
import json
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to allow importing expense_agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from expense_agent.agent import parse_expense_from_event

def test():
    try:
        receipt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dummy_receipt.png")
        with open(receipt_path, "rb") as f:
            image_bytes = f.read()
        
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "image_data": base64_image,
            "mime_type": "image/png"
        }
        
        print("Running parse_expense_from_event...")
        result = parse_expense_from_event(payload)
        print("Success! Result:")
        print(result)
    except Exception as e:
        print("Failed with exception:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
