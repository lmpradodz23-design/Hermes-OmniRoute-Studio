import fs from 'node:fs'
import path from 'node:path'

const ROOTS = ['electron', 'scripts', 'src']
const TEST_FILE = /\.(?:test|spec)\.[cm]?[jt]sx?$/
const INTERNAL_PLATFORM_RETURN =
  /if\s*\(\s*process\.platform\s*(?:===|!==)\s*['"](?:win32|darwin|linux)['"]\s*\)\s*\{[\s\S]{0,400}?\breturn\b/g
const INTERNAL_PLATFORM_ASSERTION =
  /if\s*\(\s*process\.platform\s*(?:===|!==)\s*['"](?:win32|darwin|linux)['"]\s*\)\s*\{[\s\S]{0,400}?\b(?:assert\.|expect\()/g

function collect(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const absolute = path.join(directory, entry.name)
    return entry.isDirectory() ? collect(absolute) : TEST_FILE.test(entry.name) ? [absolute] : []
  })
}

const violations = ROOTS.flatMap(root => collect(path.resolve(root))).flatMap(file => {
  const source = fs.readFileSync(file, 'utf8')
  return [...source.matchAll(INTERNAL_PLATFORM_RETURN), ...source.matchAll(INTERNAL_PLATFORM_ASSERTION)].map(match => {
    const line = source.slice(0, match.index).split(/\r?\n/).length
    return `${path.relative(process.cwd(), file)}:${line}`
  })
})

if (violations.length) {
  console.error('Platform-specific tests must use test.skipIf/test.runIf, not internal early returns:')
  for (const violation of violations) console.error(`- ${violation}`)
  process.exitCode = 1
} else {
  console.log('Platform test guards: PASS (no internal process.platform early-return no-ops)')
}
