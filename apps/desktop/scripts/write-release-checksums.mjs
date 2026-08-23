/**
 * Escreve `release/SHA256SUMS.txt` e `release/BUILD-PROVENANCE.json` depois do
 * empacotamento.
 *
 * ── Por que isto existe ─────────────────────────────────────────────────────
 *
 * A promessa central de um projeto open source é que qualquer pessoa possa
 * verificar o binário que baixou. Isso exige duas coisas, e o repositório só
 * tinha uma:
 *
 *   1. O build recusar árvore suja — `write-build-stamp.mjs` já faz, via
 *      `assertReleaseStamp` sob `HERMES_RELEASE_BUILD=1`.
 *   2. O hash publicado junto do artefato, mais o commit de onde ele saiu.
 *      Sem isso, "confira o hash" não tem com o que ser conferido.
 *
 * O instalador anterior saiu com `"dirty": true` no `install-stamp.json`: o
 * hash conferia com o esperado, mas a FONTE não era reconstruível — era um
 * commit mais um delta que só existia na máquina de quem construiu. Este script
 * fecha o outro lado: o arquivo de proveniência amarra cada artefato ao commit,
 * ao branch e ao momento do build.
 *
 * ── Formato ─────────────────────────────────────────────────────────────────
 *
 * `SHA256SUMS.txt` sai no formato padrão do `sha256sum`, com dois espaços entre
 * o hash e o nome, para que a verificação seja o comando que todo mundo já
 * conhece e não um procedimento nosso:
 *
 *     cd release && sha256sum -c SHA256SUMS.txt
 *     certutil -hashfile Hermes-OmniRoute-Studio-0.17.0-win-x64.exe SHA256   (Windows)
 *
 * ── O que faz o script falhar de propósito ──────────────────────────────────
 *
 *  - Nenhum artefato encontrado. Um script de release que termina verde sobre um
 *    diretório vazio é como se publica nada acreditando ter publicado.
 *  - Stamp sujo ou sem commit real, sob `HERMES_RELEASE_BUILD=1`. O portão já
 *    rodou no início do build, mas um `release/` montado a partir de um build
 *    antigo passaria por baixo dele.
 */

import { createHash } from "node:crypto"
import { createReadStream, existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs"
import { join, relative, resolve } from "node:path"

import { isMain } from "./utils.mjs"

const DESKTOP_ROOT = resolve(import.meta.dirname, "..")
const REPO_ROOT = resolve(DESKTOP_ROOT, "..", "..")
const RELEASE_DIR = join(DESKTOP_ROOT, "release")
const STAMP_FILE = join(DESKTOP_ROOT, "build", "install-stamp.json")

/**
 * Extensões que um usuário baixa. `.blockmap` e `latest*.yml` ficam de fora de
 * propósito: são artefatos do canal de auto-update, derivados dos instaladores,
 * e listá-los no arquivo de somas só faria a verificação manual falhar quando o
 * canal de update não fosse publicado junto.
 */
export const DISTRIBUTABLE_EXTENSIONS = [
  ".exe",
  ".msi",
  ".dmg",
  ".pkg",
  ".zip",
  ".tar.gz",
  ".AppImage",
  ".deb",
  ".rpm",
  ".snap",
  ".apk",
  ".aab"
]

export function isDistributable(fileName) {
  return DISTRIBUTABLE_EXTENSIONS.some(extension => fileName.endsWith(extension))
}

export function findArtifacts(releaseDir = RELEASE_DIR) {
  if (!existsSync(releaseDir)) {
    return []
  }

  return readdirSync(releaseDir)
    .filter(name => isDistributable(name))
    .filter(name => statSync(join(releaseDir, name)).isFile())
    .sort()
}

export function sha256(filePath) {
  return new Promise((resolvePromise, rejectPromise) => {
    const hash = createHash("sha256")
    const stream = createReadStream(filePath)

    stream.on("error", rejectPromise)
    stream.on("data", chunk => hash.update(chunk))
    stream.on("end", () => resolvePromise(hash.digest("hex")))
  })
}

export function readStamp(stampFile = STAMP_FILE) {
  if (!existsSync(stampFile)) {
    return null
  }

  try {
    return JSON.parse(readFileSync(stampFile, "utf8"))
  } catch {
    return null
  }
}

/**
 * O mesmo contrato de `assertReleaseStamp`, aplicado no fim do build. Duplicar a
 * checagem é deliberado: as duas pontas do processo têm que recusar, senão um
 * `release/` montado a partir de um build antigo escapa pelo meio.
 */
export function assertPublishable(stamp, env = process.env) {
  if (env.HERMES_RELEASE_BUILD !== "1") {
    return
  }

  if (!stamp) {
    throw new Error(
      "release refusado: build/install-stamp.json não existe. O artefato não " +
        "pode ser amarrado a nenhum commit, então ninguém consegue reconstruí-lo."
    )
  }

  if (stamp.dirty) {
    throw new Error(
      "release refusado: o stamp diz que a árvore estava suja. O artefato é um " +
        "commit mais um delta que só existe nesta máquina — ninguém mais " +
        "consegue reconstruí-lo. Commite o que foi revisado e reconstrua."
    )
  }

  if (!stamp.commit || /^0{7,40}$/.test(stamp.commit)) {
    throw new Error("release refusado: o stamp não tem um commit real.")
  }
}

export async function writeChecksums({ releaseDir = RELEASE_DIR, stampFile = STAMP_FILE, env = process.env } = {}) {
  const stamp = readStamp(stampFile)

  assertPublishable(stamp, env)

  const artifacts = findArtifacts(releaseDir)

  if (artifacts.length === 0) {
    throw new Error(
      `release refusado: nenhum artefato distribuível em ${relative(REPO_ROOT, releaseDir)}. ` +
        "Um script de checksums que termina verde sobre um diretório vazio é " +
        "como se publica nada acreditando ter publicado."
    )
  }

  const entries = []

  for (const name of artifacts) {
    const digest = await sha256(join(releaseDir, name))

    entries.push({ name, sha256: digest, bytes: statSync(join(releaseDir, name)).size })
  }

  // Formato do coreutils: <hash><dois espaços><nome>. Assim a verificação é
  // `sha256sum -c SHA256SUMS.txt`, e não um procedimento inventado por nós.
  const sumsPath = join(releaseDir, "SHA256SUMS.txt")

  writeFileSync(sumsPath, entries.map(entry => `${entry.sha256}  ${entry.name}`).join("\n") + "\n", "utf8")

  const provenancePath = join(releaseDir, "BUILD-PROVENANCE.json")

  writeFileSync(
    provenancePath,
    JSON.stringify(
      {
        schemaVersion: 1,
        commit: stamp?.commit ?? null,
        branch: stamp?.branch ?? null,
        builtAt: stamp?.builtAt ?? null,
        dirty: stamp?.dirty ?? null,
        source: stamp?.source ?? null,
        releaseBuild: env.HERMES_RELEASE_BUILD === "1",
        artifacts: entries,
        verify: {
          posix: "cd release && sha256sum -c SHA256SUMS.txt",
          windows: "certutil -hashfile <arquivo> SHA256"
        }
      },
      null,
      2
    ) + "\n",
    "utf8"
  )

  return { entries, sumsPath, provenancePath, stamp }
}

async function main() {
  try {
    const { entries, sumsPath } = await writeChecksums()

    console.log(`[write-release-checksums] ${relative(REPO_ROOT, sumsPath)}`)

    for (const entry of entries) {
      console.log(`  ${entry.sha256}  ${entry.name}`)
    }
  } catch (error) {
    console.error(`[write-release-checksums] ERROR: ${error instanceof Error ? error.message : String(error)}`)
    process.exit(1)
  }
}

if (isMain(import.meta.url)) {
  await main()
}
