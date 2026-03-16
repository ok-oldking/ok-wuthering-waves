---
description: Solve a GitHub issue by ID
---

1. Fetch the issue details using the `github_issue_solver` skill.
   - Use `python .agent/skills/github_issue_solver/scripts/github_api.py get <issue_id>`.
2. Analyze the issue and the codebase.
3. Present the proposed solution or reply to the user.
4. **MANDATORY**: Wait for user approval before proceeding.
5. If approved:
   - Apply fixes (if any).
   - Commit changes with "Fixes #<issue_id>".
   - Post a comment to the GitHub issue.
   - Close the issue.
6. If not approved, stop.
