import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import {
  installBundledDz23Guardrail,
  installBundledOmniRouteHealthScript,
  installBundledOmniRouteMcpBridge,
  installBundledProductStudioSkill
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
