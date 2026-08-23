/**
 * Tests for electron/update-marker.ts — the in-app update mutual-exclusion
 * marker that prevents a desktop relaunched mid-update from spawning a backend
 * the updater then kills in a loop (#50238).
 *
 * Run with: node --test electron/update-marker.test.ts
 * (Wired into npm test:desktop:platforms in package.json.)
 *
 * Why this matters: the gate must (a) report a live update only when the
 * updater pid is alive AND the marker is fresh, (b) treat absent/malformed/
 * dead-pid/expired markers as "no live update" so a crashed updater can't
 * strand future launches, and (c) self-heal by deleting a stale marker file.
 */

import fs from 'fs'
import assert from 'node:assert/strict'
import os from 'os'
import path from 'path'

import { test } from 'vitest'

import {
  claimUpdateMarker,
  isPidAlive,
  markerPath,
  readLiveUpdateMarker,
  releaseUpdateMarker,
  UPDATE_MARKER_MAX_AGE_MS,
  updateHandoffConflict,
  writeUpdateMarker
} from './update-marker'

function tmpHome(tag) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `hermes-marker-${tag}-`))

  return dir
}

function writeMarker(home, pid, startedAtSec) {
  fs.writeFileSync(markerPath(home), `${pid}\n${startedAtSec}`)
}

const ALIVE: typeof process.kill = () => true // injected kill that "succeeds" => pid alive

const DEAD: typeof process.kill = () => {
  const err = new Error('no such process')

  ;(err as any).code = 'ESRCH'
  throw err
}

test('absent marker => no live update', () => {
  const home = tmpHome('absent')
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE }), null)
})

test('live pid within age ceiling => live update reported', () => {
  const home = tmpHome('live')
  const now = 1_000_000_000_000
  writeMarker(home, 4242, Math.floor(now / 1000) - 5) // 5s old
  const res = readLiveUpdateMarker(home, { kill: ALIVE, now: () => now })
  assert.ok(res, 'a fresh, alive marker is a live update')
  assert.equal(res.pid, 4242)
  assert.ok(res.ageMs >= 0 && res.ageMs < 10_000)
  assert.ok(fs.existsSync(markerPath(home)), 'a live marker is NOT deleted')
})

test('dead pid => no live update and marker is pruned', () => {
  const home = tmpHome('dead')
  writeMarker(home, 999999, Math.floor(Date.now() / 1000))
  assert.equal(readLiveUpdateMarker(home, { kill: DEAD }), null)
  assert.ok(!fs.existsSync(markerPath(home)), 'a dead-pid marker self-heals (deleted)')
})

test('expired marker (past age ceiling) => no live update and pruned', () => {
  const home = tmpHome('expired')
  const now = 1_000_000_000_000
  writeMarker(home, 4242, Math.floor((now - UPDATE_MARKER_MAX_AGE_MS - 60_000) / 1000))
  // Even though the pid is "alive", the marker is too old to trust.
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE, now: () => now }), null)
  assert.ok(!fs.existsSync(markerPath(home)), 'an expired marker self-heals (deleted)')
})

test('malformed marker => no live update and pruned', () => {
  const home = tmpHome('malformed')
  fs.writeFileSync(markerPath(home), 'not-a-pid\nnonsense')
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE }), null)
  assert.ok(!fs.existsSync(markerPath(home)))
})

test('isPidAlive: own pid is alive, impossible pid is dead', () => {
  assert.equal(isPidAlive(process.pid), true)
  assert.equal(isPidAlive(-1), false)
  assert.equal(isPidAlive(0), false)
  assert.equal(isPidAlive(NaN), false)
})

test('isPidAlive: EPERM counts as alive (process owned by another user)', () => {
  const eperm = () => {
    const err = new Error('operation not permitted')

    ;(err as any).code = 'EPERM'
    throw err
  }

  assert.equal(isPidAlive(4242, eperm), true)
})

test('writeUpdateMarker writes a marker that readLiveUpdateMarker accepts', () => {
  const home = tmpHome('write')
  const now = 1_000_000_000_000
  writeUpdateMarker(home, 4242, { now: () => now })
  // The marker should be readable and report the same pid.
  const res = readLiveUpdateMarker(home, { kill: ALIVE, now: () => now })
  assert.ok(res, 'marker written by writeUpdateMarker should be detected as live')
  assert.equal(res.pid, 4242)
  assert.ok(fs.existsSync(markerPath(home)), 'marker file should exist after write')
})

test('writeUpdateMarker preserves a live holder age across pid hand-off', () => {
  const home = tmpHome('write-handoff-age')
  const now = 1_000_000_000_000
  const startedAt = Math.floor(now / 1000) - 300

  writeMarker(home, 1010, startedAt)
  writeUpdateMarker(home, 2020, { kill: ALIVE, now: () => now })

  const [pidLine, startedLine] = fs.readFileSync(markerPath(home), 'utf8').split('\n')
  assert.equal(Number.parseInt(pidLine, 10), 2020, 'the hand-off records the new owner')
  assert.equal(Number.parseInt(startedLine, 10), startedAt, 'the holder age must not restart during hand-off')
})

test('writeUpdateMarker uses the acquisition time passed to a detached script', () => {
  const home = tmpHome('write-script-acquired-at')
  const now = 1_000_000_000_000
  const startedAt = Math.floor(now / 1000) - 300

  writeUpdateMarker(home, 2020, { now: () => now, startedAt })

  const [, startedLine] = fs.readFileSync(markerPath(home), 'utf8').split('\n')
  assert.equal(Number.parseInt(startedLine, 10), startedAt)
})

test('writeUpdateMarker is best-effort (no throw on bad path)', () => {
  // A non-existent directory should not throw.
  const badHome = path.join(os.tmpdir(), 'hermes-marker-nonexistent-' + Date.now())
  assert.doesNotThrow(() => writeUpdateMarker(badHome, 4242))
})

test('writeUpdateMarker + dead pid => self-heals on read', () => {
  const home = tmpHome('write-dead')
  writeUpdateMarker(home, 999999, { now: () => Date.now() })
  // PID 999999 is almost certainly not alive.
  const res = readLiveUpdateMarker(home, { kill: DEAD })
  assert.equal(res, null, 'a dead-pid marker from writeUpdateMarker self-heals')
  assert.ok(!fs.existsSync(markerPath(home)), 'marker file is pruned')
})

// ---------------------------------------------------------------------------
// updateHandoffConflict (#75778)
//
// A retried "Update" click must not spawn a second updater over a still-live
// one — writeUpdateMarker unconditionally overwrites the marker, so an
// unchecked hand-off clobbers the original updater's claim while it is still
// alive and mutating the checkout.
// ---------------------------------------------------------------------------

test('no marker => hand-off is not blocked', () => {
  const home = tmpHome('conflict-none')
  assert.equal(updateHandoffConflict(home, { kill: ALIVE }), null)
})

test('a different live updater already owns the marker => hand-off is blocked', () => {
  const home = tmpHome('conflict-live')
  const now = 1_000_000_000_000
  writeMarker(home, 1010, Math.floor(now / 1000) - 6) // 6s old
  const conflict = updateHandoffConflict(home, { kill: ALIVE, now: () => now })
  assert.ok(conflict, 'a live foreign updater must block a new hand-off')
  assert.equal(conflict.pid, 1010)
  assert.match(conflict.message, /already running/)
  assert.match(conflict.message, /PID 1010/)
  assert.match(conflict.message, /6s/)
})

test('a dead-pid marker does not block a hand-off (self-heals)', () => {
  const home = tmpHome('conflict-dead')
  writeMarker(home, 999999, Math.floor(Date.now() / 1000))
  assert.equal(updateHandoffConflict(home, { kill: DEAD }), null)
})

test('an expired marker does not block a hand-off (self-heals)', () => {
  const home = tmpHome('conflict-expired')
  const now = 1_000_000_000_000
  writeMarker(home, 1010, Math.floor((now - UPDATE_MARKER_MAX_AGE_MS - 60_000) / 1000))
  assert.equal(updateHandoffConflict(home, { kill: ALIVE, now: () => now }), null)
})

test('minutes-scale elapsed time is formatted as "Nm Ss"', () => {
  const home = tmpHome('conflict-minutes')
  const now = 1_000_000_000_000
  writeMarker(home, 1010, Math.floor(now / 1000) - 125) // 2m 5s old
  const conflict = updateHandoffConflict(home, { kill: ALIVE, now: () => now })
  assert.ok(conflict)
  assert.match(conflict.message, /2m 5s/)
})

// ── Atomic cross-process claim / release (TOCTOU fix) ──────────────────────
test('claimUpdateMarker: first claimant acquires; a concurrent second is BLOCKED (atomic O_EXCL)', () => {
  const home = tmpHome('claim-excl')
  const a = claimUpdateMarker(home, 111, { kill: ALIVE })
  const b = claimUpdateMarker(home, 222, { kill: ALIVE })
  assert.equal(a.acquired, true)
  assert.equal(b.acquired, false) // exactly one winner
  assert.equal(b.owner?.pid, 111)
})

test('claimUpdateMarker: a stale (dead-pid) marker is self-healed and re-claimable', () => {
  const home = tmpHome('claim-stale')
  writeMarker(home, 999, 1) // ancient + dead pid
  const c = claimUpdateMarker(home, 333, { kill: DEAD })
  assert.equal(c.acquired, true)
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE })?.pid, 333)
})

test('claimUpdateMarker: a LIVE owner is never stolen', () => {
  const home = tmpHome('claim-live')
  claimUpdateMarker(home, 111, { kill: ALIVE })
  assert.equal(claimUpdateMarker(home, 222, { kill: ALIVE }).acquired, false)
})

test('releaseUpdateMarker: only the OWNER pid releases; a handed-off (other pid) marker is kept', () => {
  const home = tmpHome('release-owner')
  claimUpdateMarker(home, 111, { kill: ALIVE })
  assert.equal(releaseUpdateMarker(home, 222), false)
  assert.ok(fs.existsSync(markerPath(home)))
  assert.equal(releaseUpdateMarker(home, 111), true)
  assert.equal(fs.existsSync(markerPath(home)), false)
  assert.equal(claimUpdateMarker(home, 333, { kill: ALIVE }).acquired, true) // no wedge after release
})

test('CANARY: N concurrent claimants yield exactly one winner (swapping wx for w would break this)', () => {
  const home = tmpHome('claim-canary')
  const wins = [1, 2, 3, 4, 5].map(p => claimUpdateMarker(home, p, { kill: ALIVE }).acquired).filter(Boolean)
  assert.equal(wins.length, 1)
})

// ── Atomic PUBLISH (no empty/partial window) — closes the create-then-populate
// hazard where a concurrent self-healing reader saw an empty marker, pruned it,
// and won a second claim over the same tree. The marker must be COMPLETE the
// instant it exists, and no temp file may be left behind.
test('claimUpdateMarker: the published marker is COMPLETE the instant it exists (never empty)', () => {
  const home = tmpHome('claim-atomic')
  const res = claimUpdateMarker(home, 4242, { kill: ALIVE })
  assert.equal(res.acquired, true)
  const raw = fs.readFileSync(markerPath(home), 'utf8')
  const [pidLine, startedLine] = raw.split('\n')
  assert.equal(Number.parseInt(pidLine, 10), 4242, 'marker carries the real pid, not an empty first line')
  assert.ok(Number.isFinite(Number.parseInt(startedLine, 10)), 'marker carries a startedAt line')
  // A reader immediately after the claim sees a LIVE marker (not a pruned empty one).
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE })?.pid, 4242)
})

test('claimUpdateMarker: leaves no temp/link litter next to the marker', () => {
  const home = tmpHome('claim-no-litter')
  claimUpdateMarker(home, 111, { kill: ALIVE }) // winner
  claimUpdateMarker(home, 222, { kill: ALIVE }) // loser (EEXIST) must clean its temp
  const stray = fs.readdirSync(home).filter(f => f.includes('.claim.') || f.includes('.tmp.'))
  assert.deepEqual(stray, [], `no temp files should remain, found: ${stray.join(', ')}`)
})

test('claimUpdateMarker: a loser (EEXIST) does not corrupt or empty the winner marker', () => {
  const home = tmpHome('claim-loser-safe')
  claimUpdateMarker(home, 111, { kill: ALIVE })
  const before = fs.readFileSync(markerPath(home), 'utf8')
  const loser = claimUpdateMarker(home, 222, { kill: ALIVE })
  assert.equal(loser.acquired, false)
  const after = fs.readFileSync(markerPath(home), 'utf8')
  assert.equal(after, before, 'the winner marker content is untouched by a losing claim')
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE })?.pid, 111)
})

test('writeUpdateMarker: publishes atomically and leaves no temp litter', () => {
  const home = tmpHome('write-atomic')
  writeUpdateMarker(home, 4242, { now: () => 1_000_000_000_000 })
  const stray = fs.readdirSync(home).filter(
    f => f.includes('.tmp.') || f.includes('.claim.') || f.includes('.reap.') || f.includes('.cs')
  )
  assert.deepEqual(stray, [], `no temp files should remain, found: ${stray.join(', ')}`)
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE, now: () => 1_000_000_000_000 })?.pid, 4242)
})

// ── Ownership transfer to the updater child (#50238 handoff) ────────────────
// The desktop claims with its OWN pid, then the child updater adopts the marker
// (writeUpdateMarker with the child pid). The desktop's finally release is
// owner-scoped, so it must NOT delete the child's transferred marker.
test('owner transfer: desktop claims, child adopts, desktop release keeps the child marker', () => {
  const home = tmpHome('owner-transfer')
  const DESKTOP = 111
  const CHILD = 222

  // 1. Desktop acquires the claim (marker holds the desktop pid).
  assert.equal(claimUpdateMarker(home, DESKTOP, { kill: ALIVE }).acquired, true)
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE })?.pid, DESKTOP)

  // 2. Child updater adopts the marker (records its own pid).
  writeUpdateMarker(home, CHILD)
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE })?.pid, CHILD)

  // 3. Desktop's finally release (owner-scoped to DESKTOP) must be a no-op now.
  assert.equal(releaseUpdateMarker(home, DESKTOP), false)
  assert.ok(fs.existsSync(markerPath(home)), 'the child-owned marker must survive the desktop release')
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE })?.pid, CHILD)

  // 4. The genuine owner (child) can still release it.
  assert.equal(releaseUpdateMarker(home, CHILD), true)
  assert.equal(fs.existsSync(markerPath(home)), false)
})

// A future-dated marker must be treated as stale (M2) so it can't wedge updates.
test('future-dated marker (negative age) is treated as stale and reclaimable', () => {
  const home = tmpHome('future-marker')
  const now = 1_000_000_000_000
  // startedAt 1 hour in the FUTURE.
  writeMarker(home, 4242, Math.floor(now / 1000) + 3600)
  assert.equal(readLiveUpdateMarker(home, { kill: ALIVE, now: () => now }), null)
  assert.equal(fs.existsSync(markerPath(home)), false, 'future-dated marker self-heals')
})
