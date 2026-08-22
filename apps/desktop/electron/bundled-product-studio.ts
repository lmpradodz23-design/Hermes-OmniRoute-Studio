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
  path.join('references', 'nontechnical-intake.md'),
  path.join('references', 'deployment-integrations.md'),
  path.join('references', 'subscription-auth.md')
]

const GUARDRAIL_FILES = ['plugin.yaml', '__init__.py']

function backupSnapshotName(version: string): string {
  const timestamp = new Date().toISOString().replaceAll('-', '').replaceAll(':', '')
  const safeVersion = version.replace(/[^a-zA-Z0-9._-]/g, '_')

  return `${timestamp}-${safeVersion}`
}

function backupManagedDirectory(destinationRoot: string, version: string): void {
  const backupRoot = path.join(path.dirname(destinationRoot), '.omniroute-backups', backupSnapshotName(version))
  const backupPath = path.join(backupRoot, path.basename(destinationRoot))
  fs.mkdirSync(backupRoot, { recursive: true })
  fs.cpSync(destinationRoot, backupPath, { recursive: true, errorOnExist: true })
}

function backupManagedFile(destinationPath: string, version: string): void {
  const backupRoot = path.join(path.dirname(destinationPath), '.omniroute-backups', backupSnapshotName(version))
  fs.mkdirSync(backupRoot, { recursive: true })
  fs.copyFileSync(destinationPath, path.join(backupRoot, path.basename(destinationPath)))
  const markerPath = `${destinationPath}${MCP_BRIDGE_MARKER_SUFFIX}`

  if (fs.existsSync(markerPath)) {
    fs.copyFileSync(markerPath, path.join(backupRoot, path.basename(markerPath)))
  }
}

export type BundledSkillInstallResult = 'installed' | 'skipped-missing' | 'skipped-unmanaged' | 'updated'
export type ManagedComponentState =
  { result: BundledSkillInstallResult; status: 'ready' } | { error: string; status: 'failed' }

export function resolveStudioManagedPaths(hermesHome: string) {
  const root = path.join(hermesHome, 'omniroute-studio')

  return {
    root,
    guardrailRoot: path.join(root, 'plugins', 'dz23-guardrail'),
    healthScriptPath: path.join(root, 'scripts', 'omniroute-daily-health.py'),
    mcpBridgePath: path.join(root, 'integrations', 'omniroute-mcp-bridge.mjs'),
    mcpPolicyPath: path.join(root, 'integrations', 'omniroute-mcp-policy.mjs')
  }
}

export function installManagedComponents(
  tasks: Record<string, () => BundledSkillInstallResult>
): Record<string, ManagedComponentState> {
  const state: Record<string, ManagedComponentState> = {}

  for (const [name, install] of Object.entries(tasks)) {
    try {
      state[name] = { status: 'ready', result: install() }
    } catch (error) {
      state[name] = {
        status: 'failed',
        error: error instanceof Error ? error.message : String(error)
      }
    }
  }

  return state
}

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

  if (existed) {
    backupManagedDirectory(destinationRoot, version)
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

function bundledFiles(sourceRoot: string): string[] {
  const files: string[] = []

  const visit = (directory: string) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '.git') {
        continue
      }

      const absolutePath = path.join(directory, entry.name)

      if (entry.isDirectory()) {
        visit(absolutePath)
      } else if (entry.isFile()) {
        files.push(path.relative(sourceRoot, absolutePath))
      }
    }
  }

  if (fs.existsSync(sourceRoot)) {
    visit(sourceRoot)
  }

  return files.sort()
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

export function installBundledCreativeSkill(options: {
  destinationRoot: string
  sourceRoot: string
  version: string
}): BundledSkillInstallResult {
  return installBundledSkillCollection(options)
}

export function installBundledSkillCollection(options: {
  destinationRoot: string
  sourceRoot: string
  version: string
}): BundledSkillInstallResult {
  const files = bundledFiles(options.sourceRoot)

  if (!files.some(relativePath => path.basename(relativePath) === 'SKILL.md')) {
    return 'skipped-missing'
  }

  return installManagedBundle(
    { ...options, managedBy: 'Hermes OmniRoute Studio third-party skill collection' },
    files
  )
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

  if (existed) {
    backupManagedFile(destinationPath, version)
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

export function installBundledOmniRouteMcpPolicy(options: {
  destinationPath: string
  sourcePath: string
  version: string
}): BundledSkillInstallResult {
  return installManagedFile(options, 'Hermes OmniRoute Studio MCP policy')
}

export function installBundledOmniRouteHealthScript(options: {
  destinationPath: string
  sourcePath: string
  version: string
}): BundledSkillInstallResult {
  return installManagedFile(options, 'Hermes OmniRoute Studio health check')
}

export function uninstallManagedDirectory(destinationRoot: string): boolean {
  if (!fs.existsSync(path.join(destinationRoot, MANAGED_MARKER))) {return false}
  fs.rmSync(destinationRoot, { recursive: true, force: true })

  return true
}

export function uninstallManagedFile(destinationPath: string): boolean {
  const markerPath = `${destinationPath}${MCP_BRIDGE_MARKER_SUFFIX}`

  if (!fs.existsSync(markerPath)) {return false}
  fs.rmSync(destinationPath, { force: true })
  fs.rmSync(markerPath, { force: true })

  return true
}
