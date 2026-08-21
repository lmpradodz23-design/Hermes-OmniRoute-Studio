#!/usr/bin/env node

import { Console } from 'node:console'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const stderrConsole = new Console({ stdout: process.stderr, stderr: process.stderr })
console.log = stderrConsole.log.bind(stderrConsole)
console.warn = stderrConsole.warn.bind(stderrConsole)

function candidateRoots() {
  const roots = [process.env.OMNIROUTE_PACKAGE_ROOT]

  if (process.platform === 'win32') {
    if (process.env.APPDATA) roots.push(path.join(process.env.APPDATA, 'npm', 'node_modules', 'omniroute'))
  } else {
    roots.push(
      path.join(os.homedir(), '.npm-global', 'lib', 'node_modules', 'omniroute'),
      path.join(os.homedir(), '.local', 'lib', 'node_modules', 'omniroute'),
      '/usr/local/lib/node_modules/omniroute',
      '/usr/lib/node_modules/omniroute'
    )
  }

  return roots.filter(Boolean)
}

const root = candidateRoots().find(candidate =>
  fs.existsSync(path.join(candidate, 'open-sse', 'mcp-server', 'server.ts'))
)

if (!root) {
  throw new Error('OmniRoute package root not found; install OmniRoute globally or set OMNIROUTE_PACKAGE_ROOT')
}

const aliasResolver = await import(pathToFileURL(path.join(root, 'bin', 'aliasResolver.mjs')).href)
await aliasResolver.registerAliasResolver(root)

const tsxLoaderUrl = pathToFileURL(path.join(root, 'node_modules', 'tsx', 'dist', 'loader.mjs')).href
await import(tsxLoaderUrl)

const command = process.argv[2]
if (command === '--compression-status' || command === '--compression-set') {
  const toolsPath = path.join(root, 'open-sse', 'mcp-server', 'tools', 'compressionTools.ts')
  const compression = await import(pathToFileURL(toolsPath).href)
  const mode = process.argv[3]
  if (command === '--compression-set' && mode !== 'caveman' && mode !== 'off') {
    throw new Error('Unsupported compression mode; expected caveman or off')
  }
  const result =
    command === '--compression-status'
      ? await compression.handleCompressionStatus({})
      : await compression.handleSetCompressionEngine({ engine: mode })
  process.stdout.write(`${JSON.stringify(result)}\n`)
  process.exit(0)
}

const serverPath = path.join(root, 'open-sse', 'mcp-server', 'server.ts')
const server = await import(pathToFileURL(serverPath).href)

await server.startMcpStdio()
