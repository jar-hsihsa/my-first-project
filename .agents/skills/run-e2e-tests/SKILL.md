---
name: run-e2e-tests
description: "Run comprehensive end-to-end tests for the application, evaluate agent behavior, and generate a structured audit report while preserving database state."
---

# `run-e2e-tests` Skill

This skill defines the standard operating procedure for testing the application end-to-end. It ensures that testing does not corrupt the local database and that all layers of testing are executed systematically.

## 🚨 CRITICAL RULES
- Do not run tests without explicit user permission.
- Always back up the database before running tests, and always restore it afterward, even if tests fail.

## Workflow Steps

### Step 1: Database Backup
- Backup the SQLite database to prevent corruption from testing data.
- Run: `cp /Users/ashishraj/Documents/my-first-project/extended-expense-agent/expenses.db /Users/ashishraj/Documents/my-first-project/extended-expense-agent/expenses.db.backup`

### Step 2: Run Unit and Integration Tests
- Execute the standard test suite to ensure basic functionality is working.
- Run (from `extended-expense-agent` directory): `uv run pytest tests/unit tests/integration`
- If any test fails, capture the error output for the final report.

### Step 3: Run Agent Evaluation
- Run the agent evaluations using the Google Agents CLI.
- Run (from `extended-expense-agent` directory): `uv run agents-cli eval run --dataset tests/eval/datasets/basic-dataset.json --config tests/eval/eval_config.yaml`
- If the CLI command fails due to arguments, ensure to check `agents-cli eval run --help` and adjust, or note it in the final report.

### Step 4: Database Restoration
- Immediately restore the SQLite database to its pristine state.
- Run: `mv /Users/ashishraj/Documents/my-first-project/extended-expense-agent/expenses.db.backup /Users/ashishraj/Documents/my-first-project/extended-expense-agent/expenses.db`

### Step 5: Generate Test Report Artifact
- Create a non-technical markdown artifact named `test_report.md` summarizing the testing session.
- Format the report using the following structure:
  - **Overall Status**: [Stable / Unstable]
  - **Unit & Integration Results**: Summary of `pytest` output.
  - **E2E/Eval Results**: Summary of `agents-cli` evaluation.
  - **Bugs/Defects Found**: List any issues clearly.
  - **Agent Recommendations**: Recommended fixes or next steps.
