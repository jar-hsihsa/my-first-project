---
name: issue-resolution-workflow
description: "Workflow for addressing issues: branch from 'ashish', implement fixes iteratively, raise PR, and sync."
---

# `issue-resolution-workflow` Skill

This skill defines the standard operating procedure for handling and resolving GitHub issues. It is triggered when the user wants to raise a new issue or work on an existing issue (bug, enhancement, etc.) that was found during testing.

## 🚨 CRITICAL RULE: User Communication & Approvals

- **Explain Commands**: Since the user may not be familiar with Git commands, you MUST provide a brief, plain-English message explaining exactly what each Git or terminal command does before asking for execution permission or running it.
- **Explicit Approval**: Always wait for explicit user approval before running any branch creation, merging, pushing, or repository synchronization commands.

## Workflow Steps

1. **Issue Creation**:
   - If the user has found an issue during testing but hasn't created it yet, assist the user in raising the issue on GitHub.
   - If the `gh` CLI is not installed, attempt to use the GitHub REST API (if a token/`github-connection` is available), or fallback to providing the user with a formatted title/description to create it manually.

2. **Branch Creation**:
   - **CRITICAL**: Before creating a branch, you MUST verify the issue number and get the user's explicit approval. Do not assume the issue number or create the branch without taking approval first.
   - When asked to work on the issue and after receiving approval, create a new, separate temporary branch off of the `ashish` branch (ensuring the local `ashish` is pulled and in sync with origin).
   - The branch naming convention MUST be: `ashish-issue-<number>-<description>`.
   - Push the branch to the remote repository only after obtaining the user's explicit approval.
   - Example: 
     ```bash
     git checkout ashish
     git pull origin ashish
     git checkout -b ashish-issue-<number>-<description>
     # Push to remote repository (with user approval):
     git push -u origin ashish-issue-<number>-<description>
     ```

3. **Implementation & Iterative Fixes**:
   - Work on the temporary branch to implement the necessary fixes or features.
   - The user will iteratively test the changes.
   - If the user finds more bugs during testing or requests further changes in the same run, user may ask you to **commit all additional fixes to this same temporary branch**. Do not create another new branch.
   - **NOTE**: Use the `git-commit-formatter` skill to structure all commit messages.

4. **Testing and Marking as 'Fixed'**:
   - Once the issue is completely tested by end user, ask user to first label the issue as 'Fixed' in GitHub. 
   - Do not close the issue without user approval. or Do not add 'Closed' label without user approval. Keep the issue in the issue tab only until you are asked to close it.  

5. **Pull Request Creation**:
   - Once the user explicitly states they are satisfied with the fixes, and the issue is marked as 'Fixed' as label, take user approval before raising the Pull Request (PR) from the temporary branch.
   - The PR/changes must always target `ashish` branch only.
   - **CRITICAL NAMING RULE**: GitHub shares the same ID pool for Issues and PRs, meaning it is impossible for a PR to have the exact same number as its corresponding Issue. To ensure easy tracking, you MUST include the issue number directly in the PR Title (e.g., "Fix: <description> (Resolve Issue #<issue_number>)") and ensure the branch is named `ashish-issue-<number>-<description>`.
   - User will not raise the PR, you may give the link only just to land on the PR raised by you.

6. **PR Merger Request Approval and Git Sync**:
   - If everything looks good take approval from user if PR can be closed or merged into `ashish` branch. Once user approves it, go ahead and merge it.
   - After the PR has been approved and merged, you must take the user approval to run the `git-sync` skill to clean up local branches and synchronize the local repository with the remote.
   - If the user approves it, then only run the `git-sync` skill.

7. **Post PR Merger and Git Sync**:
   - After the PR is merged into `ashish` and the sync is complete, add a final comment to the original GitHub issue (e.g., "Resolved by PR #<number>"), remove the 'Fixed' label, add the 'Closed' label, and close the issue.
   - If the `gh` CLI is not installed, use the GitHub REST API via `curl` (if a token is available) or guide the user to close it manually.