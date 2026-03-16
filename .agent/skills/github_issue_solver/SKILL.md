---
name: github_issue_solver
description: Fetches GitHub issues, proposes solutions, and interacts with the issue (commenting, closing) after user approval.
---

# GitHub Issue Solver Skill

This skill enables the agent to automate the process of solving GitHub issues by fetching issue details, analyzing the codebase, proposing fixes, and interacting with the GitHub API.

## Workflow

When the user asks to solve a GitHub issue (e.g., "Solve issue #123"), follow these steps:

### 1. Fetch Issue Information
- Use the helper script `scripts/github_api.py` to get the issue details.
  ```powershell
  python .agent/skills/github_issue_solver/scripts/github_api.py get <issue_id>
  ```
- Extract the title, body, and labels.

### 2. Analyze and Plan
- Analyze the issue content and the relevant parts of the codebase.
- Determine if it's a bug fix, a feature request, or a general question.
- Identify the language used in the issue (English, Chinese, etc.).
- Prepare a plan:
    - For bugs: Describe the fix and any file changes.
    - For questions: Prepare a comprehensive answer.
- **IMPORTANT**: Do not apply any changes or post any comments yet.

### 3. Seek User Approval
- Present the analysis and the proposed plan to the user.
- Ask for acceptance (e.g., "Should I proceed with this fix and reply to the issue?").
- **WAIT** for the user's response.

### 4. Execution (If Accepted)
If the user accepts the proposal:
- **Apply Changes**: Modify the code as planned.
- **Commit**: Commit the changes with a message like `fix: <summary> (fixes #<issue_id>)`.
- **Reply**: Post a comment to the issue using the helper script. The reply should be in the same language as the issue.
  ```powershell
  python .agent/skills/github_issue_solver/scripts/github_api.py comment <issue_id> "Your comment here"
  ```
- **Close**: Close the issue.
  ```powershell
  python .agent/skills/github_issue_solver/scripts/github_api.py close <issue_id>
  ```

### 5. Termination (If Not Accepted)
If the user does not accept or provides different instructions:
- Do NOT reply to the issue or close it.
- Follow the user's new instructions or stop.

## Requirements
- `requests` library must be installed.
- `GITHUB_TOKEN` or `GH_TOKEN` environment variable must be set for write operations (commenting, closing).
