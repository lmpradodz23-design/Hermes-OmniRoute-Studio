import { describe, expect, it } from 'vitest'

import {
  canDeclareConnected,
  canSend,
  deriveWhatsAppView,
  mapSessionState,
  needsHumanQr,
  WhatsAppUiStatus
} from './whatsapp-surface'

describe('mapSessionState', () => {
  it('maps every real backend state 1:1', () => {
    expect(mapSessionState('connected')).toBe(WhatsAppUiStatus.CONNECTED)
    expect(mapSessionState('qr_required')).toBe(WhatsAppUiStatus.QR_REQUIRED)
    expect(mapSessionState('degraded')).toBe(WhatsAppUiStatus.DEGRADED)
    expect(mapSessionState('disconnected')).toBe(WhatsAppUiStatus.DISCONNECTED)
    expect(mapSessionState('logged_out')).toBe(WhatsAppUiStatus.AUTH_REQUIRED)
  })

  it('never maps a non-connected state to CONNECTED (no fake connection)', () => {
    for (const s of ['disconnected', 'starting', 'qr_required', 'authenticating', 'reconnecting', 'failed', 'logged_out']) {
      expect(mapSessionState(s)).not.toBe(WhatsAppUiStatus.CONNECTED)
    }
  })

  it('fails closed on an unknown state', () => {
    expect(mapSessionState('totally-bogus')).toBe(WhatsAppUiStatus.FAILED)
    expect(mapSessionState('')).toBe(WhatsAppUiStatus.FAILED)
  })
})

describe('guardrails', () => {
  it('canDeclareConnected only for real CONNECTED', () => {
    expect(canDeclareConnected(WhatsAppUiStatus.CONNECTED)).toBe(true)
    expect(canDeclareConnected(WhatsAppUiStatus.QR_REQUIRED)).toBe(false)
    expect(canDeclareConnected(WhatsAppUiStatus.DEGRADED)).toBe(false)
  })

  it('canSend only when connected or degraded', () => {
    expect(canSend(WhatsAppUiStatus.CONNECTED)).toBe(true)
    expect(canSend(WhatsAppUiStatus.DEGRADED)).toBe(true)
    expect(canSend(WhatsAppUiStatus.QR_REQUIRED)).toBe(false)
    expect(canSend(WhatsAppUiStatus.AUTH_REQUIRED)).toBe(false)
  })

  it('surfaces the human QR gate without blocking the rest of U1', () => {
    expect(needsHumanQr(WhatsAppUiStatus.QR_REQUIRED)).toBe(true)
    expect(deriveWhatsAppView('qr_required').blocker).toBe('WAITING_FOR_HUMAN_QR_SCAN')
    expect(deriveWhatsAppView('connected').blocker).toBeNull()
  })
})
