import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import {
  installBundledCreativeSkill,
  installBundledDz23Guardrail,
  installBundledOmniRouteHealthScript,
  installBundledOmniRouteMcpBridge,
  installBundledProductStudioSkill,
  installManagedComponents,
  resolveStudioManagedPaths,
  uninstallManagedDirectory,
  uninstallManagedFile
} from './bundled-product-studio'

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-product-studio-'))
  const sourceRoot = path.join(root, 'source')
  const destinationRoot = path.join(root, 'destination')
  fs.mkdirSync(path.join(sourceRoot, 'references'), { recursive: true })
  fs.writeFileSync(path.join(sourceRoot, 'SKILL.md'), '# skill\n')
  fs.writeFileSync(path.join(sourceRoot, 'references', 'delivery-gates.md'), '# gates\n')

  return { destinationRoot, root, sourceRoot }
}

test('installs the bundled skill and records managed ownership', () => {
  const paths = fixture()

  try {
    assert.equal(installBundledProductStudioSkill({ ...paths, version: '1.0.0' }), 'installed')
    assert.equal(fs.readFileSync(path.join(paths.destinationRoot, 'SKILL.md'), 'utf8'), '# skill\n')
    assert.match(fs.readFileSync(path.join(paths.destinationRoot, '.omniroute-managed.json'), 'utf8'), /1\.0\.0/)
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('installs a complete nested creative skill bundle without executing it', () => {
  const paths = fixture()

  try {
    const nestedSkill = path.join(paths.sourceRoot, 'gsap-core')
    fs.mkdirSync(path.join(nestedSkill, 'references'), { recursive: true })
    fs.writeFileSync(path.join(nestedSkill, 'SKILL.md'), '# gsap core\n')
    fs.writeFileSync(path.join(nestedSkill, 'references', 'api.md'), '# api\n')

    assert.equal(installBundledCreativeSkill({ ...paths, version: '1.0.0' }), 'installed')
    assert.equal(
      fs.readFileSync(path.join(paths.destinationRoot, 'gsap-core', 'references', 'api.md'), 'utf8'),
      '# api\n'
    )
    assert.match(fs.readFileSync(path.join(paths.destinationRoot, '.omniroute-managed.json'), 'utf8'), /third-party/)
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('updates only a directory previously marked as managed', () => {
  const paths = fixture()

  try {
    fs.mkdirSync(paths.destinationRoot, { recursive: true })
    fs.writeFileSync(path.join(paths.destinationRoot, 'SKILL.md'), '# user skill\n')

    assert.equal(installBundledProductStudioSkill({ ...paths, version: '1.0.0' }), 'skipped-unmanaged')
    assert.equal(fs.readFileSync(path.join(paths.destinationRoot, 'SKILL.md'), 'utf8'), '# user skill\n')

    fs.writeFileSync(path.join(paths.destinationRoot, '.omniroute-managed.json'), '{}\n')
    assert.equal(installBundledProductStudioSkill({ ...paths, version: '1.1.0' }), 'updated')
    assert.equal(fs.readFileSync(path.join(paths.destinationRoot, 'SKILL.md'), 'utf8'), '# skill\n')
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('installs the deterministic guardrail bundle', () => {
  const paths = fixture()

  try {
    fs.writeFileSync(path.join(paths.sourceRoot, 'plugin.yaml'), 'name: dz23-guardrail\n')
    fs.writeFileSync(path.join(paths.sourceRoot, '__init__.py'), 'def register(ctx): pass\n')

    assert.equal(installBundledDz23Guardrail({ ...paths, version: '1.0.0' }), 'installed')
    assert.match(fs.readFileSync(path.join(paths.destinationRoot, 'plugin.yaml'), 'utf8'), /dz23-guardrail/)
    assert.match(fs.readFileSync(path.join(paths.destinationRoot, '.omniroute-managed.json'), 'utf8'), /guardrail/)
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('installs and safely updates the managed OmniRoute MCP bridge', () => {
  const paths = fixture()
  const sourcePath = path.join(paths.sourceRoot, 'omniroute-mcp-bridge.mjs')
  const destinationPath = path.join(paths.destinationRoot, 'integrations', 'omniroute-mcp-bridge.mjs')

  try {
    fs.writeFileSync(sourcePath, '#!/usr/bin/env node\n')

    assert.equal(installBundledOmniRouteMcpBridge({ destinationPath, sourcePath, version: '1.0.0' }), 'installed')
    assert.equal(fs.readFileSync(destinationPath, 'utf8'), '#!/usr/bin/env node\n')
    assert.match(fs.readFileSync(`${destinationPath}.managed.json`, 'utf8'), /MCP bridge/)

    fs.writeFileSync(sourcePath, '#!/usr/bin/env node\n// v2\n')
    assert.equal(installBundledOmniRouteMcpBridge({ destinationPath, sourcePath, version: '2.0.0' }), 'updated')
    assert.match(fs.readFileSync(destinationPath, 'utf8'), /v2/)
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('does not replace an unmanaged file at the MCP bridge path', () => {
  const paths = fixture()
  const sourcePath = path.join(paths.sourceRoot, 'omniroute-mcp-bridge.mjs')
  const destinationPath = path.join(paths.destinationRoot, 'integrations', 'omniroute-mcp-bridge.mjs')

  try {
    fs.mkdirSync(path.dirname(destinationPath), { recursive: true })
    fs.writeFileSync(sourcePath, '// bundled\n')
    fs.writeFileSync(destinationPath, '// user owned\n')

    assert.equal(
      installBundledOmniRouteMcpBridge({ destinationPath, sourcePath, version: '1.0.0' }),
      'skipped-unmanaged'
    )
    assert.equal(fs.readFileSync(destinationPath, 'utf8'), '// user owned\n')
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('installs the managed OmniRoute daily health script', () => {
  const paths = fixture()
  const sourcePath = path.join(paths.sourceRoot, 'omniroute-daily-health.py')
  const destinationPath = path.join(paths.destinationRoot, 'scripts', 'omniroute-daily-health.py')

  try {
    fs.writeFileSync(sourcePath, 'print("healthy")\n')

    assert.equal(installBundledOmniRouteHealthScript({ destinationPath, sourcePath, version: '1.0.0' }), 'installed')
    assert.equal(fs.readFileSync(destinationPath, 'utf8'), 'print("healthy")\n')
    assert.match(fs.readFileSync(`${destinationPath}.managed.json`, 'utf8'), /health check/)
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('bundle install failure is isolated and reported without stopping later installs', () => {
  let laterInstallRan = false

  const state = installManagedComponents({
    broken: () => {
      throw new Error('simulated EACCES')
    },
    healthy: () => {
      laterInstallRan = true

      return 'installed'
    }
  })

  assert.equal(state.broken.status, 'failed')
  assert.match(state.broken.status === 'failed' ? state.broken.error : '', /EACCES/)
  assert.deepEqual(state.healthy, { status: 'ready', result: 'installed' })
  assert.equal(laterInstallRan, true)
})

test('Studio-managed executable components never target the active Hermes runtime', () => {
  const hermesHome = path.join(os.tmpdir(), 'hermes-home')
  const activeRuntime = path.join(hermesHome, 'hermes-agent')
  const managed = resolveStudioManagedPaths(hermesHome)

  for (const target of [
    managed.guardrailRoot,
    managed.healthScriptPath,
    managed.mcpBridgePath,
    managed.mcpPolicyPath
  ]) {
    assert.equal(path.relative(activeRuntime, target).startsWith('..'), true)
    assert.equal(path.relative(managed.root, target).startsWith('..'), false)
  }
})

test('managed bundle creates a timestamped backup before an update', () => {
  const paths = fixture()

  try {
    assert.equal(installBundledProductStudioSkill({ ...paths, version: '1.0.0' }), 'installed')
    fs.writeFileSync(path.join(paths.destinationRoot, 'SKILL.md'), '# previous managed skill\n')
    fs.writeFileSync(path.join(paths.sourceRoot, 'SKILL.md'), '# next managed skill\n')

    assert.equal(installBundledProductStudioSkill({ ...paths, version: '2.0.0' }), 'updated')

    const backupRoot = path.join(path.dirname(paths.destinationRoot), '.omniroute-backups')
    const snapshots = fs.readdirSync(backupRoot)
    assert.equal(snapshots.length, 1)
    assert.match(snapshots[0] ?? '', /^\d{8}T\d{6}\.\d{3}Z-/)
    assert.equal(
      fs.readFileSync(path.join(backupRoot, snapshots[0]!, path.basename(paths.destinationRoot), 'SKILL.md'), 'utf8'),
      '# previous managed skill\n'
    )
    assert.equal(fs.readFileSync(path.join(paths.destinationRoot, 'SKILL.md'), 'utf8'), '# next managed skill\n')
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})

test('managed uninstall removes owned components but preserves unmanaged paths', () => {
  const paths = fixture()
  const managedFile = path.join(paths.destinationRoot, 'managed.mjs')
  const unmanagedFile = path.join(paths.root, 'user-owned.mjs')

  try {
    assert.equal(installBundledProductStudioSkill({ ...paths, version: '1.0.0' }), 'installed')
    fs.mkdirSync(path.dirname(managedFile), { recursive: true })
    fs.writeFileSync(managedFile, '// managed\n')
    fs.writeFileSync(`${managedFile}.managed.json`, '{}\n')
    fs.writeFileSync(unmanagedFile, '// user\n')

    assert.equal(uninstallManagedFile(managedFile), true)
    assert.equal(fs.existsSync(managedFile), false)
    assert.equal(uninstallManagedFile(unmanagedFile), false)
    assert.equal(fs.existsSync(unmanagedFile), true)
    assert.equal(uninstallManagedDirectory(paths.destinationRoot), true)
    assert.equal(fs.existsSync(paths.destinationRoot), false)
  } finally {
    fs.rmSync(paths.root, { recursive: true, force: true })
  }
})
