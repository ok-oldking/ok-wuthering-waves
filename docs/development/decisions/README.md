# Architecture Decision Records

An ADR is required when a proposed macOS foreground-port change deliberately departs from the normative constraints, changes a cross-repository contract, introduces a new security/permission assumption, or chooses between materially different platform architectures.

## ADR-required examples

- weakening or changing foreground/focus behavior;
- changing the public-Apple-API-only policy;
- moving ownership between `ok-script` and OK-WW;
- using a capture/input design other than the accepted ScreenCaptureKit/Quartz foreground architecture;
- changing the coordinate, frame, held-state, or failure contract;
- adopting background, virtual-display, process-directed, injected, hooked, elevated, or TCC-modifying behavior;
- incompatibly changing Windows behavior or persisted OK-WW configuration;
- selecting a packaged-app identity, entitlement, signing, or permission strategy with architectural consequences;
- adopting substantial code from an external branch or historical PR;
- changing the final immutable dependency/release strategy.

Routine implementation details that stay within the existing contract do not require an ADR.

## Naming

```text
NNNN-short-kebab-title.md
```

Start at `0001`. Keep `0000-template.md` unchanged.

## Status

Use one of:

- `proposed`
- `accepted`
- `rejected`
- `superseded`

A proposed ADR does not authorize code that violates the current contract. Acceptance by the relevant project owners/maintainers is required before such implementation proceeds.

本 contributor 集成分支的用户可以明确授权其分支内的设计决定；ADR 必须记录该授权范围，不能把它写成 upstream 维护者已经接受。最终上游 MVP 审查与验收门槛仍适用。

当前决策：[ADR 0003：packaged MVP 最低 macOS 15+](0003-macos-packaged-minimum-version.md)；框架 13+ API 设计与 host gate 保留，当前包不支持 13/14。

## Cross-repository decisions

A decision spanning both repositories must:

- identify the authoritative ADR and any companion pointer;
- explain why each code change belongs in its repository;
- record development editable-install behavior and final immutable dependency behavior;
- describe coordinated migration and rollback order;
- link companion commits/PRs when available.

## Durable evidence

Each ADR records security, permissions, focus/input safety, Windows regression, tests, hardware/package gates, migration, rollback, and external-source/license review. Superseded ADRs remain in Git and link to their replacement.
