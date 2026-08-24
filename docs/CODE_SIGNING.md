# Code Signing — Hermes OmniRoute Studio

**Status for the Public Preview (`v0.17.0-omniroute.1`): `UNSIGNED_PREVIEW`.**

## What this means

The Windows installers shipped in the Public Preview (NSIS `.exe` and `.msi`)
are **not Authenticode code-signed**. This is intentional for an early
community fork preview: a trusted Windows code-signing certificate (OV/EV) has
a real cost and identity-verification process that is out of scope for a
preview build.

Evidence in the build config:

- `apps/desktop/package.json` → `build.win.signAndEditExecutable: false`
- No `certificateFile` / `certificateSubjectName` / signing environment is
  configured, and no signing step runs in the packaging scripts.

## Consequence for users: SmartScreen

Because the installer is unsigned and has little reputation, **Microsoft
Defender SmartScreen will typically show “Windows protected your PC.”** on
first run. This is expected and does **not**, by itself, indicate the file is
malicious. Users proceed with **More info → Run anyway** (documented in the
README).

## How users can verify integrity instead of relying on a signature

Every release publishes the **SHA-256** of each installer asset (in the release
notes and/or a `SHA256SUMS.txt` asset). Users should compare before running:

```powershell
Get-FileHash .\HermesOmniRoute-Studio-Setup-0.17.0-omniroute.1.exe -Algorithm SHA256
# compare the output with the value published in the GitHub Release
```

A matching hash proves the download was not altered in transit.

## Path to a signed build (future, not part of this preview)

To remove the SmartScreen friction in a later release:

1. Obtain an OV (or, for immediate reputation, EV) Windows code-signing
   certificate from a CA.
2. Provide it to electron-builder via `win.certificateFile` +
   `CSC_KEY_PASSWORD` (or an HSM/cloud-signing provider), and set
   `signAndEditExecutable: true`.
3. Sign both the NSIS `.exe` and the `.msi`; verify with `signtool verify /pa`.
4. EV certificates earn SmartScreen reputation immediately; OV certificates
   accumulate it over downloads.

Until then, the preview remains `UNSIGNED_PREVIEW` and integrity is established
by the published SHA-256 hashes.
