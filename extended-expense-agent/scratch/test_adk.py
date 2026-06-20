import asyncio
import json
from expense_agent.agent import root_agent
from google.adk.agents.context import Context

async def main():
    data = {
        "amount": 50.0,
        "submitter": "test@example.com",
        "category": "Meals",
        "description": "Lunch with client",
        "date": "2026-06-18"
    }
    
    try:
        print("Testing root_agent.run:")
        async for chunk in root_agent.run(ctx=Context(), node_input=data):
            print("CHUNK:", chunk)
    except Exception as e:
        print("Error root_agent stream:", type(e), e)

if __name__ == "__main__":
    asyncio.run(main())
