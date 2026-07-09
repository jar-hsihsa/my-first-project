---
name: clear-db-entries
description: Clears out all the database entries of employee and admin without altering any functionality.
---
# Clear DB Entries Skill
Use this skill when the user requests to clear out database entries for the expense application (e.g., clearing the SQLite database where expenses and pending approvals are stored).

## Instructions
1. First, **CRITICAL REQUIREMENT**: You MUST NOT proceed with clearing the database immediately. You must stop and explicitly ask the user for confirmation using a specific phrase, for example: *"Are you absolutely sure you want to permanently delete all database entries? Please reply with 'CONFIRM CLEAR DB' to proceed."*
2. ONLY after the user has explicitly confirmed with the requested phrase, locate the database file. In the extended-expense-agent project, the DB is typically located at `/Users/ashishraj/Documents/my-first-project/extended-expense-agent/expense_agent/expenses.db`.
3. Connect to the SQLite database.
4. Execute SQL `DELETE` commands to clear the relevant tables. The tables usually include `expenses` and `pending_approvals`.
4. Run the following python snippet to clear it safely:
```python
import sqlite3
db_path = "/Users/ashishraj/Documents/my-first-project/extended-expense-agent/expense_agent/expenses.db"
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses")
    cursor.execute("DELETE FROM pending_approvals")
    conn.commit()
print("Database cleared successfully!")
```
5. Confirm to the user that the database has been completely cleared. Do not change any schema or application functionality.
