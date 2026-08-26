# Public Preview Runbook — Hermes OmniRoute Studio `v0.17.0-omniroute.1`

Run these on **your Windows 11 host** (the only place that can build the
installer and where `gh`/`git` are authenticated). Nothing here force-pushes,
touches upstream `NousResearch/hermes-agent`, or publishes a stable release.

## SHA map (read first)

| Ref | SHA | Meaning |
|-----|-----|---------|
| Tested build lineage | `6c46770` | Windows SourceTests + native build already PASSED here |
| hygiene | `b96f4de` | sanitized personal path; removed junk tarballs |
| docs/CI | `602ca7d` | Public-Preview README, code-signing note, changelog, CI + archive hygiene |
| fork metadata | `0bb2dbe` | repository/bugs/homepage -> the fork (packaged desktop package.json) |
| **FINAL — release candidate** | **`649bf5c`** | redacted personal email/hostname from internal audit docs |

**Why the tag targets `649bf5c`, not `6c46770`.** The tag is public; `6c46770`
still exposes the real path `C:\Users\zodyp\...` (and a personal email/hostname)
in tracked docs. `649bf5c` = `6c46770` **plus only non-bundled changes** — docs,
CI guard, `.gitattributes`, `package.json` metadata, one platform-independent
Python test fixture, redactions. **`apps/desktop/electron/` is byte-identical to
`6c46770`** (verified: empty diff), so the Electron Windows PASS carries. But
`apps/desktop/package.json` (a packaged file) changed, so a **fresh native build
at `649bf5c`** is required to produce the release installers and their hashes.

Verified in the cloud on `649bf5c`: `set-exe-identity` 2/2, guardrail 47/47,
`git grep zodyp|lmprado.dz23@gmail|desktop-prado` all 0, release source archive
excludes `audit/`/junk (0 `zodyp` in the archive), secret scans clean.

---

## Step 0 — Bring the candidate into your repo (no force)

You have `hos-preview-649bf5c.bundle` (delivered with this runbook; also written
into your repo root).

```powershell
cd C:\Users\<you>\Documents\Codex\Hermes-OmniRoute

git remote -v      # confirm your FORK remote (e.g. 'oss' or 'origin') ->
                   # github.com/lmpradodz23-design/Hermes-OmniRoute-Studio
                   # NEVER push to a NousResearch/hermes-agent remote.

git bundle verify .\hos-preview-649bf5c.bundle
git fetch .\hos-preview-649bf5c.bundle release/hygiene-cleanup

git checkout develop
git merge --ff-only 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
git push oss develop        # replace 'oss' with your fork remote; NO --force
```

Sanity:

```powershell
git rev-parse HEAD          # == 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
git grep -in "zodyp"        # (no output)
```

---

## Step 1 — Re-verify SOURCE TESTS at the candidate

```powershell
git checkout 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
pwsh -File .\windows-validation.ps1 -Phase SourceTests
```

**Gate:** TYPECHECK=PASS, ELECTRON all-pass/only-honest-skips, PYTHON=PASS, NTFS
atomic-lock race + canary PASS. Expected to pass unchanged (Electron tree
identical to `6c46770`; the only changed test is the guardrail fixture, already
green; packaged metadata re-verified via set-exe-identity). Any failure → STOP.

---

## Step 2 — Native build at the candidate

```powershell
git checkout 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
cd apps\desktop
npm run dist:win
```

**Gate:** exit 0; produces the NSIS `.exe`, the `.msi`, `SHA256SUMS.txt`. Record:

```powershell
Get-ChildItem .\release\*.exe, .\release\*.msi | Get-FileHash -Algorithm SHA256
```

> The artifact name follows `Hermes-OmniRoute-Studio-${version}-win-${arch}.${ext}`,
> e.g. `Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.exe`. Use the ACTUAL
> filenames from `.\release\` in the hash commands and release notes.

---

## Step 3 — Optional: confirm the installer bundles nothing forbidden

Per the license/QA audits (source-level: clean), confirm at the artifact level:

```powershell
# unpack the asar and grep for forbidden bundled deps (should be absent)
npx --yes @electron/asar extract .\release\win-unpacked\resources\app.asar .\_asar_check
Get-ChildItem -Recurse .\_asar_check | Select-String -List "open-wa","wa-automate","whiskeysockets" 
# also confirm no .env / state.db / tokens packaged
```

Expect **no** `@open-wa`, no `@whiskeysockets/baileys`, no `.env`, no `state.db`.
Remove `_asar_check` after.

---

## Step 4 — Runtime gates (the real "is it a working preview?" test)

Clean Windows 11 profile. **Preserve by copy first** (do NOT delete): `state.db`,
userData, HERMES_HOME, settings, sessions, memory, credentials, updater/backoff
state. Then install the **actual NSIS** you will publish (not `win-unpacked`).

| Gate | Pass criteria |
|------|---------------|
| INSTALLATION | NSIS installs under `HermesOmniRoute`; DISPLAYED_VERSION = 0.17.0-omniroute.1; TESTING_OLD_V0204=NO |
| COLD_START / BACKEND_READY | Electron+renderer load; backend reaches READY (from logs, not just a window) |
| RESTART (x3) | Clean teardown; no orphan process / duplicate backend / stale lock / updater loop |
| UPDATER P0 | FORK_GUARD, UPDATE_BACKOFF, ATOMIC_LOCK, STALE_LOCK, VENV_BLOCKER all sane; no fork overwrite, no double updater, no state.db corruption |
| STATE_DB | `PRAGMA quick_check;` + `PRAGMA integrity_check;` == ok (read-only; no VACUUM/repair) |
| LOCAL_ONLY runtime | Enable it; observe network/logs: ZERO cloud egress; force local-model failure -> error/local recovery, NEVER cloud fallback; local endpoint/embeddings ALLOW. If unobservable -> NOT_PROVEN, never PASS by inference |
| U1 smoke | shell/sidebar/chat/composer/sessions/Agents/Subagents/Goals/Memory/Starmap/Model Routing/Context/Files/Artifacts/Diff/Preview/Terminal/Settings/Product Studio/Security Research/WhatsApp surface — trace UI->backend->UI; no fake buttons |
| MSI | `.msi` installs/uninstalls cleanly |
| OPENWA | if it reaches the QR step: OPENWA=WAITING_FOR_HUMAN_QR_SCAN (does not block if clearly OPTIONAL/EXTERNAL) |
| RAPTOR | external runtime; if unavailable: RAPTOR_RUNTIME=BLOCKED_BY_EXTERNAL_DEPENDENCY (do NOT bundle) |

**If any blocking gate (INSTALLATION, COLD_START, BACKEND_READY, RESTART,
LOCAL_ONLY_RUNTIME) fails → STOP. Do NOT tag or publish.**

---

## Step 5 — Tag the candidate (only after Steps 1–4 pass)

```powershell
git checkout 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
git tag -a v0.17.0-omniroute.1 -m "Hermes OmniRoute Studio - Windows Public Preview v0.17.0-omniroute.1" 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
git push oss v0.17.0-omniroute.1
git rev-list -n1 v0.17.0-omniroute.1   # MUST == 649bf5c854248ee29e8c0ba799e0afb5d263d5b3
```

---

## Step 6 — DRAFT pre-release with assets

Fill the SHA-256 (from Step 2) into `RELEASE_NOTES_v0.17.0-omniroute.1.md` first.

```powershell
gh release create v0.17.0-omniroute.1 `
  --repo lmpradodz23-design/Hermes-OmniRoute-Studio `
  --title "Hermes OmniRoute Studio - Windows Public Preview v0.17.0-omniroute.1" `
  --notes-file .\RELEASE_NOTES_v0.17.0-omniroute.1.md `
  --prerelease --draft `
  .\apps\desktop\release\Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.exe `
  .\apps\desktop\release\Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.msi `
  .\apps\desktop\release\SHA256SUMS.txt
```

**Allowed assets ONLY:** the `.exe`, the `.msi`, `SHA256SUMS.txt`. Do NOT attach
`win-unpacked`, `.bak`, logs, `state.db`, runtime evidence, `.tgz`, git bundles,
or credentials.

---

## Step 7 — Inspect the draft, then publish

Download the draft's own assets and recompute SHA-256; if any hash differs →
**STOP_RELEASE**. Confirm TAG==`649bf5c`, EXE/MSI hashes, notes, license,
notices, known-limitations, SmartScreen warning all present. Then:

```powershell
gh release edit v0.17.0-omniroute.1 --repo lmpradodz23-design/Hermes-OmniRoute-Studio --draft=false --prerelease
gh release view v0.17.0-omniroute.1 --repo lmpradodz23-design/Hermes-OmniRoute-Studio --web   # confirm publicly accessible
```

**Keep `--prerelease`. Do NOT mark latest/stable.** Stable = `NOT_AUTHORIZED`.

---

## Step 8 — Repository presentation (after publish)

Set the repo description, and topics: `hermes ai-agents developer-tools electron
multi-model mcp local-ai windows open-source llm`. Confirm README, Releases,
LICENSE detection, SECURITY, CONTRIBUTING render. No misleading claims.

---

## Optional: also scrub the personal path from git HISTORY (your call)

HEAD is clean, and neither the installer nor the release source archive contains
the personal path. But older commits + the deleted `_to_delete/*.tgz` blobs still
hold `C:\Users\zodyp\...` in **history**, browsable on a public repo. If you want
the repo's history clean too, before making the repo public (or after, accepting
a history rewrite) run `git filter-repo` to strip those paths, then re-push.
This is a **history rewrite / force operation** — I did not do it for you; it is
your decision because it rewrites published history.

## Hard rules

- No `--force`. Never push to `NousResearch/hermes-agent`.
- No invented runtime PASS; if a gate can't be observed, mark NOT_PROVEN.
- Do not bundle OpenWA / CodeQL / RAPTOR. Do not weaken LOCAL_ONLY.
- Publish PRE-RELEASE only. Stable = NOT_AUTHORIZED.
