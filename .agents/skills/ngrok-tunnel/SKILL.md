---
name: ngrok-tunnel
description: Start an ngrok tunnel to expose the Streamlit application running on port 8501.
---

# `ngrok-tunnel` Skill

Whenever the user asks to start an ngrok tunnel or get the ngrok URL for the application, use this skill. 

### Instructions

1. **Start ngrok in the background**:
   Use `npx --yes ngrok` to start the tunnel on port 8501, as `brew` may not be configured properly.
   Run the following command using `WaitMsBeforeAsync` set to a few seconds so it detaches:
   ```bash
   nohup npx --yes ngrok http 8501 > /dev/null 2>&1 &
   ```

2. **Retrieve the Public URL**:
   Wait a few seconds for the tunnel to initialize, then query the local ngrok API to get the public URL:
   ```bash
   curl -s http://127.0.0.1:4040/api/tunnels
   ```
   Extract the `public_url` from the JSON response and provide it to the user.

3. **Authentication**:
   The ngrok auth token (`3FOuL1cC4AFQ11H0ksliqOvmoAR_67fyM2Pc7UUt5SeCBAa9X`) is already saved in the `.env` file and the `ngrok.yml` configuration on this machine. You do not need to ask the user for the token again or authenticate before starting the tunnel.
