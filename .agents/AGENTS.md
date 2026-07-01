# Antigravity IDE System Directive & Guardrails

You are an agent operating inside the Antigravity IDE environment. You are strictly forbidden from writing code, modifying files, executing console/terminal build steps, or generating Artifacts without explicit, multi-stage human approval.

## 🚫 Browser Agent Guardrail (Strict Tool Lockdown)
- You are strictly prohibited from launching the built-in browser agent (`browser_subagent`), executing background web crawls, or utilizing the browser-in-the-loop screenshot feature unless the user explicitly types: *"Start the browser agent"*.
- If you believe a task requires external web research, API documentation lookups, or visual browser verification, you must pause your thought cycle and ask for permission.
- **Approval Request Format**: *"I need to use the browser agent to look up [X]. Do you grant explicit approval to start it?"*

## 🌿 Mandatory Branching Protocol
- For ANY new business requirement, new task, or logic modification, you must strictly follow the naming convention and approval process outlined in the `issue-resolution-workflow` skill to branch off `ashish`.
- Always report back to the user with the branch name and take explicit approval before continuing.
- You must switch to this task branch BEFORE compiling your pre-execution impact report.

## 📅 Monthly Sync & Merge Protocol (Day 1 of Each Month)
- On the 1st day of every month, you must proactively post a specialized notice in the chat reminding the user to sync all accumulated commits into the `develop` branch from the `ashish` branch.

## 📋 Non-Technical Pre-Execution Impact Report
When presenting updates or changes, you must communicate in simple, universal language. Do not include lots of code snippets, programming file structures, technical parameters, or architectural jargon. Focus purely on user experience, business logic rules, and human workflow.

For EVERY single change, you must pause your planning loops and output this precise layout:

### 🌿 Active Branch
- `[Insert the name of the separate branch you created for this task]`

### 🔄 Proposed Workflow Change
- **The Current Flow**: How the system behaves right now in plain English.
- **The New Flow**: Step-by-step, how the system or user journey will change after this execution.

### 💼 Business Logic Impact
- **What Changes**: The exact business rule, calculation, or policy being modified.
- **Why It Matters**: The direct impact of this change on the user or the business goals.
- **Side Effects**: Any ripple effects this might cause in other parts of the business process.

### 🛑 Request for Approval
*"Please review this operational change on the task branch. Reply with my consent to proceed, or let me know what to adjust."*

- You MUST pause execution and wait for the user's consent string inside the chat surface before editing files or generating final code artifacts.
# Coding Agent Guide

## Project Architecture
This project is an AI agent with a **Streamlit** frontend (`frontend/`), an **SQLite** database (`expenses.db`), and uses **ngrok** to expose the local server.

## Prerequisites

Install the CLI (one-time):
```bash
uv tool install google-agents-cli
```

---

## Development Phases

### Phase 1: Sync & Understand Requirements
**CRITICAL FIRST STEP**: Before reading requirements or writing any code, you must check if the local repository is in sync with the remote repository (e.g., by comparing local to origin). If it is not in sync, you MUST inform the user and ask for explicit approval to sync it (e.g., using the `git-sync` skill) before proceeding.
Once synced, understand the project's requirements, constraints, and success criteria.

### Phase 2: Build and Implement
Implement agent logic in `expense_agent/` and `frontend/`. Use `agents-cli playground` for interactive testing or run the Streamlit app. Iterate based on user feedback.

### Phase 3: Local Testing
**Requires explicit human approval.** Before running any tests, you must tell the user that you are ready to test and explicitly ask for permission. Only after the user approves can you run `uv run pytest tests/unit tests/integration`. Fix issues until all tests pass.

---

## Operational Guidelines for Coding Agents

- **Custom Skills**: Before performing a code review, syncing git, or doing end-of-day cleanups, ALWAYS consult the custom skills located in the `.agents/skills/` or `~/.gemini/config/skills/` directories.
- **Database Safety**: Never modify the schema of `expenses.db` or delete the database file without explicit user permission.
- **Code preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values (e.g., `model`), comments, and formatting.
- **NEVER change the model** unless explicitly asked.
- **Model 404 errors**: Fix `GOOGLE_CLOUD_LOCATION` (e.g., `global` instead of `us-east1`), not the model name.
- **ADK tool imports**: Import the tool instance, not the module: `from google.adk.tools.load_web_page import load_web_page`
- **Run Python with `uv`**: `uv run python script.py`. Run `agents-cli install` first.
- **Stop on repeated errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
- **Git Commits & Pushes**: Never execute `git commit` or `git push` without explicitly asking the user for permission first. You must propose the exact commit message to the user and wait for their approval before proceeding. **Immediately after a successful local commit, you MUST proactively ask the user for permission to push the changes to the remote repository.**
