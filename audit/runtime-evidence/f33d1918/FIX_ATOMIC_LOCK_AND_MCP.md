# Fixes for the two Windows SourceTests failures

## FAIL_1 - Atomic update lock: NTFS double-acquire

### Root cause
`claimUpdateMarker` serialized claim+stale-recovery through a **file-based**
critical section (`fs.openSync(cs, 'wx')` + `unlink`). On Windows/NTFS a file
lock is unreliable for this:
- delete-pending-on-open-handle: an `unlink`ed file with any lingering handle
  stays in a limbo where a new `open(wx)` returns ACCESS_DENIED, not EEXIST;
- `MoveFileEx` replace can fail when a reader holds the destination.
These made the CS fail to exclude under real contention, letting two claimants
both write the marker (each `renameSync(tmp, file)` replaces) and both return
`acquired:true`. Linux/ext does not exhibit these semantics, so the Linux run
showed 1 winner while NTFS showed 2 - which is exactly why Windows is authoritative.

A secondary issue was in the TEST harness: winners held for a fixed 500ms and
relied on process-spawn timing being tight. On Windows, `node.exe` spawns are
slow and staggered, so contenders did not reliably overlap - a non-deterministic
test that could also register benign acquire-then-exit sequences as winners.

### Fix (root cause, not the test)
1. The critical section is now a **DIRECTORY mutex** (`fs.mkdirSync`), the
   robust cross-process exclusive-create primitive on both POSIX and NTFS (the
   same choice mature lockers like proper-lockfile make). `mkdir`/`rmdir` are
   free of the file-handle delete-pending and rename-replace hazards. Ownership
   is stamped in `<lock>/owner` so release is owner-scoped and a reaper's fresh
   lock is never removed by a slow prior owner.
2. Stale-CS recovery (a holder that crashed mid-claim, > CLAIM_CS_TTL_MS old) is
   reaped by an **atomic directory rename** away, so exactly one reaper wins and
   two reapers can never both "remove then recreate" and admit two claimants.
   (The concurrency test never triggers this path - the CS is fresh each
   iteration - so it is not the test's failure cause, but it is made robust too.)
3. The marker FILE contract is unchanged (`.hermes-update-in-progress`, two
   lines) so the Rust/Python updater and the backend-start gate are unaffected.

### Test hardening (makes the concurrency test DETERMINISTIC, not weaker)
`update-marker.concurrency.test.ts` now uses a **barrier**: every child busy-waits
to a shared `startAt` instant, so all N enter `claimUpdateMarker` simultaneously
(maximum contention, the opposite of artificial serialization). The winner then
**holds the lock until all N contenders have recorded a result**, so it is
provably alive during every attempt - a benign acquire-then-exit can never
masquerade as a second winner, and a genuine simultaneous double-acquire always
shows as >1. Each child writes `<pid>.res` for post-mortem of the real
interleaving on a failing iteration. The CANARY (buggy exists->unlink->write)
still produces >1 winner under this harness.

### Evidence (Linux, pending authoritative Windows re-run)
- update-marker.test.ts + update-marker.concurrency.test.ts: 31 passed
  (20-iteration real multi-process race -> exactly 1 winner; canary -> >1).
- Full electron suite: 1593 passed / 8 skipped / 0 failed; tsc clean.
- Windows/NTFS is authoritative for this component - re-run -Phase SourceTests.

## FAIL_2 - MCP bridge ECONNREFUSED 127.0.0.1:20128

### Classification: TEST_ENVIRONMENT_DEPENDENCY (not a product defect)
`omniroute-security.test.ts` is a live integration test. The OmniRoute *gateway*
on 127.0.0.1:20128 is a SEPARATELY installed OmniRoute component that Hermes does
not bundle or start. The old guard only checked that `~/.omniroute/storage.sqlite`
exists (a proxy for "installed"). On Linux the storage file was absent -> the test
SKIPPED (which is why the suite showed 1593 "passed" - a skip, not a pass). On the
Windows box the storage file existed but the gateway was NOT running -> the guard
let the test run and the bridge's eager `fetch` to :20128 got ECONNREFUSED and the
bridge exited 1. The product code is correct (the bridge rightly refuses an
unreachable/unauthenticated gateway).

### Fix (honest precondition, no convenient masking)
The test now probes the REAL dependency: a TCP liveness check on 127.0.0.1:20128.
Both preconditions must hold (OmniRoute installed AND gateway listening) or the
test skips with a clear reason. When the gateway IS up, the full integration test
runs exactly as before. This converts the false-red into an honest named skip and
does not mask an integration the product is supposed to provide (the gateway is a
genuine external service, not something the Hermes installer starts).

### Evidence
- omniroute-security.test.ts: 9 passed / 1 skipped (the live bridge test skips
  cleanly when the gateway is not reachable). tsc clean.

## Result block (per the mission)

```
ATOMIC_LOCK_ROOT_CAUSE=file-based CS unreliable on NTFS (delete-pending / rename-replace); test relied on spawn timing
ATOMIC_LOCK_FIX=directory mutex (mkdir/rmdir) + atomic-rename stale reap + owner-scoped release; marker file contract unchanged
ATOMIC_LOCK_TARGETED_TESTS=update-marker.test.ts + update-marker.concurrency.test.ts (barrier + coordinated hold + instrumentation) = 31 passed on Linux
ATOMIC_LOCK_CANARY=buggy exists->unlink->write -> >1 winner (kept, still bites)

MCP_20128_OWNER=OmniRoute gateway (separately installed component; not started by Hermes) - integrations/omniroute-defaults.json, omniroute-mcp-bridge.mjs
MCP_ROOT_CAUSE=test guard checked storage-file existence, not gateway liveness; gateway down on Windows -> ECONNREFUSED
MCP_CLASSIFICATION=TEST_ENVIRONMENT_DEPENDENCY
MCP_FIX=probe 127.0.0.1:20128 liveness; skip honestly (with reason) unless installed AND gateway running
MCP_TARGETED_TESTS=omniroute-security.test.ts = 9 passed / 1 skipped

ELECTRON_TYPECHECK=PASS
ELECTRON_FULL=1593 passed / 8 skipped / 0 failed (Linux)
PYTHON_LOCAL_ONLY=PASS (unchanged; 143 on Windows run 1, spot-checked here)

WINDOWS_RETEST_REQUIRED=YES  (NTFS is authoritative for the atomic lock)
BUILD_AUTHORIZED=NO
```
