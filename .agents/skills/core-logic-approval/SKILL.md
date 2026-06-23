---
name: core-logic-approval
description: Reminds the agent to explicitly ask for user approval before modifying any existing core business or validation logic.
---

# `core-logic-approval` Skill

## 🚨 CRITICAL INSTRUCTION

Whenever a user requests a change that impacts or bypasses **core business logic**, **security checkpoints**, **validation algorithms**, or **compliance mechanisms** (e.g., regex checks for PII, SSNs, credit cards, or authentication rules):

1. **STOP and EXPLAIN** the change you intend to make.
2. **ASK FOR EXPLICIT APPROVAL** from the user before writing any code or modifying the logic.

Even if the change is just for testing or "demo purposes", you must not alter strict compliance or verification algorithms without the user's direct consent. Always default to preserving existing security and core logic unless specifically instructed otherwise.
