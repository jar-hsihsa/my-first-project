---
name: github-connection
description: Use the provided Personal Access Token (PAT) for GitHub API interactions when the gh CLI is unavailable.
---

# `github-connection` Skill

Whenever you need to interact with GitHub (such as creating issues, checking PR status, etc.) and the `gh` CLI is not installed or authenticated, you MUST use the GitHub REST API via `curl` along with the following Personal Access Token (PAT):

**PAT:** `YOUR_GITHUB_PAT`

### Examples

**Create an Issue:**
```bash
curl -s -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: Bearer YOUR_GITHUB_PAT" \
  https://api.github.com/repos/jar-hsihsa/my-first-project/issues \
  -d '{"title": "Issue Title", "body": "Issue Description"}'
```

**Check PR Status:**
```bash
curl -s \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: Bearer YOUR_GITHUB_PAT" \
  https://api.github.com/repos/jar-hsihsa/my-first-project/pulls
```

**Important:** Do not forget to use this token instead of asking the user to manually perform GitHub actions if the CLI tool is unavailable!
