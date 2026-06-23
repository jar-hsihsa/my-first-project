---
name: git-sync
description: Syncs the local repository with the remote, securely pruning deleted branches.
---

# `git-sync` Skill

This skill synchronizes the user's local repository with the remote repository. It performs a fetch to prune any branches that were deleted on the remote (such as after a Pull Request is merged), deletes those "gone" branches locally, and pulls the latest changes.

## 🚨 CRITICAL RULE: Ask Before Firing Commands

**You MUST use the `run_command` tool to propose the sync commands, and STOP to wait for the user to click "Approve" in the UI.**
Do not attempt to bypass user approval or run the commands silently. The user explicitly requested to give final approval before modifying local branches.

## Instructions

When the user asks to "sync the repo" or run the `git-sync` skill, follow these exact steps:

1. Use the helper script located at `./scripts/sync.sh` within this skill's directory, OR manually propose the exact commands from the script.
2. The commands to be executed are:
   ```bash
   git fetch --prune
   # Delete local branches that have been merged into the current branch
   git branch --merged | grep -vE '^\*|main|master|develop|ashish' | xargs -r git branch -d
   # Delete remote branches that have been merged into the current branch
   for b in $(git branch -r --merged | grep -vE '^\*|main|master|develop|ashish|HEAD'); do
     git push origin --delete ${b#origin/} || true
   done
   # Prune any local branches whose remotes were just deleted
   git fetch --prune
   git branch -vv | grep ': gone]' | awk '{print $1}' | xargs -r git branch -D
   git pull origin $(git branch --show-current)
   ```
3. Use the `run_command` tool with the above commands (or by invoking the script).
4. The system will automatically pause and ask the user to approve the command. **DO NOT take any further action until the user approves.**
5. Once the command completes successfully, inform the user that their local repository is now in 100% parity with the remote.
