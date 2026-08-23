/**
 * O portão de publicação, testado nos casos em que ele tem que RECUSAR.
 *
 * Um script de checksums só vale pelo que ele impede. Os três casos abaixo são
 * exatamente as formas de publicar um binário que ninguém consegue reconstruir:
 * árvore suja, commit inexistente, e diretório de release vazio — este último é
 * o mais traiçoeiro, porque termina verde.
 */

import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, it } from 'vitest'

import {
  assertPublishable,
  findArtifacts,
  isDistributable,
  sha256,
  writeChecksums
} from './write-release-checksums.mjs'

const RELEASE_ENV = { HERMES_RELEASE_BUILD: "1" }
const CLEAN_STAMP = {
  schemaVersion: 1,
  commit: "ae2008d1f80e50e2e38ff85b287df946f9a72b60",
  branch: "feature/hermes-omniroute-studio",
  builtAt: "2026-08-22T17:36:58.000Z",
  dirty: false,
  source: "local"
}

describe("isDistributable", () => {
  it("reconhece o que um usuário baixa", () => {
    for (const name of [
      "Hermes-OmniRoute-Studio-0.17.0-win-x64.exe",
      "Hermes-OmniRoute-Studio-0.17.0-win-x64.msi",
      "Hermes-OmniRoute-Studio-0.17.0-mac-arm64.dmg",
      "Hermes-OmniRoute-Studio-0.17.0-linux-x64.AppImage",
      "hermes_0.17.0_amd64.deb",
      "app-release.apk"
    ]) {
      assert.equal(isDistributable(name), true, name)
    }
  })

  it("ignora os artefatos do canal de auto-update", () => {
    // `.blockmap` e `latest*.yml` são derivados dos instaladores. Listá-los
    // faria `sha256sum -c` falhar sempre que o canal de update não fosse
    // publicado junto.
    for (const name of ["Hermes-0.17.0-win-x64.exe.blockmap", "latest.yml", "latest-mac.yml", "builder-debug.yml"]) {
      assert.equal(isDistributable(name), false, name)
    }
  })
})

describe("assertPublishable", () => {
  it("não interfere fora de um build de release", () => {
    // Build local de desenvolvimento continua funcionando com árvore suja.
    assert.doesNotThrow(() => assertPublishable({ ...CLEAN_STAMP, dirty: true }, {}))
  })

  it("RECUSA árvore suja num build de release", () => {
    assert.throws(
      () => assertPublishable({ ...CLEAN_STAMP, dirty: true }, RELEASE_ENV),
      /árvore estava suja/
    )
  })

  it("RECUSA commit de placeholder", () => {
    assert.throws(
      () => assertPublishable({ ...CLEAN_STAMP, commit: "0000000000000000000000000000000000000000" }, RELEASE_ENV),
      /commit real/
    )
  })

  it("RECUSA stamp ausente", () => {
    assert.throws(() => assertPublishable(null, RELEASE_ENV), /não existe/)
  })

  it("aceita um stamp limpo", () => {
    assert.doesNotThrow(() => assertPublishable(CLEAN_STAMP, RELEASE_ENV))
  })
})

describe("writeChecksums", () => {
  let dir
  let releaseDir
  let stampFile

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "hermes-checksums-"))
    releaseDir = join(dir, "release")
    mkdirSync(releaseDir)
    mkdirSync(join(dir, "build"))
    stampFile = join(dir, "build", "install-stamp.json")
    writeFileSync(stampFile, JSON.stringify(CLEAN_STAMP), "utf8")
  })

  afterEach(() => {
    rmSync(dir, { recursive: true, force: true })
  })

  it("RECUSA diretório de release vazio", async () => {
    // O caso mais traiçoeiro: sem esta checagem o script termina verde e o
    // release sai sem artefato nenhum.
    await assert.rejects(
      () => writeChecksums({ releaseDir, stampFile, env: RELEASE_ENV }),
      /nenhum artefato distribuível/
    )
  })

  it("RECUSA release montado sobre um stamp sujo", async () => {
    // O portão do início do build já recusaria — mas um `release/` montado a
    // partir de um build antigo passaria por baixo dele. As duas pontas checam.
    writeFileSync(releaseDir + "/Hermes-0.17.0-win-x64.exe", "conteudo", "utf8")
    writeFileSync(stampFile, JSON.stringify({ ...CLEAN_STAMP, dirty: true }), "utf8")

    await assert.rejects(() => writeChecksums({ releaseDir, stampFile, env: RELEASE_ENV }), /árvore estava suja/)
  })

  it("escreve somas no formato do coreutils", async () => {
    writeFileSync(join(releaseDir, "Hermes-0.17.0-win-x64.exe"), "instalador", "utf8")
    writeFileSync(join(releaseDir, "Hermes-0.17.0-win-x64.exe.blockmap"), "derivado", "utf8")

    const { entries, sumsPath } = await writeChecksums({ releaseDir, stampFile, env: RELEASE_ENV })

    assert.equal(entries.length, 1, "o .blockmap não entra")

    const text = readFileSync(sumsPath, "utf8")
    const expected = await sha256(join(releaseDir, "Hermes-0.17.0-win-x64.exe"))

    // Dois espaços entre hash e nome — é o que `sha256sum -c` espera.
    assert.equal(text, `${expected}  Hermes-0.17.0-win-x64.exe\n`)
  })

  it("amarra cada artefato ao commit que o produziu", async () => {
    writeFileSync(join(releaseDir, "Hermes-0.17.0-win-x64.exe"), "instalador", "utf8")

    const { provenancePath } = await writeChecksums({ releaseDir, stampFile, env: RELEASE_ENV })
    const provenance = JSON.parse(readFileSync(provenancePath, "utf8"))

    assert.equal(provenance.commit, CLEAN_STAMP.commit)
    assert.equal(provenance.branch, CLEAN_STAMP.branch)
    assert.equal(provenance.dirty, false)
    assert.equal(provenance.releaseBuild, true)
    assert.equal(provenance.artifacts.length, 1)
    assert.equal(provenance.artifacts[0].name, "Hermes-0.17.0-win-x64.exe")
    assert.match(provenance.artifacts[0].sha256, /^[0-9a-f]{64}$/)
    assert.equal(provenance.artifacts[0].bytes, "instalador".length)
  })

  it("ordena os artefatos, para que o arquivo de somas seja estável", async () => {
    writeFileSync(join(releaseDir, "z-ultimo.exe"), "b", "utf8")
    writeFileSync(join(releaseDir, "a-primeiro.msi"), "a", "utf8")

    const { entries } = await writeChecksums({ releaseDir, stampFile, env: RELEASE_ENV })

    assert.deepEqual(
      entries.map(entry => entry.name),
      ["a-primeiro.msi", "z-ultimo.exe"]
    )
  })

  it("findArtifacts devolve lista vazia quando não há release/", () => {
    assert.deepEqual(findArtifacts(join(dir, "nao-existe")), [])
  })
})
