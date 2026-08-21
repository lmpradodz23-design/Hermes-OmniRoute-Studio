import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'

import ts from 'typescript'

const sourcePath = path.resolve('src/i18n/en.ts')
const outputPath = path.resolve('src/i18n/pt-br.generated.ts')
const fieldSourcePath = path.resolve('src/app/settings/constants.ts')
const fieldOutputPath = path.resolve('src/i18n/pt-br-field-copy.generated.ts')
const cachePath = path.join(os.tmpdir(), 'hermes-pt-br-translation-cache-v2.json')
const endpoint = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=pt&dt=t'
const batchSeparator = '\n\uE100HERMES_PT_BR_SPLIT_9F7A\uE101\n'

const source = await fs.readFile(sourcePath, 'utf8')
const sourceFile = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
const fieldSource = await fs.readFile(fieldSourcePath, 'utf8')
const fieldSourceFile = ts.createSourceFile(
  fieldSourcePath,
  fieldSource,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TS
)

const enDeclaration = sourceFile.statements
  .filter(ts.isVariableStatement)
  .flatMap(statement => statement.declarationList.declarations)
  .find(declaration => ts.isIdentifier(declaration.name) && declaration.name.text === 'en')

if (!enDeclaration?.initializer) {
  throw new Error('Could not locate the English locale object')
}

function findDeclaration(source, name) {
  return source.statements
    .filter(ts.isVariableStatement)
    .flatMap(statement => statement.declarationList.declarations)
    .find(declaration => ts.isIdentifier(declaration.name) && declaration.name.text === name)
}

const fieldLabelsDeclaration = findDeclaration(fieldSourceFile, 'FIELD_LABELS')
const fieldDescriptionsDeclaration = findDeclaration(fieldSourceFile, 'FIELD_DESCRIPTIONS')
if (!fieldLabelsDeclaration?.initializer || !fieldDescriptionsDeclaration?.initializer) {
  throw new Error('Could not locate the settings field-copy objects')
}

const translatableRanges = [
  enDeclaration.initializer,
  fieldLabelsDeclaration.initializer,
  fieldDescriptionsDeclaration.initializer
].map(node => ({ start: node.pos, end: node.end, sourceFile: node.getSourceFile() }))
const textByNode = new Map()
const uniqueTexts = new Set()

function isInTranslatableRange(node) {
  return translatableRanges.some(
    range => node.getSourceFile() === range.sourceFile && node.pos >= range.start && node.end <= range.end
  )
}

function isPropertyName(node) {
  const parent = node.parent
  return (
    (ts.isPropertyAssignment(parent) ||
      ts.isMethodDeclaration(parent) ||
      ts.isPropertyDeclaration(parent) ||
      ts.isPropertySignature(parent)) &&
    parent.name === node
  )
}

function shouldTranslate(text) {
  if (!/[A-Za-z]/.test(text) || /^\s*$/.test(text)) return false
  if (/^(?:https?:\/\/|mailto:|[A-Za-z]:[\\/])/.test(text)) return false
  if (/^(?:en(?:-[A-Z]{2})?|UTC|JSON|YAML|TOML|MCP|SSH|HTTP|HTTPS)$/.test(text)) return false
  return true
}

function collect(node) {
  if (!isInTranslatableRange(node) || isPropertyName(node)) {
    ts.forEachChild(node, collect)
    return
  }

  if (
    ts.isStringLiteral(node) ||
    ts.isNoSubstitutionTemplateLiteral(node) ||
    ts.isTemplateHead(node) ||
    ts.isTemplateMiddle(node) ||
    ts.isTemplateTail(node)
  ) {
    if (shouldTranslate(node.text)) uniqueTexts.add(node.text)
  }

  ts.forEachChild(node, collect)
}

collect(enDeclaration.initializer)
collect(fieldLabelsDeclaration.initializer)
collect(fieldDescriptionsDeclaration.initializer)

let cache = {}
try {
  cache = JSON.parse(await fs.readFile(cachePath, 'utf8'))
} catch {
  cache = {}
}

const protectedPatterns = [
  /`[^`]+`/g,
  /https?:\/\/[^\s)]+/gi,
  /\b[A-Z][A-Z0-9_]{2,}\b/g,
  /--[a-z0-9][a-z0-9-]*/gi,
  /\b(?:Ctrl|Cmd|Alt|Shift)\+[A-Za-z0-9+]+/gi,
  /\b[\w.-]+\.(?:json|ya?ml|toml|md|tsx?|jsx?|py|go|rs|sh|ps1|exe|dmg|deb|rpm|AppImage)\b/gi
]

function protect(text) {
  const values = []
  let value = text
  for (const pattern of protectedPatterns) {
    value = value.replace(pattern, match => {
      const token = `\uE000${values.length}\uE001`
      values.push(match)
      return token
    })
  }
  return { value, values }
}

function restore(text, values) {
  let restored = text
  values.forEach((value, index) => {
    restored = restored.replaceAll(`\uE000${index}\uE001`, value)
  })
  return restored
}

async function translateBatch(entries) {
  const protectedEntries = entries.map(protect)
  const body = protectedEntries.map(entry => entry.value).join(batchSeparator)
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body: new URLSearchParams({ q: body }),
    signal: AbortSignal.timeout(30_000)
  })

  if (!response.ok) throw new Error(`Translation request failed with HTTP ${response.status}`)

  const payload = await response.json()
  const translated = payload[0].map(segment => segment[0]).join('')
  const parts = translated.split(batchSeparator)
  if (parts.length !== entries.length) {
    throw new Error(`Translation batch returned ${parts.length} parts for ${entries.length} inputs`)
  }
  return parts.map((part, index) => restore(part, protectedEntries[index].values))
}

const pending = [...uniqueTexts].filter(text => cache[text] === undefined)
const batches = []
let batch = []
let batchSize = 0

for (const value of pending) {
  const nextSize = batchSize + value.length + batchSeparator.length
  if (batch.length > 0 && nextSize > 3200) {
    batches.push(batch)
    batch = []
    batchSize = 0
  }
  batch.push(value)
  batchSize += value.length + batchSeparator.length
}
if (batch.length > 0) batches.push(batch)

for (let index = 0; index < batches.length; index += 1) {
  const entries = batches[index]
  let translated
  let lastError

  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      translated = await translateBatch(entries)
      break
    } catch (error) {
      lastError = error
      await new Promise(resolve => setTimeout(resolve, attempt * 750))
    }
  }

  if (!translated) throw lastError
  entries.forEach((value, entryIndex) => {
    cache[value] = translated[entryIndex]
  })
  await fs.writeFile(cachePath, `${JSON.stringify(cache, null, 2)}\n`, 'utf8')
  process.stdout.write(`Translated batch ${index + 1}/${batches.length}\r`)
}

for (const value of uniqueTexts) {
  textByNode.set(value, cache[value] ?? value)
}

const transformer = context => root => {
  const { factory } = context

  function visit(node) {
    if (isInTranslatableRange(node) && !isPropertyName(node)) {
      const translated = textByNode.get(node.text)
      if (translated !== undefined) {
        if (ts.isStringLiteral(node)) return factory.createStringLiteral(translated)
        if (ts.isNoSubstitutionTemplateLiteral(node)) {
          return factory.createNoSubstitutionTemplateLiteral(translated)
        }
        if (ts.isTemplateHead(node)) return factory.createTemplateHead(translated)
        if (ts.isTemplateMiddle(node)) return factory.createTemplateMiddle(translated)
        if (ts.isTemplateTail(node)) return factory.createTemplateTail(translated)
      }
    }

    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === 'en') {
      return factory.updateVariableDeclaration(
        node,
        factory.createIdentifier('ptBrBase'),
        node.exclamationToken,
        node.type,
        ts.visitNode(node.initializer, visit)
      )
    }

    return ts.visitEachChild(node, visit, context)
  }

  return ts.visitNode(root, visit)
}

const result = ts.transform(sourceFile, [transformer])
const printer = ts.createPrinter({ newLine: ts.NewLineKind.LineFeed })
const generated = printer
  .printFile(result.transformed[0])
  .replaceAll('FIELD_DESCRIPTIONS', 'PT_BR_FIELD_DESCRIPTIONS')
  .replaceAll('FIELD_LABELS', 'PT_BR_FIELD_LABELS')
  .replace(
    "import { PT_BR_FIELD_DESCRIPTIONS, PT_BR_FIELD_LABELS } from '@/app/settings/constants'",
    "import { PT_BR_FIELD_DESCRIPTIONS, PT_BR_FIELD_LABELS } from './pt-br-field-copy.generated'"
  )
result.dispose()

function translateInitializer(declaration) {
  const transformed = ts.transform(declaration.initializer, [transformer])
  const expression = transformed.transformed[0]
  const rendered = printer.printNode(ts.EmitHint.Expression, expression, fieldSourceFile)
  transformed.dispose()
  return rendered
}

const fieldBanner = '// Generated from app/settings/constants.ts by scripts/generate-pt-br-locale.mjs.\n\n'
const fieldGenerated = `${fieldBanner}import { defineFieldCopy } from '@/app/settings/field-copy'\n\nexport const PT_BR_FIELD_LABELS: Record<string, string> = ${translateInitializer(fieldLabelsDeclaration)}\n\nexport const PT_BR_FIELD_DESCRIPTIONS: Record<string, string> = ${translateInitializer(fieldDescriptionsDeclaration)}\n`

const banner =
  '// Generated from en.ts by scripts/generate-pt-br-locale.mjs.\n' +
  '// Curated Brazilian Portuguese overrides live in pt-br.ts.\n\n'
await fs.writeFile(outputPath, `${banner}${generated}`, 'utf8')
await fs.writeFile(fieldOutputPath, fieldGenerated, 'utf8')
process.stdout.write(`\nWrote ${outputPath} and ${fieldOutputPath} with ${uniqueTexts.size} translated strings.\n`)
