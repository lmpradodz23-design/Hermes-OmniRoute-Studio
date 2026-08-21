# Product Delivery Gates

Use only the gates relevant to the product, but explicitly mark every applicable gate as passed, failed, blocked, or not applicable.

## Engineering

- Repository identity, branch, scope, and dirty files are recorded.
- Static types, formatting, linting, and focused tests pass.
- Unit tests cover business rules and failure branches.
- Integration tests exercise real module boundaries.
- End-to-end tests exercise the user-visible workflow.
- Production build completes without hidden fallback or placeholder behavior.

## Architecture and Operations

- API contracts, schemas, migrations, compatibility, and rollback are verified.
- Timeouts, cancellation, retry, backoff, idempotency, and rate limits are intentional.
- Logs contain enough context to diagnose failures without leaking secrets.
- Health checks distinguish process health, dependency readiness, and workflow success.
- Deployment, upgrade, uninstall, backup, and restore paths are documented and tested where applicable.

## Experience

- Loading, empty, error, offline, permission, and recovery states are rendered.
- Keyboard navigation, focus order, labels, contrast, and screen-reader status are checked.
- Narrow and wide layouts are visually exercised.
- Destructive actions explain scope and recovery before execution.

## Security and Privacy

- Authentication, authorization, object ownership, and tenant isolation are tested server-side.
- Inputs, URLs, uploads, redirects, and tool arguments are validated at their trust boundary.
- Secrets remain outside source, client bundles, screenshots, prompts, and logs.
- Browser, filesystem, shell, MCP, and plugin capabilities are least-privileged and attributable.
- Dependency advisories are reviewed; accepted risk includes a reason and mitigation.
