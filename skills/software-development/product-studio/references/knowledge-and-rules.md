# Knowledge Cards and Scoped Rules

Keep declarative knowledge separate from procedural behavior.

## Knowledge Cards

A Knowledge Card is one atomic, reusable fact with provenance. Store project cards under `.hermes/knowledge/` when the repository permits it, or in Hermes local memory when it does not.

Each card must contain:

- a stable title and short fact statement;
- source path, symbol or URL, and revision or retrieval date;
- tenant, environment, module, or project scope;
- confidence: `verified`, `inferred`, or `stale`;
- invalidation condition;
- related cards without copying their full content.

Never turn a chat assumption into a verified card. Never store credentials, browser cookies, raw personal data, or unrestricted production exports. Refresh drift-prone cards before using them for deployment, security, prices, regulations, or provider capabilities.

Skills describe how to perform work. Knowledge Cards record facts discovered while performing it. Session memory may help recall either, but it does not replace their provenance.

## Scoped rules

Use Hermes' existing hierarchical `AGENTS.md` contract instead of adding a competing `RULES.md` loader:

- root `AGENTS.md` defines repository-wide rules;
- nested `AGENTS.md` files add rules for their directory subtree;
- `AGENTS.override.md` replaces the same-scope rule file when an intentional override is needed;
- load the full applicable chain before editing a file;
- narrower scope wins only where it explicitly conflicts.

Keep different products and tenants in separate workspaces or scoped rule trees. Never let a card or rule from one tenant silently influence another.
