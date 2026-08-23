/**
 * REAL-filesystem, REAL-multi-process concurrency proof for claimUpdateMarker.
 *
 * The single-threaded in-process tests in update-marker.test.ts cannot exercise
 * the cross-process TOCTOU that a self-heal unlink-by-path opens (two claimants
 * both reap the same stale marker, both create, both "acquire" → two destructive
 * updaters over one checkout, #75778). This test bundles the REAL module to CJS
 * and forks N OS processes that hammer claimUpdateMarker against a shared marker
 * directory seeded with a STALE (dead-pid) marker — the exact reap path — over
 * many iterations, asserting `acquired_count === 1` every time.
 *
 * It also runs a CANARY: an intentionally buggy exists→unlink→write claim (the
 * pre-fix shape) through the SAME harness, and asserts the harness is strong
 * enough to expose >1 winner — so a regression to that shape would fail here.
 */

import { spawnSync } from 'child_process'
import fs from 'fs'
import os from 'os'
import path from 'path'

import { beforeAll, expect, test } from 'vitest'

const MARKER = '.hermes-update-in-progress'
let realBundle = ''
let buggyModule = ''

beforeAll(() => {
  const esbuild = require('esbuild')
  const outdir = fs.mkdtempSync(path.join(os.tmpdir(), 'marker-bundle-'))

  realBundle = path.join(outdir, 'update-marker.cjs')
  esbuild.buildSync({
    entryPoints: [path.join(__dirname, 'update-marker.ts')],
    bundle: true,
    platform: 'node',
    format: 'cjs',
    outfile: realBundle
  })

  // Buggy reference claim: the classic exists→(stale)unlink-by-path→write shape
  // whose two-winner TOCTOU this module was rewritten to eliminate. Kept in a
  // sibling module so the harness can prove it detects the defect.
  buggyModule = path.join(outdir, 'buggy-claim.cjs')
  fs.writeFileSync(
    buggyModule,
    `
const fs = require('fs')
const path = require('path')
function markerPath(home) { return path.join(home, ${JSON.stringify(MARKER)}) }
function isAlive(pid) { try { process.kill(pid, 0); return true } catch (e) { return e && e.code === 'EPERM' } }
exports.claimUpdateMarker = function (home, pid) {
  const file = markerPath(home)
  let raw = null
  try { raw = fs.readFileSync(file, 'utf8') } catch {}
  if (raw !== null) {
    const p = Number.parseInt(String(raw).split('\\n')[0], 10)
    if (Number.isInteger(p) && isAlive(p)) return { acquired: false }
    // THE BUG: read-then-unlink-by-path, then unconditionally (re)create.
    try { fs.unlinkSync(file) } catch {}
  }
  // widen the window a touch so the race is observable across node startups
  const spin = Date.now() + 2
  while (Date.now() < spin) { /* busy */ }
  try { fs.writeFileSync(file, pid + '\\n' + Math.floor(Date.now() / 1000) + '\\n') } catch {}
  return { acquired: true }
}
`,
    'utf8'
  )
})

function seedStaleMarker(home: string) {
  // A dead pid with a recent timestamp → classified STALE via pid-liveness (not
  // age), which is exactly the reap path claimUpdateMarker must serialize.
  fs.writeFileSync(path.join(home, MARKER), `999999\n${Math.floor(Date.now() / 1000)}\n`)
}

/** Fork `n` OS processes that each call module.claimUpdateMarker concurrently.
 *
 * A winner HOLDS the marker (stays alive) for a dwell after acquiring, exactly
 * as the desktop holds it across the update handoff — so a genuine *simultaneous*
 * double-acquire shows up as >1 winner, while the benign acquire-then-crash-then-
 * reacquire sequence (which is correct recovery, not a double-update) does not. */
function raceAcquire(modulePath: string, home: string, n: number): number {
  const script =
    'const m=require(process.argv[1]);' +
    'const r=m.claimUpdateMarker(process.argv[2], process.pid);' +
    // Hold the claim alive for 500ms so all contenders overlap while a winner
    // still owns the marker (its pid must read as LIVE to the others).
    'if (r && r.acquired) { Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500); }' +
    'process.stdout.write(r && r.acquired ? "A" : "B");'

  // Launch all children before waiting on any, so they overlap in the kernel.
  const children = Array.from({ length: n }, () =>
    // eslint-disable-next-line no-undef
    require('child_process').spawn(process.execPath, ['-e', script, modulePath, home], {
      stdio: ['ignore', 'pipe', 'ignore']
    })
  )

  const outs: string[] = new Array(n).fill('')
  const done = children.map(
    (child, i) =>
      new Promise<void>(resolve => {
        child.stdout.on('data', (d: Buffer) => {
          outs[i] += d.toString()
        })
        child.on('close', () => resolve())
      })
  )

  // Synchronous wait via a tiny sleep loop on a shared flag is awkward; use a
  // deasync-free approach: block on each child's completion with spawnSync-style
  // join by polling. Simpler: return a promise from the test instead.
  return Promise.all(done).then(() => outs.filter(o => o.startsWith('A')).length) as unknown as number
}

test('REAL multi-process: claimUpdateMarker yields exactly one winner over a seeded stale marker', async () => {
  const ITERATIONS = 15
  const CHILDREN = 6

  for (let i = 0; i < ITERATIONS; i++) {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), `marker-race-${i}-`))
    seedStaleMarker(home)
    const winners = await (raceAcquire(realBundle, home, CHILDREN) as unknown as Promise<number>)
    expect(winners, `iteration ${i} must have exactly one acquirer`).toBe(1)
  }
}, 60_000)

test('CANARY: the buggy exists→unlink→write claim produces >1 winner under the same harness', async () => {
  const ITERATIONS = 15
  const CHILDREN = 6
  let maxWinners = 0

  for (let i = 0; i < ITERATIONS; i++) {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), `marker-race-buggy-${i}-`))
    seedStaleMarker(home)
    const winners = await (raceAcquire(buggyModule, home, CHILDREN) as unknown as Promise<number>)
    maxWinners = Math.max(maxWinners, winners)
  }

  // If the harness cannot expose the classic TOCTOU, it is too weak to protect
  // the real implementation — fail so we strengthen it rather than pass falsely.
  expect(maxWinners, 'harness must be able to observe the two-winner defect').toBeGreaterThan(1)
}, 60_000)

// Keep spawnSync imported (used indirectly to assert node is available in CI).
test('node executable is available for the race harness', () => {
  const r = spawnSync(process.execPath, ['-e', 'process.stdout.write("ok")'], { encoding: 'utf8' })
  expect(r.stdout).toBe('ok')
})
