---
name: pyappify-patch-notes
description: Generate or update localized release patch notes for PyAppify launchers and standalone updaters using root-level CHANGELOG.md and CHANGELOG.language.md files. Use for i18n patch notes, translated changelogs, or preparing update notes for a version. Task UI gettext translations belong to ok-script-i18n; committing, tagging, and publishing belong to deploy.
---

# PyAppify Patch Notes

Write curated notes for ok-ww users in the format supported by PyAppify's
per-language changelog feature. Generate the files locally; a request for notes
alone does not authorize a commit, tag, or push.

## Files and parser contract

Keep the files at the application repository root, in UTF-8:

| File | Language | App catalog locale |
|---|---|---|
| `CHANGELOG.md` | English and fallback | `en_US` |
| `CHANGELOG.zh-CN.md` | Simplified Chinese | `zh_CN` |
| `CHANGELOG.zh-TW.md` | Traditional Chinese | `zh_TW` |
| `CHANGELOG.es.md` | Spanish | `es_ES` |
| `CHANGELOG.ja.md` | Japanese | `ja_JP` |
| `CHANGELOG.ko.md` | Korean | `ko_KR` |

For an unqualified request for i18n notes in this repository, create or update
all six files, including on the first run. Honor an explicitly narrower language
request. File suffixes use PyAppify language codes, not gettext locale names;
English is `CHANGELOG.md`, not `CHANGELOG.en_US.md`. These files do not require
editing or compiling the task UI `.po`/`.mo` catalogs.

```markdown
# Changelog

## v3.5.29 (2026-11-12)
- Fixed daily tasks stopping after a teleport.
- Improved combat targeting when several enemies are nearby.
```

The example illustrates syntax, not actual release claims or a version to use.

- An unindented `## <tag>` starts a section. Its first whitespace-separated word
  must match the version tag; `[v3.5.29]` and `3.5.29` also match `v3.5.29`.
  Dates or other trailing text are ignored. Preserve alpha/beta suffixes exactly.
- `- ` or `* ` starts a note; an indented continuation joins the preceding note.
  Plain paragraphs and `###` category headings do not become notes. Prefer flat
  bullets; nested lists are parsed as additional notes rather than a hierarchy.
- Put the newest release first. Use the same tag and date in every translation,
  with one section per version, and preserve older entries.
- PyAppify reads the changelogs from the **target version's commit**. It combines
  notes for tagged versions brought in by the update, falling back to English
  per version and deduplicating identical notes. If the target has no entry in
  the selected language or English, it falls back to commit messages; untagged
  branch/PR versions also use commit messages. Avoid empty placeholder sections.

## Generate the entries

Limit release-note history to **ok-ww v3.0.0 onward**. Do not generate or
backfill sections for 2.x or earlier releases. This cutoff refers to the app's
version tags, not the ok-script or PyAppify dependency versions. When reporting
the generated range, explicitly mention the v3.0.0 history cutoff. A request for
the next release still covers that release's changes since its baseline;
historical backfills cover only the requested releases within this cutoff.

For an initial historical backfill, enumerate every reachable version tag from
v3.0.0 through the target, including alpha/beta tags, and create matching sections
in all requested languages. Compare stable releases with the previous reachable
stable tag so their notes include prerelease changes. Compare prereleases with
the previous reachable prerelease in their version line, or the previous stable
release when none exists. Check diffs for merge-only or vaguely named releases.
Use each tag's release date rather than today's date. For a release containing
only internal changes or the same tree as its baseline, use a concise translated
maintenance note stating that no additional user-facing changes were recorded;
do not invent features or leave an empty section. Verify tag coverage and the
v3.0.0 lower bound across all language files before reporting completion.

1. Inspect `git status --short`, existing `CHANGELOG*.md`, tags, and the requested
   release range. Use the user's target tag and base when supplied. Otherwise
   use the next tag calculated by the existing [deploy skill](../deploy/SKILL.md),
   in the requested stable/alpha/beta channel, without committing or tagging.
   Use the previous reachable tag in that channel as the baseline; for a stable
   release use the previous stable tag so prerelease changes are included.
   If the baseline predates v3.0.0, use the v3.0.0 boundary instead. For a
   v3.0.0 entry, describe only changes introduced by that release rather than
   summarizing all earlier history. State the chosen range;
   ask only when the intended release line or scope cannot be inferred.
2. Read the non-merge commit subjects and bodies for that range, then inspect
   relevant diffs to verify user-visible effects:

   ```powershell
   git log --no-merges --format='%h %s%n%b' <base-tag>..<target-ref>
   git diff --stat <base-tag> <target-ref>
   ```

   For a future release, `<target-ref>` is normally `HEAD`. Include relevant
   uncommitted changes only if they are intended for that release, and inspect
   their diff separately. Do not incorporate unrelated worktree changes.
3. Draft concise English bullets describing observable additions, improvements,
   and fixes. Combine duplicate changes and omit reverted behavior, internal
   refactors, CI/tests, and dependency bumps without a verified user effect.
   Preserve meaningful limitations; do not infer performance or reliability
   gains from commit titles alone. Do not invent entries to reach a bullet count.
4. Prepend the entry below each file's title, creating missing requested files
   with a `# Changelog` title. If the target section exists, update it in place.
   Translate the same facts and qualifications into every requested language,
   preserving bullet order, tags, links, commands, and code identifiers. Use
   established localized character, task, and game terms from this repository's
   catalogs and docs. Distinguish Simplified and Traditional Chinese.
5. Ensure every generated changelog path is listed explicitly, once per line,
   in `deploy.txt`. The release workflow uses this allowlist to synchronize the
   China and Global update repositories from `pyappify.yml`; notes present only
   in the source repository will not reach those users. Check that
   `.update_repo_gitignore` does not exclude the files. Add only paths that exist.
6. Verify the format and translations as below, then report the tag, base/range,
   files, and any compatibility limitation. When deployment is also requested,
   finish notes and sync-list edits before the deployment commit and annotated
   tag, and continue the deploy workflow under the user's existing authorization.

## Verify and maintain compatibility

- Check that each requested file has exactly one nonempty target section and
  that all translations contain the same changes and qualifications. Review
  `git diff --check` and the changelog/`deploy.txt` diff; include untracked files
  in the review because ordinary `git diff` does not show them.
- When available, use the actual `pyappify.changelog` parser to read each file
  with `utf-8-sig`, call `parse_changelog`, and check the notes under
  `version_key(target_tag)`. Confirm note counts match the authored bullets and
  exercise `notes_for_versions` for a translated language and an English fallback.
  Use the repository-local Python interpreter for these checks.
- Inspect the installed package or the linked/sibling PyAppify source before
  claiming runtime support. PyAppify Python 1.0.20 and launcher v1.2.7 ship the
  per-language changelog feature; Python 1.0.19 lacks `pyappify.changelog`.
  Check the installed runtime rather than silently upgrading dependencies.
  If validating with a sibling
  `pyappify-python/pyappify/changelog.py`, load that file with `runpy.run_path`
  and report that source validation separately from installed runtime support.
- For upstream details, consult [PyAppify's update-note documentation](https://github.com/ok-oldking/pyappify#update-notes)
  and the `pyappify.changelog` module in pyappify-python. The original
  `examples/claude-skills/release-changelog/SKILL.md` is a format reference;
  this repository's deploy skill controls numbering and publishing.
- To correct an already released entry, edit it in a later commit for the next
  release. Existing tags retain their original notes; users updating across that
  version to a newer target can receive the corrected historical entry. Do not
  move published tags to change their notes.
