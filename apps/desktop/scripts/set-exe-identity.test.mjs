import assert from 'node:assert/strict'

import { test } from 'vitest'

import { normalizeWindowsVersion } from './set-exe-identity.mjs'

test('normalizes the Studio prerelease into a four-part Windows PE version', () => {
  assert.equal(normalizeWindowsVersion('0.17.0-omniroute.1'), '0.17.0.1')
})

test('normalizes stable and incomplete semantic versions', () => {
  assert.equal(normalizeWindowsVersion('2.4.6'), '2.4.6.0')
  assert.equal(normalizeWindowsVersion('3.2'), '3.2.0.0')
  assert.equal(normalizeWindowsVersion(undefined), '0.0.0.0')
})
