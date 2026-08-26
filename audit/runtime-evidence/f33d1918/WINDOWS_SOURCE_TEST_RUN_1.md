# WINDOWS_SOURCE_TEST_RUN_1 (preserved evidence - do not overwrite)

Executor: windows-validation.ps1 -Phase SourceTests, on the real Windows 11 / NTFS host.
Baseline: f33d1918aeebedbb6b69cbb65eadd6a27851d123.

```
TYPECHECK=PASS
ELECTRON=1581 PASS / 2 FAIL / 18 SKIP  (113 files PASS, 2 files FAIL, 2 files SKIP)
PYTHON=143 PASS
WINDOWS_SOURCE_TESTS=FAIL

FAIL_1 = electron/update-marker.concurrency.test.ts
         "REAL multi-process: claimUpdateMarker yields exactly one winner over a seeded stale marker"
         iteration 0 -> Expected: 1  Received: 2   (double-acquire on NTFS)
FAIL_2 = electron/omniroute-security.test.ts
         "real MCP bridge exposes privileged tools but denies their missing write scopes"
         MCP bridge exited 1 / TypeError: fetch failed / connect ECONNREFUSED 127.0.0.1:20128
```

This run is what proved the two defects. The executor itself worked correctly (it
found real problems on the authoritative platform). The fixes below were made in
response; Windows remains authoritative for the atomic-lock component.
