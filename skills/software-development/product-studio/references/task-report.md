# Task Report and File Review

The DZ23 Guardrail writes a redacted local report to `<HERMES_HOME>/task-reports/report-<timestamp>-<session>.md` when a session changed files. It records changed paths, Git summary, tools, delegates, provider/model token usage when available, and the session outcome.

The report is an index for review, not proof by itself. Pair every success claim with the real command output, rendered interaction, external lifecycle, or production observation that supports it.

## Review flow

1. inspect the changed-file list and `git diff --stat`;
2. open each relevant diff and validate it against the spec;
3. reject or revert an individual file when it exceeds scope;
4. stage only accepted files;
5. run the checks again after the final change;
6. commit, push, publish, or deploy only as a separate authorized action.

Task reports never include full tool arguments or full diffs because those can contain secrets or private data. Native secret redaction is applied before the file is written. No report means no file change was observed or report generation failed; it must not be described as audit proof.
