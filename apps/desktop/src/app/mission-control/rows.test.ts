/**
 * A projeção do Mission Control — ordenação, filtro e ações permitidas.
 *
 * O painel só vale se a primeira linha for a que precisa de uma pessoa. Estes
 * testes travam essa promessa contra o caso que a motiva: várias sessões
 * trabalhando ao mesmo tempo, uma delas com um processo morto.
 */

import { describe, expect, it } from 'vitest'

import type { ClientSessionState } from '@/app/types'
import type { ComposerStatusItem } from '@/store/composer-status'

import { buildMissionGroups, canDismiss, canStop, summarize } from './rows'

const item = (over: Partial<ComposerStatusItem> = {}): ComposerStatusItem => ({
  id: 'i1',
  state: 'running',
  title: 'npm test',
  type: 'background',
  ...over
})

const state = (storedSessionId: null | string) =>
  ({ storedSessionId }) as unknown as ClientSessionState

const titleFor = (stored: null | string, runtime: string) => stored ?? runtime

describe('buildMissionGroups', () => {
  it('agrupa por sessão e conta o que está rodando e o que falhou', () => {
    const groups = buildMissionGroups(
      {
        's-1': [item({ id: 'a' }), item({ id: 'b', state: 'failed' }), item({ id: 'c', state: 'done' })]
      },
      { 's-1': state('stored-1') },
      titleFor
    )

    expect(groups).toHaveLength(1)
    expect(groups[0]).toMatchObject({ failed: 1, running: 1, runtimeId: 's-1', storedId: 'stored-1' })
    expect(groups[0]!.items).toHaveLength(3)
  })

  it('descarta todos: são o checklist do turno, não trabalho de fundo', () => {
    const groups = buildMissionGroups(
      { 's-1': [item({ id: 't', type: 'todo' }), item({ id: 'b' })] },
      { 's-1': state('stored-1') },
      titleFor
    )

    expect(groups[0]!.items.map(i => i.id)).toEqual(['b'])
  })

  it('omite a sessão que só tinha todos, em vez de mostrar um grupo vazio', () => {
    const groups = buildMissionGroups(
      { 's-1': [item({ type: 'todo' })] },
      { 's-1': state('stored-1') },
      titleFor
    )

    expect(groups).toEqual([])
  })

  it('mantém goals e subagentes, que são trabalho', () => {
    const groups = buildMissionGroups(
      {
        's-1': [
          item({ id: 'g', type: 'goal', goalStatus: 'active' }),
          item({ id: 's', type: 'subagent' })
        ]
      },
      { 's-1': state('stored-1') },
      titleFor
    )

    expect(groups[0]!.items.map(i => i.type)).toEqual(['goal', 'subagent'])
  })

  it('põe a falha ANTES do que está rodando', () => {
    // Falha para de mudar sozinha; execução ainda pode terminar bem. Ordenar
    // pelo mais barulhento enterraria justamente a linha que precisa de alguém.
    const groups = buildMissionGroups(
      {
        'rodando': [item({ id: 'r1' }), item({ id: 'r2' })],
        'falhou': [item({ id: 'f1', state: 'failed' })]
      },
      { 'rodando': state('a'), 'falhou': state('b') },
      titleFor
    )

    expect(groups.map(g => g.runtimeId)).toEqual(['falhou', 'rodando'])
  })

  it('desempata por título, para a lista não dançar entre renders', () => {
    const groups = buildMissionGroups(
      { 'z': [item({ state: 'done' })], 'a': [item({ state: 'done' })] },
      { 'z': state('z-title'), 'a': state('a-title') },
      titleFor
    )

    expect(groups.map(g => g.title)).toEqual(['a-title', 'z-title'])
  })

  it('sobrevive a uma sessão sem id armazenado (chat novo, ainda não persistido)', () => {
    const groups = buildMissionGroups({ 'runtime-1': [item()] }, {}, titleFor)

    expect(groups[0]!.storedId).toBeNull()
    expect(groups[0]!.title).toBe('runtime-1')
  })
})

describe('summarize', () => {
  it('soma o que o cabeçalho do painel mostra', () => {
    const groups = buildMissionGroups(
      {
        's-1': [item({ id: 'a' }), item({ id: 'b', state: 'failed' })],
        's-2': [item({ id: 'c' })]
      },
      { 's-1': state('1'), 's-2': state('2') },
      titleFor
    )

    expect(summarize(groups)).toMatchObject({ failed: 1, running: 2, sessions: 2 })
  })

  it('zera limpo quando não há nada rodando', () => {
    expect(summarize([])).toMatchObject({ failed: 0, running: 0, sessions: 0 })
  })
})

describe('ações permitidas', () => {
  it('só oferece parar para processo de fundo em execução', () => {
    expect(canStop(item())).toBe(true)
    expect(canStop(item({ state: 'done' }))).toBe(false)
    // Um botão "parar" num subagente ou num goal seria um botão que mente:
    // eles terminam pelo próprio ciclo.
    expect(canStop(item({ type: 'subagent' }))).toBe(false)
    expect(canStop(item({ type: 'goal' }))).toBe(false)
  })

  it('só oferece dispensar para linha já encerrada', () => {
    expect(canDismiss(item({ state: 'done' }))).toBe(true)
    expect(canDismiss(item({ state: 'failed' }))).toBe(true)
    expect(canDismiss(item())).toBe(false)
    expect(canDismiss(item({ type: 'subagent', state: 'done' }))).toBe(false)
  })
})
