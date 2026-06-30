# Copyright (c) 2026 MyCompany LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from expense_agent.agent import employee_review_gate

class DummyContext:
    def __init__(self):
        self.state = {}

@pytest.mark.asyncio
async def test_employee_review_gate_manual_submit() -> None:
    ctx = DummyContext()
    # Test that a manual submission bypasses the employee review gate pause
    node_input = {
        "expense": {
            "amount": 100.0,
            "category": "Meals",
            "description": "Lunch",
            "is_manual_submit": True,
        }
    }
    
    events = []
    async for event in employee_review_gate._func(ctx, node_input):
        events.append(event)
        
    assert len(events) == 1
    assert isinstance(events[0], Event)
    assert events[0].output == node_input


@pytest.mark.asyncio
async def test_employee_review_gate_ocr_needs_review() -> None:
    ctx = DummyContext()
    # Test that an OCR submission without ocr_amount triggers a review pause
    node_input = {
        "expense": {
            "amount": 100.0,
            "category": "Meals",
            "description": "Lunch",
            "is_manual_submit": False,
            "ocr_amount": None,
        }
    }
    
    events = []
    async for event in employee_review_gate._func(ctx, node_input):
        events.append(event)
        
    assert len(events) == 1
    assert isinstance(events[0], RequestInput)
    assert events[0].interrupt_id == "employee_review"
