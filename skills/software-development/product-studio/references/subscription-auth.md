# Subscription-backed AI accounts

Use official browser/device login and official vendor CLIs. Never scrape cookies, copy a private browser profile, impersonate a vendor client, or silently reuse another tool's rotating refresh token.

## ChatGPT and Codex

- Prefer Hermes's `openai-codex` device-code flow from Settings > Providers > Accounts. It opens the official verification page and stores a separate Hermes credential.
- The official Codex CLI is the second supported lane. Run `codex login` and select ChatGPT sign-in, then use the `codex_app_server` runtime when the task should execute inside Codex itself.
- ChatGPT-plan Codex usage is distinct from an OpenAI API key. If the user selects an API-key provider, label it as separately billed.
- Do not import `~/.codex/auth.json` into Hermes. Codex refresh tokens rotate and sharing the credential file can break either client.

## Claude Code

- For subscription-included usage, prefer the official Claude Code CLI itself: install the vendor CLI, run `claude`, choose `/login`, and keep `ANTHROPIC_API_KEY` unset so it cannot override the subscription login.
- Delegate a bounded task through Hermes with `delegate_task` and `acp_command: "claude"` when Claude Code should perform the work. This preserves the official CLI's authentication and accounting boundary.
- Hermes's direct Claude OAuth/setup-token provider is a separate compatibility path. Anthropic may charge third-party use to usage credits; the UI must not describe it as guaranteed subscription-only usage.
- Never read, copy, or refresh Claude Code credentials merely to make a third-party direct HTTP client look like Claude Code.

## Other account-backed providers

- GitHub Copilot ACP uses the official Copilot CLI login.
- Qwen, MiniMax, xAI, and Nous use only the provider flows exposed in the Accounts catalog.
- Report the authenticated account/provider, model availability, quota behavior, and whether usage is plan-included or separately billed. Do not infer billing from successful authentication.

## Verification

For each connected lane, show a redacted auth-status result, list models through that same lane, perform one minimal non-destructive request, and confirm that no API-key environment variable silently took precedence.
