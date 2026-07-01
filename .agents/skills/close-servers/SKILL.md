---
name: close-servers
description: Closes or stops the Streamlit and ngrok server processes.
---
# Close Servers Skill
Use this skill when the user specifically asks to stop/close the running Streamlit and/or ngrok servers.

## Instructions
1. **Locate running processes**: Find all running processes related to `streamlit` and `ngrok`:
   ```bash
   ps -eo pid,ppid,command | grep -iE 'streamlit|ngrok' | grep -v grep
   ```
2. **Terminate ALL processes — including child processes and ports**: Run this single command to force-kill everything:
   ```bash
   pkill -9 -f streamlit; pkill -9 -f ngrok; pkill -9 -f "npm exec ngrok"; pkill -9 -f "uv run streamlit"; lsof -ti:8501 | xargs kill -9 2>/dev/null; lsof -ti:4040 | xargs kill -9 2>/dev/null
   ```
   This kills:
   - All `streamlit` processes (including python/venv child processes)
   - All `ngrok` processes (including `npm exec ngrok` wrappers)
   - Any process holding port `8501` (Streamlit) or `4040` (ngrok dashboard)
3. **Verify termination**: Confirm nothing is left running:
   ```bash
   ps -eo pid,ppid,command | grep -iE 'streamlit|ngrok' | grep -v grep; lsof -ti:8501; lsof -ti:4040; echo "All clear"
   ```
   The output should show nothing except "All clear".
4. **Confirm to User**: Report back to the user with a confirmation message exactly like:
   `Both servers are now closed and not running.`
