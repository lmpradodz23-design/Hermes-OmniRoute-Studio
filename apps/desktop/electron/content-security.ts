import path from 'node:path'
import { fileURLToPath } from 'node:url'

const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https: http://127.0.0.1:* http://localhost:*",
  "font-src 'self' data:",
  "media-src 'self' data: blob: https: http://127.0.0.1:* http://localhost:*",
  "connect-src 'self' https: http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:* wss:",
  "frame-src 'self' https: http://127.0.0.1:* http://localhost:*",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'self'",
  "frame-ancestors 'none'"
].join('; ')

export function contentSecurityPolicyHeaders(
  responseHeaders: Record<string, string[] | undefined> = {}
): Record<string, string[] | undefined> {
  const headers = { ...responseHeaders }

  for (const key of Object.keys(headers)) {
    if (key.toLowerCase() === 'content-security-policy') {delete headers[key]}
  }

  headers['Content-Security-Policy'] = [CONTENT_SECURITY_POLICY]

  return headers
}

export function hardenWebviewAttachment(
  webPreferences: {
    allowRunningInsecureContent?: boolean
    contextIsolation?: boolean
    nodeIntegration?: boolean
    nodeIntegrationInSubFrames?: boolean
    preload?: unknown
    sandbox?: boolean
    webSecurity?: boolean
  },
  params: { partition?: string; src?: string }
): boolean {
  delete webPreferences.preload
  webPreferences.nodeIntegration = false
  webPreferences.nodeIntegrationInSubFrames = false
  webPreferences.contextIsolation = true
  webPreferences.sandbox = true
  webPreferences.webSecurity = true
  webPreferences.allowRunningInsecureContent = false
  params.partition = 'persist:hermes-preview'

  const raw = typeof params.src === 'string' ? params.src.trim() : ''

  if (!raw || raw === 'about:blank') {return true}

  try {
    const parsed = new URL(raw)

    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
  } catch {
    return false
  }
}

export function isTrustedRendererNavigation(
  rawUrl: string,
  options: { devServer?: string; rendererIndexPath: string }
): boolean {
  try {
    const candidate = new URL(rawUrl)

    if (options.devServer) {
      const trusted = new URL(options.devServer)

      return candidate.origin === trusted.origin
    }

    if (candidate.protocol !== 'file:') {return false}
    const candidatePath = path.resolve(fileURLToPath(candidate))
    const rendererPath = path.resolve(options.rendererIndexPath)

    return process.platform === 'win32'
      ? candidatePath.toLowerCase() === rendererPath.toLowerCase()
      : candidatePath === rendererPath
  } catch {
    return false
  }
}

export { CONTENT_SECURITY_POLICY }
