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

/**
 * Fork `n` OS processes that each call module.claimUpdateMarker under a strict
 * BARRIER so they contend simultaneously, and where a winner HOLDS the marker
 * until every contender has recorded a result. This makes the concurrency test
 * DETERMINISTIC rather than dependent on process-spawn timing:
 *
 *   - Barrier: every child busy-waits until a shared wall-clock `startAt`, so
 *     they all enter claimUpdateMarker at the same instant (maximum contention).
 *     This is the opposite of "serializing artificially" - it forces overlap
 *     even on Windows, where spawning node.exe is slow and staggered.
 *   - Coordinated hold: the winner stays alive (its pid must read LIVE to the
 *     others) until all `n` result files exist, so a benign acquire-then-exit
 *     can never masquerade as a second winner, and a genuine simultaneous
 *     double-acquire always shows as >1.
 *   - Instrumentation: each child writes `<pid>.res` = "A pid=.. t=.." so a
 *     failing iteration can be dumped for post-mortem of the real interleaving.
 *
 * Returns { winners, dump } where dump is the per-child records (for diagnosis).
 */
function raceAcquire(
  modulePath: string,
  home: string,
  n: number
): Promise<{ winners: number; dump: string }> {
  const resultsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'marker-res-'))
  const startAt = Date.now() + 1500 // barrier: ample time for all children to spawn (Windows-slow)
  const holdMs = 9000

  const script = [
    'const m=require(process.argv[1]);',
    'const home=process.argv[2];',
    'const startAt=Number(process.argv[3]);',
    'const n=Number(process.argv[4]);',
    'const dir=process.argv[5];',
    'const fs=require("fs"),path=require("path");',
    'const mypid=process.pid;',
    // BARRIER: all children spin until the shared start instant.
    'while(Date.now()<startAt){}',
    'const t0=Date.now();',
    'const r=m.claimUpdateMarker(home, mypid);',
    'const acquired=!!(r&&r.acquired);',
    'try{fs.writeFileSync(path.join(dir,mypid+".res"),(acquired?"A":"B")+" pid="+mypid+" t="+(Date.now()-t0)+"ms owner="+(r&&r.owner?JSON.stringify(r.owner):"-")+"\\n");}catch(e){}',
    // COORDINATED HOLD: the winner stays alive until every child has recorded,
    // so it is provably alive during all contenders' attempts.
    'if(acquired){const dl=Date.now()+' + holdMs + ';for(;;){let c=0;try{c=fs.readdirSync(dir).filter(f=>f.endsWith(".res")).length;}catch(e){}if(c>=n||Date.now()>dl)break;const s=Date.now()+5;while(Date.now()<s){}}}',
    'process.stdout.write(acquired?"A":"B");'
  ].join('')

  const children = Array.from({ length: n }, () =>
    // eslint-disable-next-line no-undef
    require('child_process').spawn(
      process.execPath,
      ['-e', script, modulePath, home, String(startAt), String(n), resultsDir],
      { stdio: ['ignore', 'pipe', 'ignore'] }
    )
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

  return Promise.all(done).then(() => {
    const winners = outs.filter(o => o.startsWith('A')).length
    let dump = ''
    try {
      for (const f of fs.readdirSync(resultsDir).filter(x => x.endsWith('.res'))) {
        dump += fs.readFileSync(path.join(resultsDir, f), 'utf8')
      }
    } catch {
      void 0
    }
    return { winners, dump }
  })
}

test('REAL multi-process: claimUpdateMarker yields exactly one winner over a seeded stale marker', async () => {
  const ITERATIONS = 20
  const CHILDREN = 6

  for (let i = 0; i < ITERATIONS; i++) {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), `marker-race-${i}-`))
    seedStaleMarker(home)
    const { winners, dump } = await raceAcquire(realBundle, home, CHILDREN)
    expect(winners, `iteration ${i} must have exactly one acquirer. Interleaving:\n${dump}`).toBe(1)
  }
}, 120_000)

test('CANARY: the buggy exists->unlink->write claim produces >1 winner under the same harness', async () => {
  const ITERATIONS = 10
  const CHILDREN = 6
  let maxWinners = 0

  for (let i = 0; i < ITERATIONS; i++) {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), `marker-race-buggy-${i}-`))
    seedStaleMarker(home)
    const { winners } = await raceAcquire(buggyModule, home, CHILDREN)
    maxWinners = Math.max(maxWinners, winners)
  }

  // If the harness cannot expose the classic TOCTOU, it is too weak to protect
  // the real implementation - fail so we strengthen it rather than pass falsely.
  expect(maxWinners, 'harness must be able to observe the two-winner defect').toBeGreaterThan(1)
}, 120_000)

// Keep spawnSync imported (used indirectly to assert node is available in CI).
test('node executable is available for the race harness', () => {
  const r = spawnSync(process.execPath, ['-e', 'process.stdout.write("ok")'], { encoding: 'utf8' })
  expect(r.stdout).toBe('ok')
})
