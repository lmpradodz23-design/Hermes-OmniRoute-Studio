import fs from 'node:fs'
import path from 'node:path'

const MANAGED_MARKER = '.omniroute-managed.json'
const MCP_BRIDGE_MARKER_SUFFIX = '.managed.json'

const SKILL_FILES = [
  'SKILL.md',
  path.join('agents', 'openai.yaml'),
  path.join('references', 'browser-security.md'),
  path.join('references', 'delivery-gates.md'),
  path.join('references', 'multi-agent-orchestration.md'),
  path.join('references', 'spec-driven-delivery.md'),
  path.join('references', 'knowledge-and-rules.md'),
  path.join('references', 'task-report.md'),
  path.join('references', 'nontechnical-intake.md')
]

const GUARDRAIL_FILES = ['plugin.yaml', '__init__.py']

export type BundledSkillInstallResult = 'installed' | 'skipped-missing' | 'skipped-unmanaged' | 'updated'

function installManagedBundle(
  options: {
    destinationRoot: string
    managedBy: string
    sourceRoot: string
    version: string
  },
  files: string[]
): BundledSkillInstallResult {
  const { destinationRoot, managedBy, sourceRoot, version } = options

  if (!fs.existsSync(path.join(sourceRoot, files[0] ?? ''))) {
    return 'skipped-missing'
  }

  const markerPath = path.join(destinationRoot, MANAGED_MARKER)
  const existed = fs.existsSync(destinationRoot)

  if (existed && !fs.existsSync(markerPath)) {
    return 'skipped-unmanaged'
  }

  for (const relativePath of files) {
    const source = path.join(sourceRoot, relativePath)

    if (!fs.existsSync(source)) {
      continue
    }

    const destination = path.join(destinationRoot, relativePath)
    fs.mkdirSync(path.dirname(destination), { recursive: true })
    fs.copyFileSync(source, destination)
  }

  fs.writeFileSync(markerPath, JSON.stringify({ managedBy, version }, null, 2) + '\n', 'utf8')

  return existed ? 'updated' : 'installed'
}

export function installBundledProductStudioSkill(options: {
  destinationRoot: string
  sourceRoot: string
  version: string
}): BundledSkillInstallResult {
  return installManagedBundle({ ...options, managedBy: 'Hermes OmniRoute Studio' }, SKILL_FILES)
}

export function installBundledDz23Guardrail(options: {
  destinationRoot: string
  sourceRoot: string
  version: string
}): BundledSkillInstallResult {
  return installManagedBundle({ ...options, managedBy: 'Hermes OmniRoute Studio guardrail' }, GUARDRAIL_FILES)
}

function installManagedFile(
  options: {
    destinationPath: string
    sourcePath: string
    version: string
  },
  managedBy: string
): BundledSkillInstallResult {
  const { destinationPath, sourcePath, version } = options

  if (!fs.existsSync(sourcePath)) {
    return 'skipped-missing'
  }

  const markerPath = `${destinationPath}${MCP_BRIDGE_MARKER_SUFFIX}`
  const existed = fs.existsSync(destinationPath)

  if (existed && !fs.existsSync(markerPath)) {
    return 'skipped-unmanaged'
  }

  fs.mkdirSync(path.dirname(destinationPath), { recursive: true })
  fs.copyFileSync(sourcePath, destinationPath)
  fs.writeFileSync(markerPath, JSON.stringify({ managedBy, version }, null, 2) + '\n', 'utf8')

  return existed ? 'updated' : 'installed'
}

export function installBundledOmniRouteMcpBridge(options: {
  destinationPath: string
  sourcePath: string
  version: string
}): BundledSkillInstallResult {
  return installManagedFile(options, 'Hermes OmniRoute Studio MCP bridge')
}

export function installBundledOmniRouteHealthScript(options: {
  destinationPath: string
  sourcePath: string
  version: string
}): BundledSkillInstallResult {
  return installManagedFile(options, 'Hermes OmniRoute Studio health check')
}
