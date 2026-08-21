import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'

const TOKEN_PREFIX = 'oma_live_'
const TOKEN_TTL_DAYS = 90

interface SafeStorageApi {
  decryptString(value: Buffer): string
  encryptString(value: string): Buffer
  isEncryptionAvailable(): boolean
}

interface StoredLocalToken {
  version: 1
  id: string
  prefix: string
  expiresAt: string
  encrypted: {
    encoding: 'safeStorage'
    value: string
  }
}

export interface OmniRouteLocalToken {
  expiresAt: string
  id: string
  token: string
}

interface LocalTokenOptions {
  homeDirectory?: string
  now?: () => Date
  randomBytes?: (size: number) => Buffer
  safeStorageApi: SafeStorageApi
  userDataDirectory: string
}

function databasePath(homeDirectory: string): string {
  return path.join(homeDirectory, '.omniroute', 'storage.sqlite')
}

function tokenStorePath(userDataDirectory: string): string {
  return path.join(userDataDirectory, 'omniroute-local-token.json')
}

function requireSecureStorage(api: SafeStorageApi): void {
  let available = false

  try {
    available = api.isEncryptionAvailable()
  } catch {
    available = false
  }

  if (!available) {
    throw new Error('Secure OS token storage is required for the OmniRoute integration')
  }
}

function writeSecretAtomic(filePath: string, value: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const temporary = `${filePath}.${process.pid}.tmp`

  try {
    fs.rmSync(temporary, { force: true })
    fs.writeFileSync(temporary, value, { encoding: 'utf8', mode: 0o600 })

    try {
      fs.chmodSync(temporary, 0o600)
    } catch {
      // Windows ACL hardening is handled separately; safeStorage still keeps
      // the credential encrypted when POSIX mode bits are unavailable.
    }

    fs.renameSync(temporary, filePath)
  } finally {
    fs.rmSync(temporary, { force: true })
  }
}

function readStoredToken(filePath: string, safeStorageApi: SafeStorageApi): OmniRouteLocalToken | null {
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8')) as StoredLocalToken

    if (
      parsed.version !== 1 ||
      typeof parsed.id !== 'string' ||
      typeof parsed.expiresAt !== 'string' ||
      parsed.encrypted?.encoding !== 'safeStorage' ||
      typeof parsed.encrypted.value !== 'string'
    ) {
      return null
    }

    const token = safeStorageApi.decryptString(Buffer.from(parsed.encrypted.value, 'base64'))

    if (!token.startsWith(TOKEN_PREFIX)) {return null}

    return { expiresAt: parsed.expiresAt, id: parsed.id, token }
  } catch {
    return null
  }
}

function openTokenDatabase(homeDirectory: string): DatabaseSync {
  const location = databasePath(homeDirectory)

  if (!fs.existsSync(location)) {
    throw new Error('OmniRoute token database is unavailable; start OmniRoute before enabling the integration')
  }

  const database = new DatabaseSync(location)
  database.exec('PRAGMA busy_timeout=5000')

  return database
}

function tokenRowIsValid(database: DatabaseSync, token: OmniRouteLocalToken, now: Date): boolean {
  if (Date.parse(token.expiresAt) <= now.getTime()) {return false}

  const row = database
    .prepare('SELECT token_hash, expires_at FROM cli_access_tokens WHERE id = ? LIMIT 1')
    .get(token.id) as { expires_at?: string | null; token_hash?: string } | undefined

  if (!row?.token_hash) {return false}
  const expected = crypto.createHash('sha256').update(token.token).digest('hex')

  if (!/^[0-9a-f]{64}$/i.test(row.token_hash)) {return false}

  if (!crypto.timingSafeEqual(Buffer.from(row.token_hash), Buffer.from(expected))) {return false}

  return !row.expires_at || Date.parse(row.expires_at) > now.getTime()
}

function deleteTokenRow(database: DatabaseSync, id: string): void {
  if (/^tok_[0-9a-f-]{36}$/i.test(id)) {
    database.prepare('DELETE FROM cli_access_tokens WHERE id = ?').run(id)
  }
}

export function ensureOmniRouteLocalToken(options: LocalTokenOptions): OmniRouteLocalToken {
  requireSecureStorage(options.safeStorageApi)
  const homeDirectory = options.homeDirectory ?? os.homedir()
  const now = (options.now ?? (() => new Date()))()
  const storePath = tokenStorePath(options.userDataDirectory)
  const database = openTokenDatabase(homeDirectory)

  try {
    const existing = readStoredToken(storePath, options.safeStorageApi)

    if (existing && tokenRowIsValid(database, existing, now)) {
      return existing
    }

    if (existing) {deleteTokenRow(database, existing.id)}

    const randomBytes = options.randomBytes ?? crypto.randomBytes
    const token = `${TOKEN_PREFIX}${randomBytes(32).toString('base64url')}`
    const id = `tok_${crypto.randomUUID()}`
    const expiresAt = new Date(now.getTime() + TOKEN_TTL_DAYS * 86_400_000).toISOString()
    const encrypted = options.safeStorageApi.encryptString(token).toString('base64')

    const stored: StoredLocalToken = {
      version: 1,
      id,
      prefix: token.slice(0, 15),
      expiresAt,
      encrypted: { encoding: 'safeStorage', value: encrypted }
    }

    database
      .prepare(
        `INSERT INTO cli_access_tokens
        (id, token_hash, token_prefix, name, scope, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        id,
        crypto.createHash('sha256').update(token).digest('hex'),
        stored.prefix,
        'Hermes OmniRoute Studio local bridge',
        'admin',
        now.toISOString(),
        expiresAt
      )

    try {
      writeSecretAtomic(storePath, JSON.stringify(stored, null, 2))
    } catch (error) {
      deleteTokenRow(database, id)
      throw error
    }

    return { expiresAt, id, token }
  } finally {
    database.close()
  }
}

export function revokeOmniRouteLocalToken(options: LocalTokenOptions): boolean {
  const storePath = tokenStorePath(options.userDataDirectory)
  const stored = readStoredToken(storePath, options.safeStorageApi)

  if (!stored) {
    fs.rmSync(storePath, { force: true })

    return false
  }

  const database = openTokenDatabase(options.homeDirectory ?? os.homedir())

  try {
    deleteTokenRow(database, stored.id)
  } finally {
    database.close()
  }

  fs.rmSync(storePath, { force: true })

  return true
}
