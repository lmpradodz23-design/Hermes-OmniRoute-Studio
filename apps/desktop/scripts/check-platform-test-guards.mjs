import fs from 'node:fs'
import path from 'node:path'

const ROOTS = ['electron', 'scripts', 'src', 'e2e']
const TEST_FILE = /\.(?:test|spec)\.[cm]?[jt]sx?$/
const PLATFORM_REFERENCE = /process\.platform/
const TOP_LEVEL_PLATFORM_CONSTANT = /^(?:const|let|var)\b.*process\.platform/
const DECLARATIVE_PLATFORM_GUARD = /^(?:test|it|describe)\.(?:skipIf|runIf)\(.*process\.platform/
const COMMENT = /^(?:\/\/|\/\*|\*)/
const ANONYMOUS_SKIP = /\b(?:test|it|describe|t)\.skip\(\s*\)/g
const NAMED_SKIP = /\b(?:test|it|describe)\.skip(?:If)?\([^)]*\)?\s*\(\s*(['"`])([^'"`]+)\1|\bt\.skip\(\s*(['"`])([^'"`]+)\3/gms

function collect(directory) {
  if (!fs.existsSync(directory)) return []

  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const absolute = path.join(directory, entry.name)
    return entry.isDirectory() ? collect(absolute) : TEST_FILE.test(entry.name) ? [absolute] : []
  })
}

function lineNumber(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

const files = ROOTS.flatMap(root => collect(path.resolve(root)))
const violations = []
const namedSkips = []

for (const file of files) {
  const source = fs.readFileSync(file, 'utf8')
  const relative = path.relative(process.cwd(), file)

  for (const [index, rawLine] of source.split(/\r?\n/).entries()) {
    const line = rawLine.trim()

    if (
      !PLATFORM_REFERENCE.test(line) ||
      COMMENT.test(line) ||
      TOP_LEVEL_PLATFORM_CONSTANT.test(rawLine) ||
      DECLARATIVE_PLATFORM_GUARD.test(line)
    ) {
      continue
    }

    violations.push(
      `${relative}:${index + 1} uses process.platform in executable test code; declare a host constant at module scope or use test.skipIf/test.runIf`,
    )
  }

  for (const match of source.matchAll(ANONYMOUS_SKIP)) {
    violations.push(`${relative}:${lineNumber(source, match.index)} has an anonymous skip without a reason`)
  }

  for (const match of source.matchAll(NAMED_SKIP)) {
    const reason = (match[2] || match[4] || '').trim()

    if (reason) namedSkips.push(`${relative}:${lineNumber(source, match.index)} — ${reason}`)
  }
}

if (violations.length) {
  console.error('Platform test guard violations:')
  for (const violation of violations) console.error(`- ${violation}`)
  process.exitCode = 1
} else {
  console.log('Platform test guards: PASS (no process.platform branches inside executable test code)')
  console.log(`Named skips discovered: ${namedSkips.length}`)
  for (const skip of namedSkips) console.log(`- ${skip}`)
}
