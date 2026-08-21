# Hermes OmniRoute Studio

Hermes OmniRoute Studio is a Windows desktop edition designed for nontechnical users who want to request a website, SaaS, CRM, desktop application, mobile project or automation in natural language while retaining engineering review evidence.

## What is included

- Native OmniRoute preset using the local OpenAI-compatible endpoint at `http://127.0.0.1:20128/v1`.
- All 107 tools advertised by the OmniRoute MCP server. Tools are not hidden to simulate safety; deterministic hooks and explicit approval boundaries protect risky operations.
- `dz23-moa` virtual multi-model preset, with three reference slots and one aggregator slot.
- Multi-agent delegation with up to five concurrent children and depth two.
- Product Studio orchestration for UI, backend, data, API, testing, security, SEO, deployment and architecture work.
- Spec-first Goal workflow: `/goal draft` produces reviewable requirements and pauses; `/goal resume` continues only after review.
- Cross-chat memory and user-profile memory through Hermes. Optional providers can be configured without placing secrets in project files.
- Chromium project preview inside the app, scoped agent access and no automatic import of personal browser cookies.
- Native SSH connection profiles for authorized remote development.
- pt-BR interface catalog and English/Chinese compatibility.
- Caveman compression control with explicit on/off state, routed through OmniRoute.
- Xiaomi MiMo provider documentation and configuration entry point.
- Daily local OmniRoute health check and log digest.
- Task reports with redaction, diff evidence, tools/subagents used and verification state.

## Safe defaults

- The dashboard and gateway stay local; the installer does not expose them publicly.
- No Hermes fallback chain is added because OmniRoute owns provider fallback.
- Destructive shell/database/container commands are blocked by a deterministic `pre_tool_call` hook.
- Writes outside the active workspace require explicit confirmation.
- A coding task cannot be marked verified without fresh command evidence.
- Task reports redact fields whose names match key, token, secret or password.
- The Studio never auto-commits, pushes or publishes a project. Review remains granular and user-controlled.
- Secrets are entered through runtime configuration or OS-backed secure storage and are never bundled.

## Side-by-side installation

The Studio uses a unique application id, executable, protocol and installer name. It can coexist with the upstream Hermes Desktop installation. The managed installer only updates Studio-owned skill, plugin and integration files; it creates timestamped backups before changing a pre-existing managed target.

The original `%LOCALAPPDATA%\hermes` runtime can be reused for compatibility, while the desktop application identity remains separate. Do not uninstall the upstream Hermes application until the Studio has been validated for the intended workflows.

## External dependencies

The feature catalog is available without embedding credentials, but provider-backed execution requires the user's own authorized accounts. In particular, model providers, hosted SSH servers, Supabase, Stripe, GitHub and similar integrations need their respective credentials and permission scopes. A catalog entry is not evidence that a third-party lifecycle has been tested.

## Verification gates

Before a release is published:

1. run TypeScript typecheck and lint;
2. run focused Studio tests and the full Electron suite;
3. run Python tests through `scripts/run_tests.sh`;
4. build the production desktop bundle;
5. scan changed files and packaged resources for secrets;
6. build and smoke-test the NSIS installer;
7. inspect the installed identity and bundled managed resources;
8. generate SHA-256 checksums and a release evidence report.

## Known proof boundary

Local automated tests prove the integration contracts and Windows packaging behavior. A real remote SSH lifecycle cannot be claimed until an authorized host and key are supplied. Likewise, every external provider must be tested with its own disposable or properly scoped credential before it can be declared operational.
