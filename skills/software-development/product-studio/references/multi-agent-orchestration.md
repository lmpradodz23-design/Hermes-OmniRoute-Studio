# Multi-Agent Product Orchestration

The parent Hermes session is the accountable Product Orchestrator. It owns scope, dependency order, integration, user communication, and the final evidence ledger. Specialists advise or implement bounded work; they do not independently broaden scope or declare the product complete.

## Execution Modes

| Scope | Topology | Rule |
|---|---|---|
| Tiny, one-domain change | Parent only | Avoid delegation overhead. |
| Focused independent task | One leaf `delegate_task` | Return evidence and a bounded recommendation or patch. |
| Two to four independent domains | One batch `delegate_task` call | Run in parallel; assign non-overlapping files or read-only reviews. |
| Large product with nested workstreams | One orchestrator child plus bounded leaves | Use only when the child must decompose its own domain. |
| Repeated long-lived collaboration | Named Hermes bots and a team chat | Give each teammate its own memory, skills, and canonical chat. |

Do not create a permanent agent when an ephemeral delegate is enough. Do not spin up the full roster for a button color, copy edit, or single query.

## Specialist Roster

1. **UI Architect** — interaction model, semantic tokens, responsive and mobile-first layout, component reuse, WCAG AA, rendered visual verification.
2. **Data and Supabase Engineer** — schemas, PostgreSQL, migrations, transactions, indexes, RLS, storage policies, tenant isolation, backup and restore. Use the generic data scope when Supabase is absent.
3. **API Integrator** — external APIs, Edge Functions or server-side proxies, secrets, webhooks, signatures, idempotency, retry, rate limits, failure contracts.
4. **Testing Engineer** — unit and integration tests, Playwright end-to-end workflows, fixtures, failure injection, regression reproduction, evidence capture.
5. **Security and Privacy Engineer** — threat model, OWASP, authentication, authorization, SSRF, XSS, CSRF, data minimization, secret handling, plugin/MCP/browser trust.
6. **Code Auditor** — architecture conformance, strict types, multi-tenant correctness, concurrency, performance, dead code, duplication, maintainability.
7. **SEO and Accessibility Engineer** — metadata, structured data, sitemap, robots policy, crawlability, semantic HTML, accessibility and performance signals.
8. **Deploy and Reliability Engineer** — builds, environment contracts, containers, CI/CD, health and readiness, logs, metrics, rollout, rollback, upgrade and uninstall.
9. **AI and Agent Architect** — model routing, OmniRoute policies, prompts, tools, MCP, RAG, memory boundaries, evaluation, cost, latency, fallback and agent handoffs.

## Dynamic Selection

Map requested outcomes to the smallest role set. Examples:

- “Change this button color”: UI Architect only, or parent only if trivial.
- “Create subscription billing”: Data, API, UI, Security, Testing, and Deploy; Code Auditor reviews after integration.
- “Add an AI coding agent”: AI and Agent Architect, Security, API, Testing, and Deploy; UI joins only if a user-facing surface changes.
- “Fix login loop”: Testing reproduces, API or Data diagnoses ownership, Security reviews session controls, Code Auditor performs final regression review.

Select roles from affected trust boundaries and acceptance criteria, not keyword matching alone.

## Dependency Graph

Use this default order, pruning irrelevant stages:

1. Product Orchestrator establishes scope and acceptance criteria.
2. Data and Security establish contracts and trust boundaries.
3. API and AI implement service behavior against those contracts.
4. UI implements the user journey against stable interfaces.
5. Testing exercises the integrated workflow and failure paths.
6. Code Auditor independently reviews the combined diff and test evidence.
7. SEO/Accessibility and Deploy/Reliability run release-specific gates.
8. Product Orchestrator reconciles findings, reruns affected gates, and reports residual risk.

Parallelize only nodes without a dependency edge. Run reviewers after the integrated code exists, not against divergent partial branches.

## Delegate Contract

Every `delegate_task` request must include:

- exact repository, branch, workspace, and user scope;
- role and concrete goal;
- files or subsystem owned, with read-only status when applicable;
- inputs and contracts it may rely on;
- prohibited actions and sensitive boundaries;
- required tests or inspection evidence;
- a compact return schema: findings, files changed, tests run, risks, blockers.

Use one batch call for siblings so the runtime applies its real concurrency policy. Give each delegate a distinct lens; identical reviewer prompts produce duplicated confidence, not broader evidence.

## Integration Rules

- The Product Orchestrator reviews every delegate result and the actual combined diff.
- Never accept a delegate's “passed” claim without the referenced command output or reproducible interaction.
- Assign a single writer per file at a time. Read-only auditors may overlap writers only when they review a stable snapshot.
- A failed or timed-out specialist falls back to direct parent work or a smaller retry; it never silently removes an acceptance criterion.
- Any external publish, payment, credential creation, destructive migration, or production deployment remains subject to explicit user authorization.
