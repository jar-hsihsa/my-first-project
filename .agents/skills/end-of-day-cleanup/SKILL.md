---
name: end-of-day-cleanup
description: Orchestrates both closing the servers and clearing the database when the user is completely done working for the day.
---
# End of Day Cleanup Skill
Use this skill when the user states they are finished with their work, calling it a day, or specifically asks for a full reset of servers and test data.

## Instructions
1. First, cleanly terminate all Streamlit and ngrok processes by running the following command to force-kill everything and its ports:
   ```bash
   pkill -9 -f streamlit; pkill -9 -f ngrok; pkill -9 -f "npm exec ngrok"; pkill -9 -f "uv run streamlit"; lsof -ti:8501 | xargs kill -9 2>/dev/null; lsof -ti:4040 | xargs kill -9 2>/dev/null
   ```
2. Next, invoke the instructions from the `clear-db-entries` skill to wipe the database. **Remember to still ask for explicit user confirmation** as dictated by the `clear-db-entries` skill.
3. Once both are complete, confirm to the user: `Both servers are now closed, and DB entries are deleted. Start with fresh entries tomorrow.`
