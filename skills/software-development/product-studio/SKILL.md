---
name: product-studio
description: Build any production software product end to end.
version: 0.3.0
author: DZ23, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [software, architecture, ux, security, testing]
    related_skills: [plan, test-driven-development, requesting-code-review]
---

# Product Studio Skill

Act as the accountable senior engineer for a product from discovery through a verified release. Combine architecture, implementation, product design, security, testing, performance, and operations without claiming evidence that was not produced.

## When to Use

- Building or materially changing a web, desktop, mobile, API, data, or AI product.
- Turning an idea into a working repository, application, or production-ready feature.
- Auditing and improving an existing product across frontend, backend, data, infrastructure, and security.
- Validating a product in the embedded browser after implementation.
- Don't use for a one-line explanation, translation, or a narrowly scoped non-product edit.

## Prerequisites

- Read every applicable `AGENTS.md` and the project's own contribution instructions before editing.
- Establish the exact repository, branch, workspace, runtime, package manager, deployment target, and allowed scope.
- Inventory existing modules and integrations before adding a new abstraction or dependency.
- Load `references/delivery-gates.md` for implementation and release work.
- Load `references/browser-security.md` before using an authenticated or user-controlled browser session.
- Load `references/multi-agent-orchestration.md` when the request spans more than one independent technical domain or asks for an agent team.
- Load `references/spec-driven-delivery.md` for every medium or large build, migration, or cross-system change.
- Load `references/knowledge-and-rules.md` when saving reusable project knowledge or defining workspace-specific behavior.
- Load `references/task-report.md` before closing a coding task or handing changes to a reviewer.
- Load `references/nontechnical-intake.md` when the user describes a business or product without technical requirements.
- Load `references/deployment-integrations.md` before connecting a hosting/database account or publishing a project.
- Load `references/subscription-auth.md` before connecting ChatGPT/Codex, Claude Code, Copilot, or another subscription-backed CLI.

## Procedure

1. **Frame the outcome.** Restate the user-visible result, acceptance criteria, constraints, non-goals, and irreversible actions. Completion criterion: the requested outcome can be tested without interpreting vague wording.
2. **Create the reviewable spec when warranted.** For medium or large work, produce requirements, architecture, task order, acceptance gates, risks, rollback, and Mermaid diagrams where relationships matter. `/goal draft` must remain paused until `/goal resume`; narrow fixes may proceed without this gate. Completion criterion: the design can be reviewed before files change.
3. **Audit the system.** Inspect architecture, dependencies, configuration, authentication, authorization, tenancy, data, APIs, jobs, storage, observability, CI/CD, tests, and current working-tree changes. Completion criterion: every affected boundary and owner is identified.
4. **Select execution topology.** Work directly for one tightly coupled domain; use one `delegate_task` specialist for a focused independent investigation; use a single batch call for independent cross-domain work; use an orchestrator child only when nested decomposition is genuinely needed. Completion criterion: every delegate has a bounded scope, unique output contract, file ownership, and validation target.
5. **Diagnose with evidence.** Separate symptom, cause, impact, priority, and uncertainty. Never replace missing evidence with an assumption. Completion criterion: the proposed change addresses the demonstrated root cause or clearly labeled product requirement.
6. **Design the smallest coherent solution.** Define contracts, trust boundaries, failure modes, migrations, rollback, accessibility, responsive behavior, latency, and operating cost. Extend existing architecture unless evidence supports replacement. Completion criterion: compatibility and failure behavior are explicit.
7. **Implement in vertical slices.** Keep types strict, secrets server-side, permissions least-privileged, errors actionable, and UI strings localized. Pair behavior with unit or integration tests as each slice lands. Completion criterion: there are no placeholders, dead branches, TODOs, or fake success paths in scope.
8. **Validate the experience and live preview.** Run focused tests first, then the relevant integration, end-to-end, build, and security checks. For a UI, start the real project server, open its localhost URL in the embedded preview, and exercise rendered behavior with `drive_preview`, `read_preview`, or browser tools. Completion criterion: important happy paths, failures, edge cases, keyboard use, responsive layout, and the live preview have evidence.
9. **Harden release readiness.** Review OWASP risks, data exposure, dependency advisories, rate limits, timeouts, retry/idempotency, logs, metrics, backups, migration safety, and rollback. Completion criterion: residual risks are documented with severity and owner.
10. **Distill knowledge and report honestly.** Save durable facts as source-backed Knowledge Cards, keep procedural guidance in Skills, respect hierarchical `AGENTS.md`, and use the generated task report for changed files, tools, delegates, models, and verification evidence. Never call local compilation production proof.

When the user says “publish this”, “put it online”, “deploy my app”, or equivalent plain language, follow `references/deployment-integrations.md`; do not require them to know Supabase, Vercel, MCP, CLI flags, or infrastructure terminology.

## Product Design Rules

- Prefer a clear information hierarchy and a small number of obvious actions.
- Meet WCAG AA for contrast, keyboard navigation, focus, labels, status, and errors.
- Design loading, empty, offline, permission-denied, partial-success, and recovery states.
- Validate desktop and mobile layouts in the rendered product, not from source inspection alone.
- Treat polish as functional: motion must explain state, copy must guide recovery, and feedback must follow every material action.

## Security Rules

- Map trust boundaries before adding browser control, plugins, MCP servers, uploads, webhooks, or model tools.
- Require explicit user intent before sensitive browser actions, authentication, publishing, payments, destructive changes, or sending external messages.
- Never copy browser cookies, saved passwords, tokens, or private profile data into prompts or logs.
- Validate access control on the server; client-side hiding is not authorization.
- Prefer allowlists and narrowly scoped capabilities over general shell, filesystem, or network access.

## Pitfalls

- A healthy endpoint does not prove the full workflow or data integrity.
- A design mock does not prove accessible rendered behavior.
- High test coverage does not compensate for missing authorization or tenant-isolation tests.
- Automatic retries can duplicate side effects without idempotency.
- A plugin or MCP server is executable trust, not passive configuration.
- A successful local build does not prove signing, installation, update, migration, rollback, or production operation.
- Spawning every specialist for every request increases cost and creates correlated noise; select only the domains with independent work.
- Multiple agents editing the same files without ownership boundaries creates regressions that apparent parallelism cannot recover.

## Verification

Before reporting completion, account for all applicable gates in `references/delivery-gates.md`. Provide the exact commands or interactions run, their outcomes, the generated artifact location, known residual risks, and a safe rollback or uninstall path.
