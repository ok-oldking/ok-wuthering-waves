---
name: deploy
description: Commit completed repository changes and create the next annotated version tag. Use when the user asks to deploy, release, publish a version, create a release tag, run `deploy` for a stable release, `deploy beta` for a beta prerelease, or `deploy alpha`/`release alpha` for an alpha prerelease.
---

# Deploy

Use this workflow to turn validated local changes into one commit and one annotated version tag. Do not push unless the user explicitly requests it.

## Variants

- `deploy` or `deploy release`: create a stable tag, such as `v3.3.54`.
- `deploy beta`: create a beta tag, such as `v3.3.55-beta.1`.
- `deploy alpha` or `release alpha`: create an alpha tag, such as `v3.3.55-alpha.1`.

Stable versions increment the patch number of the latest stable `vMAJOR.MINOR.PATCH` tag. For alpha and beta independently:

- Continue an unreleased prerelease line by incrementing its suffix, for example `v3.3.55-beta.1` to `v3.3.55-beta.2`.
- If no prerelease exists for a version beyond the latest stable release, begin the next patch at `.1`, for example stable `v3.3.54` creates `v3.3.55-beta.1`.
- Treat a prerelease whose base version has already been released as closed; start the following patch rather than tagging a prerelease after its stable release.

Use `scripts/next_tag.py` to calculate tags; it ignores tags outside these formats.

## Workflow

1. Inspect the worktree with `git status --short --branch` and inspect the relevant diff.
   Do not include unrelated user changes in the deployment commit. If the intended commit contents are ambiguous, confirm them before staging.
2. Confirm the changes are ready to ship.
   Run appropriate focused tests or the repository's documented verification. If verification fails, stop before committing or tagging unless the user explicitly accepts the failure.
3. Read the most recent non-merge commit subject before composing the new message:

   ```powershell
   git log --no-merges -1 --format=%s
   ```

   Write a concise commit message describing the staged changes in the same natural language as that subject. For example, if the latest non-merge subject is Chinese, write the new subject in Chinese; if it is English, write it in English. Preserve a recognizable local style when practical.
4. Calculate the tag before committing, selecting `release`, `beta`, or `alpha` from the user's command. Include the publishing remote when configured, typically `origin`, so local and published tag names are both considered without overwriting an existing local tag:

   ```powershell
   .\.venv\Scripts\python.exe .agent\skills\deploy\scripts\next_tag.py release --remote origin
   .\.venv\Scripts\python.exe .agent\skills\deploy\scripts\next_tag.py beta --remote origin
   .\.venv\Scripts\python.exe .agent\skills\deploy\scripts\next_tag.py alpha --remote origin
   ```

   If no repository `.venv` exists, run the script with available Python. If remote tag lookup fails, stop before creating a version tag rather than guessing from stale local tags.
5. Stage only the intended files, inspect `git diff --cached`, then create the commit:

   ```powershell
   git add -- <intended-files>
   git diff --cached --stat
   git diff --cached
   git commit -m "<message in matching language>"
   ```

   Do not create an empty commit unless the user explicitly requests it.
6. Create an annotated tag on the newly created commit, matching this repository's existing tags:

   ```powershell
   git tag -a "<calculated-tag>" -m "<calculated-tag>"
   git show --no-patch --decorate HEAD
   ```

7. Report the commit subject and tag. Push the commit and tag only when explicitly requested:

   ```powershell
   git push origin HEAD "<calculated-tag>"
   ```

## Guardrails

- Never rewrite, move, or delete an existing tag as part of deployment.
- Never include merge commits when choosing the commit-message language.
- Never infer a successful release from a tag alone; report local tagging separately from pushing or CI publishing.
- Keep stable, beta, and alpha numbering independent except that the latest stable release closes older or equal prerelease base versions.
