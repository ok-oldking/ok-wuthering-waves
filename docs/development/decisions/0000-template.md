# ADR NNNN: Decision title

- Status: `proposed`
- Date: YYYY-MM-DD
- Owners/reviewers:
- Affected repositories: `ok-script` / `ok-wuthering-waves`
- Related issue/PR/ADR:

## Context

Describe the problem, current behavior, triggering evidence, and why the existing normative constraints or architecture are insufficient.

## Scope boundary

State what this decision changes and what remains out of scope. Explicitly address foreground-only operation, public API policy, fail-closed behavior, repository ownership, official-client scope, and Windows compatibility.

## Decision

Describe the chosen architecture and externally observable behavior. Include interfaces, state transitions, lifecycle, configuration, capability claims, and failure behavior where relevant.

## Alternatives considered

For each serious alternative, record:

- design summary;
- benefits;
- risks and limitations;
- reason rejected or deferred.

## Public API and platform-policy review

List the Apple frameworks/APIs involved and confirm whether they are public. Explicitly address private APIs, `CGEvent.postToPid`, BetterDisplay/virtual displays, injection/hooks, anti-cheat interaction, root requirements, and TCC modification even when they are not used.

## Security, permission, and fail-closed analysis

Describe:

- Screen Recording and Accessibility effects;
- packaged-app identity and entitlement effects;
- frontmost checks and race boundaries;
- held-key/button and `release_all()` behavior;
- stale frame/geometry rejection;
- target, capture, permission, task, and application shutdown behavior;
- data, logs, credentials, screenshots, and privacy impact.

## Repository ownership and dependency impact

Explain why each change belongs in `ok-script` or OK-WW. Record companion changes, editable development linkage, and the final immutable dependency relationship.

## Windows and other-provider regression impact

List affected Windows, ADB, browser, headless, Qt, web, task, config, or packaging paths and the compatibility behavior that must remain unchanged.

## Test and acceptance plan

List exact automated tests and manual/hardware/package gates. Use only:

1. `not-implemented`
2. `unit-tested`
3. `hardware-validated`
4. `packaged-app-validated`

State the required level before merge and public release.

## Migration and rollout

Describe config/schema changes, compatibility adapters, feature flags, task visibility/defaults, documentation, and user migration.

## Rollback

Describe the safe code/config/dependency rollback order. A rollback must preserve fail-closed behavior and identify which evidence gates become invalid.

## External source and license review

For adopted code or design from an external branch, PR, package, article, or sample, record URL/reference, author, license, modifications, and compatibility conclusion. Write “none” when not applicable.

## Consequences and known limitations

Record benefits, costs, deferred work, unsupported cases, and operational burden.

## Approval record

Record who accepted/rejected the decision, on what date, and links to the durable review record.
