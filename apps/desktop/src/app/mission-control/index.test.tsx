/**
 * O painel Mission Control renderizado contra os stores REAIS.
 *
 * A projeção já é testada isolada em `rows.test.ts`. O que estes testes trancam
 * é o que só quebra na montagem: o painel lê `$statusItemsBySession` (um
 * `computed` sobre goals/subagentes/background/todos), então preencher o store
 * de origem tem que aparecer na tela — e os botões destrutivos têm que chamar
 * as ações certas com o id de RUNTIME, não com o id armazenado. Trocar um pelo
 * outro mataria o processo errado, e nada na UI denunciaria.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as ComposerStatus from '@/store/composer-status'
import { $backgroundStatusBySession } from '@/store/composer-status'
import { $sessionStates } from '@/store/session-states'

import { MissionControlPane } from './index'

const stopBackgroundProcess = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
const dismissBackgroundProcess = vi.hoisted(() => vi.fn())
const refreshBackgroundProcesses = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
const refreshAllBackgroundProcesses = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))

type ComposerStatusModule = typeof ComposerStatus

vi.mock('@/store/composer-status', async importOriginal => {
  const actual = await importOriginal<ComposerStatusModule>()

  return {
    ...actual,
    dismissBackgroundProcess,
    refreshAllBackgroundProcesses,
    refreshBackgroundProcesses,
    stopBackgroundProcess
  }
})

const running = {
  id: 'proc-1',
  state: 'running' as const,
  title: 'npm run build',
  type: 'background' as const
}

const failed = {
  exitCode: 1,
  id: 'proc-2',
  state: 'failed' as const,
  title: 'pytest -q',
  type: 'background' as const
}

describe('MissionControlPane', () => {
  beforeEach(() => {
    $backgroundStatusBySession.set({})
    $sessionStates.set({})
    stopBackgroundProcess.mockClear()
    dismissBackgroundProcess.mockClear()
    refreshBackgroundProcesses.mockClear()
    refreshAllBackgroundProcesses.mockClear()
  })

  afterEach(() => {
    cleanup()
    $backgroundStatusBySession.set({})
    $sessionStates.set({})
  })

  it('mostra o estado vazio quando nada está rodando', () => {
    render(<MissionControlPane />)

    expect(screen.getByText('Nothing running')).toBeTruthy()
  })

  it('lista trabalho de fundo de mais de uma sessão ao mesmo tempo', () => {
    // É a razão de o painel existir: com cinco sessões trabalhando, a status
    // stack do composer só mostra a sessão aberta.
    $backgroundStatusBySession.set({ 'rt-1': [running], 'rt-2': [failed] })

    render(<MissionControlPane />)

    expect(screen.getByText('npm run build')).toBeTruthy()
    expect(screen.getByText('pytest -q')).toBeTruthy()
  })

  it('resume o total no cabeçalho', () => {
    $backgroundStatusBySession.set({ 'rt-1': [running], 'rt-2': [failed] })

    render(<MissionControlPane />)

    // "1 failed" também aparece no cabeçalho do grupo — a asserção é sobre a
    // linha de resumo, que precisa carregar as duas contagens juntas.
    const summary = screen.getByText(/running across/)

    expect(summary.textContent).toContain('1 running across 2 sessions')
    expect(summary.textContent).toContain('1 failed')
  })

  it('para o processo com o id de RUNTIME da sessão dona dele', () => {
    // O bug que este teste impede: usar o storedId aqui mataria o processo de
    // outra sessão (ou nenhum), silenciosamente.
    $sessionStates.set({ 'rt-1': { storedSessionId: 'stored-abc' } as never })
    $backgroundStatusBySession.set({ 'rt-1': [running] })

    render(<MissionControlPane />)
    fireEvent.click(screen.getByLabelText('Stop this process'))

    expect(stopBackgroundProcess).toHaveBeenCalledWith('rt-1', 'proc-1')
  })

  it('não oferece parar para linha já encerrada, nem dispensar para linha viva', () => {
    $backgroundStatusBySession.set({ 'rt-1': [running], 'rt-2': [failed] })

    render(<MissionControlPane />)

    // Uma viva → um "parar"; uma encerrada → um "dispensar".
    expect(screen.getAllByLabelText('Stop this process')).toHaveLength(1)
    expect(screen.getAllByLabelText('Dismiss this row')).toHaveLength(1)
  })

  it('dispensa a linha encerrada pela sessão certa', () => {
    $backgroundStatusBySession.set({ 'rt-2': [failed] })

    render(<MissionControlPane />)
    fireEvent.click(screen.getByLabelText('Dismiss this row'))

    expect(dismissBackgroundProcess).toHaveBeenCalledWith('rt-2', 'proc-2')
  })

  it('abre a sessão dona da linha, pelo id ARMAZENADO', () => {
    // Ação e navegação usam ids diferentes de propósito: o gateway fala id de
    // runtime, a UI de sessões fala id armazenado.
    const onOpenSession = vi.fn()

    $sessionStates.set({ 'rt-1': { storedSessionId: 'stored-abc' } as never })
    $backgroundStatusBySession.set({ 'rt-1': [running] })

    render(<MissionControlPane onOpenSession={onOpenSession} />)
    fireEvent.click(screen.getByLabelText(/Open this session/))

    expect(onOpenSession).toHaveBeenCalledWith('stored-abc')
  })

  it('não oferece abrir sessão que ainda não foi persistida', () => {
    $backgroundStatusBySession.set({ 'rt-novo': [running] })

    render(<MissionControlPane onOpenSession={vi.fn()} />)

    expect(screen.queryByLabelText(/Open this session/)).toBeNull()
  })

  it('mostra o exit code rotulado — um "1" solto pode ser qualquer coisa', () => {
    $backgroundStatusBySession.set({ 'rt-2': [failed] })

    render(<MissionControlPane />)

    expect(screen.getByText('exit 1')).toBeTruthy()
  })

  it('anuncia o estado por texto, e não só por cor', () => {
    // O ícone é sempre `aria-hidden`, e o estado entrava apenas como classe de
    // cor. Um usuário de leitor de tela ouvia "npm run build" e "pytest -q" sem
    // saber qual das duas morreu. WCAG 1.4.1.
    $backgroundStatusBySession.set({ 'rt-1': [running], 'rt-2': [failed] })

    render(<MissionControlPane />)

    expect(screen.getByText('Running')).toBeTruthy()
    expect(screen.getByText('Failed')).toBeTruthy()
  })

  it('nomeia a sessão no rótulo do botão, em vez de apagá-la', () => {
    // `aria-label` SUBSTITUI o conteúdo do botão: com cinco sessões, um leitor
    // de tela ouvia "Abrir esta sessão" cinco vezes, sem nome nenhum.
    $sessionStates.set({ 'rt-1': { storedSessionId: 'stored-abc' } as never })
    $backgroundStatusBySession.set({ 'rt-1': [running] })

    render(<MissionControlPane onOpenSession={vi.fn()} />)

    expect(screen.getByLabelText(/Session stored/)).toBeTruthy()
  })

  it('nomeia sessão desconhecida pelo prefixo curto, não pelo UUID inteiro', () => {
    $backgroundStatusBySession.set({ 'a3f1c9e2-4b5d-6e7f-8a9b-0c1d2e3f4a5b': [running] })

    render(<MissionControlPane />)

    expect(screen.getByText('Session a3f1c9e2')).toBeTruthy()
  })

  it('hidrata o trabalho de TODAS as sessões ao abrir, não só as já vistas', () => {
    // O painel prometia "de todas as sessões" e só conhecia as que esta janela
    // tinha aberto: um processo morto numa sessão fechada não aparecia — o caso
    // exato para o qual ele existe.
    render(<MissionControlPane />)

    expect(refreshAllBackgroundProcesses).toHaveBeenCalled()
  })

  it('o botão Atualizar funciona no estado vazio, que é quando se aperta', () => {
    render(<MissionControlPane />)
    refreshAllBackgroundProcesses.mockClear()

    fireEvent.click(screen.getByLabelText('Refresh'))

    expect(refreshAllBackgroundProcesses).toHaveBeenCalled()
  })
})
