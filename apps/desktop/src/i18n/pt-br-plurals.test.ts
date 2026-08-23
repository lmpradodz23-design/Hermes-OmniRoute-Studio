/**
 * As funções de tradução do pt-BR, CHAMADAS — não só contadas.
 *
 * ── Por que este arquivo existe ──────────────────────────────────────────────
 *
 * `pt-br.test.ts` mede cobertura percorrendo o catálogo, e o `flatten` dele
 * ignora valores função. São 388 chaves-função em `en.ts`, e nenhuma delas era
 * verificada por ninguém. A métrica dizia 98,5% enquanto a tela mostrava:
 *
 *     "2 anexoé"        "2 modeloé"       "2 subagenteé"
 *     "2 encontraré"    "2 resultadoé em 2senhora"
 *     "Empregos"        "Filial X · Comprometer-se Y"
 *
 * A causa era o gerador automático: ele extraía CADA literal isoladamente e
 * mandava traduzir. Em `${n} model${n === 1 ? '' : 's'}` o sufixo `'s'` virava
 * uma string traduzível por conta própria e voltava como `'é'`; `'ms'` voltava
 * como `'senhora'`; `'m'` como `'eu'`.
 *
 * Cobertura não pega isso — só chamar pega. Este teste chama cada função com 1
 * e com 2 e exige que a diferença entre as duas saídas seja plural de verdade.
 */

import { describe, expect, it } from 'vitest'

import { TRANSLATIONS } from './catalog'

/** Sufixos que marcam plural em português. */
const PLURAL_SUFFIX = /^(s|es|ns|is|res|ões|ãos)\b/

function collectFunctionPaths(node: unknown, path: string[], out: string[][]) {
  if (typeof node === 'function') {
    out.push(path)

    return
  }

  if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
      collectFunctionPaths(value, [...path, key], out)
    }
  }
}

function resolve(root: unknown, path: string[]): unknown {
  return path.reduce<unknown>((node, key) => (node as Record<string, unknown>)?.[key], root)
}

describe('funções de plural do pt-BR', () => {
  it('produzem plural de verdade, e não um sufixo traduzido por engano', () => {
    const ptBr = (TRANSLATIONS as Record<string, unknown>)['pt-br']
    const paths: string[][] = []

    collectFunctionPaths(ptBr, [], paths)

    expect(paths.length).toBeGreaterThan(300)

    const broken: string[] = []

    for (const path of paths) {
      const fn = resolve(ptBr, path) as (n: number) => string
      let one: string
      let two: string

      try {
        one = fn(1)
        two = fn(2)
      } catch {
        // Função que espera outro formato de argumento; fora do escopo deste teste.
        continue
      }

      if (typeof one !== 'string' || typeof two !== 'string') {
        continue
      }

      // Números fora: a diferença que interessa é a das PALAVRAS.
      const a = one.replace(/\d+/g, '#')
      const b = two.replace(/\d+/g, '#')

      if (a === b) {
        continue
      }

      let index = 0

      while (index < a.length && index < b.length && a[index] === b[index]) {
        index += 1
      }

      const divergence = b.slice(index)

      if (!PLURAL_SUFFIX.test(divergence) && divergence.trim() !== '') {
        broken.push(`${path.join('.')}\n      (1) ${one}\n      (2) ${two}`)
      }
    }

    expect(broken, `Plural quebrado em ${broken.length} chave(s):\n\n${broken.join('\n\n')}`).toEqual([])
  })
})

describe('estrutura do arquivo de overrides', () => {
  it('não tem chave duplicada — a segunda apaga a primeira em silêncio', async () => {
    // Aconteceu duas vezes durante esta correção: um bloco `skills:` novo
    // inserido antes de um `skills:` já existente é simplesmente descartado
    // pelo JavaScript — sem erro, sem aviso — e a tradução "corrigida" nunca
    // aparece na tela. A comparação é por CAMINHO COMPLETO: `settings.nav` e
    // `sidebar.nav` são chaves distintas e legítimas.
    const { readFileSync } = await import('node:fs')
    const { join } = await import('node:path')
    const source = readFileSync(join(process.cwd(), 'src', 'i18n', 'pt-br.ts'), 'utf8')

    const stack: string[] = []
    const seen = new Set<string>()
    const duplicates: string[] = []
    let inString: string | null = null

    for (let index = 0; index < source.length; index += 1) {
      const char = source[index]!

      // Pular literais: chaves e aspas dentro de texto não são estrutura.
      if (inString) {
        if (char === '\\') {
          index += 1
        } else if (char === inString) {
          inString = null
        }
        continue
      }

      if (char === "'" || char === '"' || char === '`') {
        inString = char
        continue
      }

      if (char === '}') {
        stack.pop()
        continue
      }

      if (char !== '{') {
        continue
      }

      // Nome da chave imediatamente antes desta abertura de bloco.
      const before = source.slice(Math.max(0, index - 120), index)
      const name = /([a-zA-Z_$][\w$]*|'[^']+')\s*:\s*$/.exec(before)?.[1]

      if (!name) {
        stack.push('?')
        continue
      }

      const path = [...stack.filter(part => part !== '?'), name.replace(/'/g, '')].join('.')

      if (seen.has(path)) {
        duplicates.push(path)
      }

      seen.add(path)
      stack.push(name.replace(/'/g, ''))
    }

    expect(duplicates, `Blocos duplicados: ${duplicates.join(', ')}`).toEqual([])
  })
})
