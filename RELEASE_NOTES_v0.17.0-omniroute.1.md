# Hermes OmniRoute Studio — Windows Public Preview `v0.17.0-omniroute.1`

> **⚠️ Public Preview.** Early community **fork** build for **Windows 10/11**,
> for evaluation only. Expect rough edges. **Not** an official Nous Research
> release. This is a **derivative work** of
> [Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT, © Nous Research).

## Install

1. Download **one** installer below:
   - `Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.exe` (NSIS), or
   - `Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.msi` (MSI).
2. **Verify the SHA-256** (see hashes below) before running.
3. Run it. Windows **SmartScreen will warn** (the build is unsigned) — click
   **More info → Run anyway**. This is expected for an unsigned preview and
   does not by itself mean the file is unsafe. See
   [`docs/CODE_SIGNING.md`](../blob/main/docs/CODE_SIGNING.md).

```powershell
Get-FileHash .\Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.exe -Algorithm SHA256
Get-FileHash .\Hermes-OmniRoute-Studio-0.17.0-omniroute.1-win-x64.msi -Algorithm SHA256
```

## SHA-256 of installer assets

> Fill in from the **build produced at the tagged commit** (`SHA256SUMS.txt`).
> Do not reuse hashes from an earlier build — NSIS/MSI output is not
> byte-reproducible, so each rebuild yields new hashes.

```
NSIS  .exe : <PASTE SHA-256 FROM THE TAGGED BUILD>
MSI   .msi : <PASTE SHA-256 FROM THE TAGGED BUILD>
```

## What's in this preview

- Side-by-side Windows desktop edition with native **OmniRoute** routing, MCP
  tooling, Product Studio, pt-BR UI, project preview, guardrails, and SSH.
- **`LOCAL_ONLY`** fail-closed mode: memory and tools restricted to the local
  machine and loopback — **zero cloud egress**; missing/unreadable config fails
  **closed** (private), never open.
- A default-on destructive-command guardrail plugin.

## Licensing & third parties

- Upstream MIT license and attribution preserved: [`LICENSE`](../blob/main/LICENSE),
  [`NOTICE-OMNIROUTE-STUDIO.md`](../blob/main/NOTICE-OMNIROUTE-STUDIO.md),
  [`THIRD_PARTY_NOTICES.md`](../blob/main/THIRD_PARTY_NOTICES.md).
- WhatsApp automation (OpenWA / Baileys) is **not bundled** in the installer —
  it is fetched at runtime on the end user's machine.

## Known limitations

- **Unsigned** — SmartScreen warning (above).
- Windows-only preview; not hardened for production.
- The OmniRoute gateway is a separate component; some integrations require it
  running locally.

## Verified before release

- Windows source tests (Electron + Python), typecheck, and the NTFS atomic-lock
  multi-process race + canary: **PASS** on the tested build lineage.
- No real secrets, no personal filesystem paths; upstream attribution intact;
  no copyleft dependency bundled in the installer.

---
_Report issues on the [issue tracker](../issues)._
