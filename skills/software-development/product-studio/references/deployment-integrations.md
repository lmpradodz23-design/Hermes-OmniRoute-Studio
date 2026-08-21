# Deployment Integrations

Use this reference when a nontechnical user asks to put a project online, create its backend, connect external applications, or prepare a production release.

## Intent routing

- A web frontend or full-stack JavaScript application defaults to Vercel preview deployment when the repository is compatible.
- PostgreSQL, authentication, file storage, realtime, and Edge Functions default to an existing Supabase project when one is already linked; otherwise present the browser login/project selection flow.
- Netlify, Cloudflare, or another configured target wins when the repository already declares that platform.
- Composio supplies optional external application tools. It is not the database, hosting platform, or a replacement for native provider CLIs.
- Never ask a nontechnical user to select a framework or memorize commands. Infer the safest compatible path from the repository and explain the chosen target in plain language.

## Account connection

1. Prefer the installed Hermes MCP catalog entries for Supabase and Vercel. They use vendor OAuth in the browser and keep provider tokens out of the project.
2. For deployment operations not exposed by MCP, use the official CLI login flow: `supabase login` or `vercel login`. Never scrape browser cookies or copy tokens from another application's credential store.
3. Confirm the active Supabase organization/project and Vercel user/team before linking. Record the non-secret identifiers in the task report.
4. Keep service-role keys, deploy tokens, database passwords, and Composio keys in the scoped Hermes secret store or provider credential store. Never write them into source, screenshots, logs, or client bundles.

## Supabase workflow

1. Detect an existing `supabase/config.toml`, migrations, seed data, generated types, and local project state.
2. Use `supabase login`, `supabase link`, and `supabase status` for account and project setup.
3. Start locally and validate migrations, functions, storage policies, authentication, tenant isolation, and RLS. Every exposed table must have intentional RLS and adversarial cross-tenant tests.
4. Before remote database changes, run the repository checks and `supabase db push --dry-run`. Show the migration set and rollback/backup plan.
5. Apply a remote migration only to the explicitly identified project. Never use remote database reset as a deployment shortcut.
6. Regenerate types and run integration/E2E tests after schema changes.

## Vercel workflow

1. Detect project root, framework, monorepo boundaries, build command, output directory, environment requirements, and an existing `.vercel` link.
2. Use `vercel login`, verify `vercel whoami`, then run `vercel link` for a single project or `vercel link --repo` for a monorepo.
3. Pull environment metadata without exposing values. Run the normal local lint, typecheck, tests, and production build first.
4. Deploy a preview with `vercel deploy`. Capture its URL and deployment identifier, then exercise health, authentication, critical pages, mobile layout, and failure states. Use `vercel curl` for protected previews.
5. Production is a separate promotion gate. Prefer a verified preview followed by promotion or a blue/green `--skip-domain` deployment. Record the prior production deployment so rollback is actionable.
6. Never disable deployment protection to make automated validation easier.

## Composio workflow

1. Install the `composio` MCP catalog entry only when the user wants tools from external applications.
2. Store `MCP_COMPOSIO_API_KEY` in the scoped Hermes secret file; the MCP config contains only `${MCP_COMPOSIO_API_KEY}` in the `x-consumer-api-key` header.
3. Authorize each requested application in the vendor browser flow and review the requested permissions. Do not connect every application preemptively.
4. Keep a narrow toolkit/tool allowlist per workspace. Read operations may follow the active approval mode; messages, payments, publication, deletion, credential changes, and production mutations require a clear action preview.
5. Hermes guardrails remain authoritative because remote MCP actions do not inherit Composio SDK hooks.

## Release evidence

Report the exact repository, branch, commit, provider account/team, linked project, migration plan, preview URL, checks run, production action, rollback target, and anything not verified. A successful CLI exit or HTTP 200 alone is not end-to-end proof.
