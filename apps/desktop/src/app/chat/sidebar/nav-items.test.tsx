import { describe, expect, it } from 'vitest'

import { en } from '@/i18n/en'
import { ptBr } from '@/i18n/pt-br'

import { AGENTS_ROUTE, ARTIFACTS_ROUTE, CRON_ROUTE, MESSAGING_ROUTE, SKILLS_ROUTE, STARMAP_ROUTE } from '../../routes'

import { SIDEBAR_NAV } from './nav-items'

describe('SIDEBAR_NAV', () => {
  it('leads with New session and surfaces Agents right after it', () => {
    expect(SIDEBAR_NAV[0].id).toBe('new-session')
    expect(SIDEBAR_NAV[1].id).toBe('agents')
  })

  it('routes Agents to the live AGENTS_ROUTE (a real destination, not a dead button)', () => {
    const agents = SIDEBAR_NAV.find(item => item.id === 'agents')
    expect(agents).toBeDefined()
    expect(agents?.route).toBe(AGENTS_ROUTE)
    expect(agents?.keybindActionId).toBe('nav.agents')
  })

  it('surfaces Memory (starmap) as a live destination', () => {
    const memory = SIDEBAR_NAV.find(item => item.id === 'starmap')
    expect(memory).toBeDefined()
    expect(memory?.route).toBe(STARMAP_ROUTE)
  })

  it('every route-backed row points at a defined app route', () => {
    const knownRoutes = new Set([AGENTS_ROUTE, SKILLS_ROUTE, MESSAGING_ROUTE, ARTIFACTS_ROUTE, CRON_ROUTE, STARMAP_ROUTE])
    for (const item of SIDEBAR_NAV) {
      if (item.route) {
        expect(knownRoutes.has(item.route)).toBe(true)
      } else {
        // the only actionless-but-routeless row is the New session action
        expect(item.action).toBe('new-session')
      }
    }
  })

  it('has an i18n label for every nav id in both en and pt-BR', () => {
    for (const item of SIDEBAR_NAV) {
      expect(en.sidebar.nav[item.id], `en label for ${item.id}`).toBeTruthy()
      expect(ptBr.sidebar.nav[item.id], `pt-BR label for ${item.id}`).toBeTruthy()
    }
  })

  it('translates the Agents label to pt-BR (not left in English)', () => {
    expect(en.sidebar.nav.agents).toBe('Agents')
    expect(ptBr.sidebar.nav.agents).toBe('Agentes')
  })
})
