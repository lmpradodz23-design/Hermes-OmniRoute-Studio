/**
 * In-app update mutual-exclusion marker (#50238).
 *
 * The Tauri updater writes HERMES_HOME/.hermes-update-in-progress for the whole
 * duration of an `--update` run (see apps/bootstrap-installer/src-tauri/src/
 * update.rs `UpdateMarkerGuard`). The marker body is two lines: the updater's
 * pid and the unix-seconds it started.
 *
 * Why: if the user relaunches the desktop mid-update — the window vanished with
 * no progress and looks crashed — a fresh instance must NOT spawn its own local
 * backend. That backend re-locks the venv shim, the updater's straggler cleanup
 * (`force_kill_other_hermes`, taskkill /IM hermes.exe) kills it, the launch
 * fails with the 45s "backend didn't come up" timeout, and the user relaunches
 * into the same trap — an infinite respawn/kill loop. The desktop gates local
 * backend startup on this marker and parks until the update finishes.
 *
 * This module holds the PURE, side-effect-light logic (path, pid liveness,
 * parse + staleness) so it is unit-testable without booting Electron. The
 * polling/boot-progress wrapper lives in main.ts where the boot-progress and
 * log sinks are.
 */

import fs from 'fs'
import path from 'path'

// Even with a live-looking PID, never treat a marker older than this as a live
// update. A full update (git pull + pip + desktop rebuild) is minutes, not tens
// of minutes; past this the marker is almost certainly stale (e.g. the OS
// recycled the pid onto an unrelated process), so the gate self-heals.
export const UPDATE_MARKER_MAX_AGE_MS = 20 * 60 * 1000

// A marker whose startedAt is in the FUTURE by more than this tolerance is
// corrupt or clock-tampered: its age would be negative and would otherwise dodge
// the staleness ceiling forever (never self-healing, wedging updates). Small
// negatives from ordinary clock jitter are allowed; beyond this it is stale.
export const FUTURE_SKEW_TOLERANCE_MS = 5 * 60 * 1000

export function markerPath(hermesHome) {
  return path.join(hermesHome, '.hermes-update-in-progress')
}

// True only if a host process with this pid is currently alive. Signal 0 does
// not deliver a signal — it just probes existence/permission. ESRCH => dead;
// EPERM => alive but owned by another user (still "alive" for our purposes).
// Injectable `kill` keeps it unit-testable.
export function isPidAlive(pid, kill: typeof process.kill = process.kill.bind(process)) {
  if (!Number.isInteger(pid) || pid <= 0) {
    return false
  }

  try {
    kill(pid, 0)

    return true
  } catch (err) {
    return Boolean(err && err.code === 'EPERM')
  }
}

/**
 * Read + interpret the marker.
 *
 * Returns `{ pid, ageMs }` only when an update is GENUINELY still running
 * (parseable pid that is alive, within the age ceiling). Returns `null` for
 * every "no live update" case — absent, unreadable, malformed, dead pid, or
 * past the ceiling — and, when a stale marker file exists, deletes it so it
 * cannot strand future launches.
 *
 * Pure-ish: file I/O against the given path, plus an injectable pid probe and
 * clock for tests.
 */
export function readLiveUpdateMarker(
  hermesHome,
  {
    kill,
    now = Date.now,
    maxAgeMs = UPDATE_MARKER_MAX_AGE_MS
  }: {
    now?: () => number
    maxAgeMs?: number
    kill?: typeof process.kill
  } = {}
) {
  const file = markerPath(hermesHome)
  let raw
  // Capture the marker's identity (mtime) BEFORE reading so the stale-heal
  // unlink can bail if the file was atomically replaced (temp+rename) between
  // our read and our unlink — otherwise we could delete a freshly-written LIVE
  // marker (a boot-loop / double-claim TOCTOU). Best-effort: -1 skips the guard.
  let mtimeAtRead = -1

  try {
    try {
      mtimeAtRead = fs.statSync(file).mtimeMs
    } catch {
      mtimeAtRead = -1
    }
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return null // absent or unreadable => no live update
  }

  const [pidLine, startedLine] = String(raw).split('\n')
  const pid = Number.parseInt((pidLine || '').trim(), 10)
  const startedAt = Number.parseInt((startedLine || '').trim(), 10)
  const ageMs = Number.isFinite(startedAt) ? now() - startedAt * 1000 : Infinity
  const alive = Number.isInteger(pid) && isPidAlive(pid, kill)
  // A marker dated far in the FUTURE is corrupt/tampered — its negative age
  // would dodge the age ceiling forever, so treat it as stale.
  const suspiciousFuture = Number.isFinite(startedAt) && ageMs < -FUTURE_SKEW_TOLERANCE_MS

  if (!alive || ageMs > maxAgeMs || suspiciousFuture) {
    try {
      // Only prune if the marker on disk is STILL the one we read (mtime match),
      // so a marker another process just rewrote is never deleted from under it.
      if (mtimeAtRead < 0 || fs.statSync(file).mtimeMs === mtimeAtRead) {
        fs.unlinkSync(file)
      }
    } catch {
      void 0
    }

    return null
  }

  return { pid, ageMs }
}

/**
 * Write the update-in-progress marker *from the desktop* before handing off
 * to the detached updater.
 *
 * The Tauri-based hermes-setup.exe takes several seconds to initialise its
 * window and reach the Rust `run_update` entry point where it writes the
 * marker itself. During that gap the desktop's `app.quit()` teardown kills
 * the backend child, the renderer's WebSocket drops, and the renderer
 * immediately calls `ensureBackend()` → `waitForUpdateToFinish()`. Because
 * the updater hasn't written the marker yet, the gate sees no live update
 * and spawns a *new* backend — which re-locks `.pyd` files in the venv.
 * When the updater finally reaches the venv-rebuild stage it finds those
 * files locked and the update bricks.
 *
 * Fix: the desktop writes the marker itself, using the spawned updater's
 * PID, immediately after `spawn()`. The updater's `UpdateMarkerGuard` will
 * later adopt it or another hand-off stage may replace the PID. A live
 * holder's original timestamp is preserved across those transfers so retries
 * cannot keep resetting the 20-minute stale ceiling. When the updater finishes
 * it deletes the marker as before.
 * If the updater never starts (spawn failure) the marker still contains a
 * real PID, so `readLiveUpdateMarker` will self-heal once that PID exits.
 */
export function writeUpdateMarker(
  hermesHome,
  pid,
  {
    kill,
    now = Date.now,
    maxAgeMs = UPDATE_MARKER_MAX_AGE_MS,
    startedAt
  }: {
    now?: () => number
    maxAgeMs?: number
    kill?: typeof process.kill
    startedAt?: number
  } = {}
) {
  const file = markerPath(hermesHome)
  const nowMs = now()
  const owner = readLiveUpdateMarker(hermesHome, { kill, maxAgeMs, now: () => nowMs })

  const acquiredAt =
    typeof startedAt === 'number' && Number.isInteger(startedAt)
      ? startedAt
      : owner
        ? Math.floor((nowMs - owner.ageMs) / 1000)
        : Math.floor(nowMs / 1000)

  // Publish ATOMICALLY (temp + rename) so a concurrent reader never observes a
  // half-written first line and mistakes it for a dead marker to prune. rename
  // over an existing marker is atomic on the same filesystem; the temp is
  // uniquely named per pid so parallel writers don't clobber each other's temp.
  const tmp = `${file}.tmp.${pid}`

  try {
    fs.writeFileSync(tmp, `${pid}\n${acquiredAt}\n`, 'utf8')
    fs.renameSync(tmp, file)
  } catch {
    // Best-effort: if we can't write the marker, proceed anyway. The
    // updater will write its own when it reaches run_update.
    try {
      fs.unlinkSync(tmp)
    } catch {
      void 0
    }
  }
}

/**
 * Read + classify a marker WITHOUT deleting it (unlike readLiveUpdateMarker,
 * whose self-heal unlink-by-path is a TOCTOU). Returns 'absent' | 'live' |
 * 'stale'. Used inside the claim critical section, where reads never mutate.
 */
function peekMarker(
  file,
  {
    kill,
    maxAgeMs = UPDATE_MARKER_MAX_AGE_MS,
    now = Date.now
  }: { kill?: typeof process.kill; maxAgeMs?: number; now?: () => number } = {}
): { state: 'absent' | 'live' | 'stale'; info?: { pid: number; ageMs: number } } {
  let raw

  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return { state: 'absent' }
  }

  const [pidLine, startedLine] = String(raw).split('\n')
  const pid = Number.parseInt((pidLine || '').trim(), 10)
  const startedAt = Number.parseInt((startedLine || '').trim(), 10)
  const ageMs = Number.isFinite(startedAt) ? now() - startedAt * 1000 : Infinity
  const alive = Number.isInteger(pid) && isPidAlive(pid, kill)
  const suspiciousFuture = Number.isFinite(startedAt) && ageMs < -FUTURE_SKEW_TOLERANCE_MS

  if (!alive || ageMs > maxAgeMs || suspiciousFuture) {
    return { state: 'stale' }
  }

  return { state: 'live', info: { pid, ageMs } }
}

// The claim critical-section spinlock. A crashed CS holder must not wedge
// updates forever, but the CS is held for only a couple of syscalls, so any CS
// older than this is unambiguously abandoned (its holder died mid-claim) and a
// live holder is never mistaken for it. Generous margin over the real CS
// duration (microseconds) so a running holder is never reaped.
export const CLAIM_CS_TTL_MS = 30 * 1000
const CLAIM_CS_SPIN_MS = 2000 // total time to wait for the CS before failing closed

function claimCsPath(file) {
  return `${file}.cs`
}

/**
 * Enter the claim critical section by atomically creating a CS lock file
 * (`open(..., 'wx')` — O_EXCL). Returns a unique owner token on success, or null
 * if the CS could not be taken within the spin budget (→ caller fails closed).
 *
 * A CS older than CLAIM_CS_TTL_MS belonged to a process that crashed mid-claim;
 * it is reaped owner-safely: rename it away (atomic; one reaper wins) then delete
 * the grabbed copy only if it is STILL the stale one — never a fresh CS.
 */
function enterClaimCs(file, pid): string | null {
  const cs = claimCsPath(file)
  // The CS spinlock times itself against REAL wall-clock, because it compares
  // against the CS file's real mtime and busy-spins in real time. A test's
  // injected `now` (which controls MARKER staleness) must NOT drive this, or a
  // constant fake clock would make the spin deadline unreachable and hang.
  const now = Date.now
  const token = `${pid}\n${now()}\n${csTokenCounter++}\n${process.pid}`
  const deadline = now() + CLAIM_CS_SPIN_MS

  for (;;) {
    let fd
    try {
      fd = fs.openSync(cs, 'wx') // atomic exclusive create
    } catch (err) {
      if (err && (err as NodeJS.ErrnoException).code === 'EEXIST') {
        // A CS exists — fall through to inspect/reap it below.
      } else {
        return null // unexpected IO error → fail closed
      }
      fd = undefined
    }

    if (fd !== undefined) {
      // We created the CS. Write the token; if that fails (e.g. disk full), do
      // NOT leave an EMPTY cs behind — it would wedge every claim until the TTL
      // reap. Unlink it and fail closed immediately.
      let wrote = false
      try {
        fs.writeSync(fd, token)
        wrote = true
      } catch {
        wrote = false
      } finally {
        try {
          fs.closeSync(fd)
        } catch {
          void 0
        }
      }

      if (!wrote) {
        try {
          fs.unlinkSync(cs)
        } catch {
          void 0
        }

        return null // could not stamp the CS → fail closed, no empty-cs wedge
      }

      return token
    }

    // CS is held. Reap it only if it is abandoned (older than the TTL).
    let ageMs = 0
    try {
      ageMs = now() - fs.statSync(cs).mtimeMs
    } catch {
      // Vanished between openSync(EEXIST) and stat → retry immediately.
      continue
    }

    if (ageMs > CLAIM_CS_TTL_MS) {
      const grave = `${cs}.reap.${pid}.${now()}.${csTokenCounter++}`
      try {
        fs.renameSync(cs, grave) // atomic; exactly one reaper wins
      } catch {
        continue // lost the reap race → retry the create
      }
      // Only delete if it is STILL abandoned (a fresh CS created in the window
      // would have a young mtime — restore it rather than discard a live CS).
      try {
        if (now() - fs.statSync(grave).mtimeMs > CLAIM_CS_TTL_MS) {
          fs.unlinkSync(grave)
        } else {
          try {
            fs.linkSync(grave, cs)
          } catch {
            void 0
          }
          try {
            fs.unlinkSync(grave)
          } catch {
            void 0
          }
        }
      } catch {
        void 0
      }
      continue
    }

    if (now() >= deadline) {
      return null // a live CS held the section past our budget → fail closed
    }
    // Brief busy spin; the CS is microseconds-long so this rarely loops.
    spinBriefly()
  }
}

let csTokenCounter = 0

function spinBriefly() {
  const until = Date.now() + 1
  while (Date.now() < until) {
    // busy-wait ~1ms; the CS holder finishes in microseconds
  }
}

/** Release the claim CS only if we still own it (token match) — never delete a
 * reaper's fresh CS. */
function exitClaimCs(file, token: string) {
  const cs = claimCsPath(file)
  try {
    if (fs.readFileSync(cs, 'utf8') === token) {
      fs.unlinkSync(cs)
    }
  } catch {
    void 0
  }
}

/**
 * ATOMIC cross-process claim of the update marker. Contract: at most ONE process
 * acquires; two desktop instances can never both start a destructive update.
 *
 * Correctness rests on a single insight: any "remove the stale marker at PATH"
 * races with "someone replaced it at PATH", so a self-heal unlink/rename in the
 * claim path can double-acquire (a third claimant slips into the absent window).
 * We therefore SERIALIZE the whole read-decide-write through an atomic
 * critical-section spinlock (`enterClaimCs`, an O_EXCL create). Inside the CS no
 * other claimant runs, so the marker can be inspected and (over)written safely:
 *   - live owner → block (never stolen);
 *   - absent/stale → write our marker atomically (temp+rename) and acquire.
 * The CS is held for a couple of syscalls; a CS abandoned by a crashed claimant
 * self-heals after CLAIM_CS_TTL_MS.
 *
 * Call BEFORE the first destructive step (backend kill). Release the MARKER with
 * releaseUpdateMarker on every path that does NOT hand off to the updater.
 */
export function claimUpdateMarker(
  hermesHome,
  pid,
  {
    kill,
    now = Date.now,
    maxAgeMs = UPDATE_MARKER_MAX_AGE_MS,
    startedAt
  }: {
    now?: () => number
    maxAgeMs?: number
    kill?: typeof process.kill
    startedAt?: number
  } = {}
): { acquired: boolean; owner?: { pid: number; ageMs: number } } {
  const file = markerPath(hermesHome)
  const nowMs = now()
  const acquiredAt =
    typeof startedAt === 'number' && Number.isInteger(startedAt) ? startedAt : Math.floor(nowMs / 1000)

  const token = enterClaimCs(file, pid)
  if (token === null) {
    return { acquired: false } // could not serialize → fail closed
  }

  try {
    const peek = peekMarker(file, { kill, maxAgeMs, now: () => nowMs })

    if (peek.state === 'live') {
      return { acquired: false, owner: peek.info }
    }

    // Absent or stale: write our marker atomically. Inside the CS no other
    // claimant can interleave, so a plain atomic replace is safe and there is no
    // unlink-by-path to race.
    const tmp = `${file}.claim.${pid}.${nowMs}`
    try {
      fs.writeFileSync(tmp, `${pid}\n${acquiredAt}\n`, 'utf8')
      fs.renameSync(tmp, file) // atomic replace of an absent/stale marker
    } catch {
      try {
        fs.unlinkSync(tmp)
      } catch {
        void 0
      }

      return { acquired: false } // could not publish → fail closed
    }

    return { acquired: true }
  } finally {
    exitClaimCs(file, token)
  }
}

/**
 * Release the marker ONLY if it still belongs to `pid` (owner-scoped). After a
 * hand-off the marker holds the updater child's pid, so releasing with the
 * desktop pid is a safe no-op there; on a pre-spawn failure it holds our pid and
 * must be cleared so the next boot (and the backend-start gate) is not wedged.
 * Never deletes another process's live claim.
 */
export function releaseUpdateMarker(hermesHome, pid): boolean {
  const file = markerPath(hermesHome)
  let raw
  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return false // nothing to release
  }
  const ownerPid = Number.parseInt((String(raw).split('\n')[0] || '').trim(), 10)
  if (ownerPid !== pid) {
    return false // not ours (handed off, or someone else) — leave it
  }
  try {
    fs.unlinkSync(file)
    return true
  } catch {
    return false
  }
}

/**
 * Whether a NEW updater hand-off must be refused because a different,
 * already-alive updater currently owns the marker (#75778).
 *
 * `writeUpdateMarker` unconditionally overwrites the marker file. Called
 * before every hand-off with no conflict check, a user who clicks "Update"
 * again while a prior updater is still parked mid-run (e.g. "waiting for
 * Hermes to exit…") clobbers that still-running updater's claim: the
 * retry's pre-write now names the NEW child, so the OLD process — alive
 * and mutating the checkout — is no longer recorded as the owner. A second
 * live updater can then run over the same tree unrecorded, the exact
 * two-updaters-at-once hazard `UpdateMarkerGuard` in the Rust updater
 * exists to prevent (apps/bootstrap-installer/src-tauri/src/update.rs).
 *
 * Returns the live foreign owner (with a ready-to-show message) when the
 * hand-off must be refused, or `null` when it's safe to spawn — no marker,
 * or the existing one is stale/dead and self-heals via
 * `readLiveUpdateMarker`.
 */
export function updateHandoffConflict(
  hermesHome,
  opts: {
    now?: () => number
    maxAgeMs?: number
    kill?: typeof process.kill
  } = {}
) {
  const owner = readLiveUpdateMarker(hermesHome, opts)

  if (!owner) {
    return null
  }

  const mins = Math.floor(owner.ageMs / 60_000)
  const secs = Math.floor((owner.ageMs % 60_000) / 1000)
  const elapsed = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

  return {
    pid: owner.pid,
    ageMs: owner.ageMs,
    message: `An update is already running (PID ${owner.pid}, started ${elapsed} ago). Wait for it to finish, then try again.`
  }
}
