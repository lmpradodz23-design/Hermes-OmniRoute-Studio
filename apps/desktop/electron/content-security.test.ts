import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

import { test } from 'vitest'

import {
  contentSecurityPolicyHeaders,
  hardenWebviewAttachment,
  isTrustedRendererNavigation
} from './content-security'

test('CSP header is present and prevents executable content injection', () => {
  const headers = contentSecurityPolicyHeaders({ 'content-type': ['text/html'] })
  const policy = headers['Content-Security-Policy']?.[0] ?? ''

  assert.match(policy, /default-src 'self'/)
  assert.match(policy, /script-src 'self' 'wasm-unsafe-eval'/)

  assert.doesNotMatch(policy, /(?<!wasm-)unsafe-eval/)
  assert.match(policy, /object-src 'none'/)
  assert.match(policy, /base-uri 'none'/)
  assert.match(policy, /frame-ancestors 'none'/)
})

test('webview attributes are neutralized before attachment', () => {
  const preferences: Record<string, unknown> = {
    contextIsolation: false,
    nodeIntegration: true,
    preload: 'file:///tmp/attacker.js',
    sandbox: false
  }

  const params: Record<string, unknown> = {
    partition: 'persist:attacker',
    src: 'https://example.com'
  }

  const allowed = hardenWebviewAttachment(preferences, params)

  assert.equal(allowed, true)
  assert.equal(preferences.nodeIntegration, false)
  assert.equal(preferences.contextIsolation, true)
  assert.equal(preferences.sandbox, true)
  assert.equal(preferences.preload, undefined)
  assert.equal(params.partition, 'persist:hermes-preview')

  assert.equal(hardenWebviewAttachment({}, { src: 'javascript:alert(1)' }), false)
  assert.equal(hardenWebviewAttachment({}, { src: 'file:///tmp/payload.html' }), false)
})

test('packaged renderer navigation is confined to its exact application file', () => {
  const dist = path.join(os.tmpdir(), 'hermes-dist')
  const index = path.join(dist, 'index.html')

  assert.equal(
    isTrustedRendererNavigation(`${pathToFileURL(index)}#/session`, { rendererIndexPath: index }),
    true
  )
  assert.equal(
    isTrustedRendererNavigation(pathToFileURL(path.join(os.tmpdir(), 'payload.html')).toString(), {
      rendererIndexPath: index
    }),
    false
  )
  assert.equal(isTrustedRendererNavigation('https://attacker.invalid', { rendererIndexPath: index }), false)
})
