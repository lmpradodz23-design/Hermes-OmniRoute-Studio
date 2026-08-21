# Browser Control and Privacy

## Choose the Surface

- Use the embedded preview for observable product validation and user-guided browsing.
- Use an isolated automation profile for repeatable public or test-account workflows.
- Use an existing personal browser session only when the user explicitly requests that exact task.

## Consent Boundary

- Confirm the target site and intended outcome before accessing authenticated content.
- Pause for passwords, passkeys, CAPTCHA, multi-factor authentication, payments, publishing, deletion, or permission grants.
- Never request that the user paste a password, recovery code, private key, or session cookie into chat.
- Do not traverse unrelated tabs, history, downloads, stored credentials, or account settings.

## Data Handling

- Read only the minimum visible content needed for the task.
- Do not persist cookies, tokens, personal data, or screenshots unless the user requests an artifact and understands its contents.
- Redact secrets and personal identifiers from logs, test fixtures, screenshots, and final reports.
- Close or detach isolated sessions after validation and explain whether a reusable profile remains.

## Action Safety

- Preview intended recipients, scope, and irreversible effects before external writes.
- Prefer drafts and reversible changes when the user has not explicitly authorized publication or submission.
- Stop if page identity, account identity, or target environment is ambiguous.
