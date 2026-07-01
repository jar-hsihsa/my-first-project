# End-to-End Requirement Execution Workflow

This document outlines the strict, phase-wise execution flow the AI agent follows when handling a new requirement, including all human approval gates and the configuration files that dictate the agent's behavior.

## Workflow Diagram

```mermaid
flowchart TD
    %% Styling
    classDef rule fill:#ffe6cc,stroke:#d79b00,stroke-width:2px,color:#333;
    classDef skill fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px,color:#333;
    classDef human fill:#d5e8d4,stroke:#82b366,stroke-width:2px,color:#333;
    classDef file fill:#f5f5f5,stroke:#666,stroke-width:1px,stroke-dasharray: 5 5;
    
    Start((New Requirement)) --> P1
    
    subgraph Phase 1: Ingestion and Sync
        P1[Check Git Sync]:::rule
        F1[[.agents/AGENTS.md]]:::file -.-> |Phase 1 Rule| P1
        P1 --> P1_sync{Out of sync?}
        P1_sync -- Yes --> P1_sync_run[Run Git Sync]:::skill
        F2[[global skills/git-sync]]:::file -.-> |Read Skill| P1_sync_run
        P1_sync -- No --> P2
        P1_sync_run --> P2
    end
    
    subgraph Phase 2: Issue and Branching
        P2[Check or Create GitHub Issue]:::skill
        F3[[global skills/issue-resolution]]:::file -.-> |Read Skill| P2
        P2 --> P2_branch[Create Branch off ashish]:::skill
        F3 -.-> |Read Skill| P2_branch
        P2_branch --> H1{Approval: Branch Creation}:::human
        H1 --> P3
    end
    
    subgraph Phase 3: The Safety Pause
        P3[Generate Impact Report]:::rule
        F1 -.-> |Impact Report Rule| P3
        P3 --> H2{Consent: Proceed with coding}:::human
        H2 --> P4
    end
    
    subgraph Phase 4: Implementation
        P4[Write Code]:::rule
        F1 -.-> |Operational Guidelines| P4
        P4 --> P4_browser{Need Web Search?}
        P4_browser -- Yes --> H3{Approval: Browser usage}:::human
        H3 --> P4_web[Browse Web]
        P4_browser -- No --> P5
        P4_web --> P5
    end
    
    subgraph Phase 5: QA and Testing
        P5[Run Tests via pytest]:::rule
        F1 -.-> |Local Testing Rule| P5
        P5 --> H4{Approval: Run tests}:::human
        H4 --> P6
    end
    
    subgraph Phase 6: Committing and PR
        P6[Format Commit Message]:::skill
        F4[[global skills/git-commit-formatter]]:::file -.-> |Read Skill| P6
        P6 --> H5{Approval: Git Commit}:::human
        H5 --> P6_issue[Label Issue Fixed]:::skill
        F3 -.-> |Read Skill| P6_issue
        P6_issue --> P6_pr[Raise PR to ashish]:::skill
        P6_pr --> H6{Approval: Raise PR}:::human
        H6 --> P7
    end
    
    subgraph Phase 7: Senior Review and Cleanup
        P7[Wait for Senior Approved comment]:::skill
        F3 -.-> |Read Skill| P7
        P7 --> P7_merge[Merge to ashish]:::skill
        P7_merge --> P7_sync[Sync Branch and Delete Temp]:::skill
        F2 -.-> |Read Skill| P7_sync
        P7_sync --> P7_close[Close Issue]:::skill
        P7_close --> Finish((Complete))
    end
```

## Phase-by-Phase Breakdown

### Phase 1: Ingestion & Environment Sync
**Trigger:** You type a new feature requirement into the chat.
* 🧠 **File Activated:** `.agents/AGENTS.md` (Phase 1 Rule)
   * **Action**: Before reading your requirement fully, this rule forces a background check (`git fetch` / `git status`) to ensure local code isn't outdated.
* 🧠 **File Activated (If Stale):** `~/.gemini/config/skills/git-sync/SKILL.md`
   * **Action**: If out of sync, stop, inform you, and ask for **Explicit Approval** to run the Git Sync skill to pull the latest changes.

### Phase 2: Issue Creation & Branching
* 🧠 **File Activated:** `.agents/AGENTS.md` (Mandatory Branching Protocol)
   * **Action**: Forbids coding on the main branch and redirects to the Issue Workflow.
* 🧠 **File Activated:** `~/.gemini/config/skills/issue-resolution-workflow/SKILL.md`
   * **Action**: Check GitHub. If no issue exists, assist in creating one via the `gh` CLI.
   * **Action**: Branch off `ashish` using the format `ashish-issue-<number>-<description>`. 
   * 🛑 **APPROVAL GATE**: Explain terminal commands and ask for **Explicit Approval** to create and push the branch.

### Phase 3: The Safety Pause & Impact Report
* 🧠 **File Activated:** `.agents/AGENTS.md` (Pre-Execution Impact Report)
   * **Action**: A hard stop. No code can be written yet. 
   * **Action**: Generate a plain-English report outlining the Current Flow, New Flow, and Business Logic Impact.
   * 🛑 **APPROVAL GATE**: Hard-locked until you type your consent string in the chat panel. 

### Phase 4: Implementation (With Guardrails)
* 🧠 **File Activated:** `.agents/AGENTS.md` (Operational Guidelines & Browser Guardrail)
   * **Action**: Begin writing code. 
   * **Action**: The Browser Guardrail forces a pause for **Explicit Approval** if an external web search is needed. 
   * **Action**: Ensure the `expenses.db` schema is not modified. Iterate on the same branch based on local testing.

### Phase 5: Quality Assurance & Testing
* 🧠 **File Activated (Optional):** `.agents/skills/code-review/SKILL.md`
   * **Action**: If requested, check for SQLite SQL-injection, Streamlit caching issues, and PEP8 standards.
* 🧠 **File Activated:** `.agents/AGENTS.md` (Local Testing Phase Rule)
   * 🛑 **APPROVAL GATE**: State readiness to run tests and wait for **Explicit Approval**.
   * **Action**: Execute `uv run pytest tests/unit tests/integration`.

### Phase 6: Committing & PR
* 🧠 **File Activated:** `~/.gemini/config/skills/git-commit-formatter/SKILL.md`
   * **Action**: Generate a "Conventional Commit" message (e.g., `feat(auth): add login`).
* 🧠 **File Activated:** `.agents/AGENTS.md` (Git Commits Rule)
   * 🛑 **APPROVAL GATE**: Propose the commit message and wait for **Explicit Approval**.
* 🧠 **File Activated:** `~/.gemini/config/skills/issue-resolution-workflow/SKILL.md`
   * **Action**: Update the GitHub issue to have only the 'Fixed' label.
   * 🛑 **APPROVAL GATE**: Ask for permission to raise a Pull Request targeting the `ashish` branch.

### Phase 7: The Senior Review & Cleanup
* 🧠 **File Activated:** `~/.gemini/config/skills/issue-resolution-workflow/SKILL.md`
   * **Action**: Wait for the senior developer to comment "Approved" or "LGTM" on the GitHub PR.
   * **Action**: Merge it into `ashish`. Automatically delete the temporary feature branch.
* 🧠 **File Activated:** `~/.gemini/config/skills/git-sync/SKILL.md`
   * **Action**: Pull the freshly merged `ashish` branch down to the local machine.
   * **Action**: Close the GitHub issue with a "Resolved" comment.
