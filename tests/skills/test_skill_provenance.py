"""Toda skill empacotada declara de onde veio.

── Por que este teste existe ────────────────────────────────────────────────

O Studio empacota 227 skills. Dessas, a maioria veio junto com o fork do Hermes
Agent, e um punhado foi trazido de repositórios de terceiros — GSAP, LottieFiles,
Anthropic, obra/superpowers, entre outros. Sem um teste, a resposta para "esta
skill pode ser redistribuída?" depende de alguém lembrar, e no dia da publicação
ninguém lembra. Pior: a próxima skill adicionada reabre o buraco em silêncio,
porque nada quebra.

O teste transforma a pergunta em um portão. Uma skill nova sem proveniência
declarada falha o build, **nomeando o diretório**.

── O contrato ───────────────────────────────────────────────────────────────

Um diretório de skill (qualquer diretório com `SKILL.md`) tem que cair em um
destes três casos, e o teste diz em qual:

  1. `firstParty` em `skills/PROVENANCE.json` — escrita neste repositório.
  2. `upstreamInherited` em `skills/PROVENANCE.json` — veio com o fork, coberta
     pela LICENSE MIT da raiz e pela proveniência do upstream.
  3. Declarada em algum `SOURCES.json` / `SOURCE.json`, com repositório, commit,
     licença e `localPaths` apontando para o caminho **deste** repositório.

`paths` descreve o repositório de ORIGEM e é a informação certa para rastrear a
vendorização; `localPaths` diz onde a coisa caiu aqui. Os dois são necessários e
não são a mesma coisa — foi por confundir os dois que `img2threejs`, declarado
com `paths: ["."]`, parecia não ter proveniência nenhuma.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOTS = ("skills", "optional-skills")
MANIFEST_PATH = REPO_ROOT / "skills" / "PROVENANCE.json"

# Campos sem os quais uma declaração não serve para nada: não dá para auditar
# "de onde veio" sem repositório, nem "que versão" sem commit, nem "posso
# redistribuir" sem licença.
REQUIRED_SOURCE_FIELDS = ("id", "repository", "commit", "license")


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def discover_skill_dirs() -> list[str]:
    """Todo diretório que contém um `SKILL.md`."""
    found: set[str] = set()

    for root in SKILL_ROOTS:
        base = REPO_ROOT / root

        if not base.is_dir():
            continue

        for skill_md in base.rglob("SKILL.md"):
            found.add(_relative(skill_md.parent))

    return sorted(found)


def discover_source_files() -> list[Path]:
    """`SOURCES.json` e `SOURCE.json`.

    Os dois nomes existem na árvore. Aceitar ambos é deliberado: renomear o
    arquivo que o processo de vendorização criou quebraria a rastreabilidade com
    o commit que o trouxe, e o ganho seria cosmético.
    """
    found: list[Path] = []

    for root in SKILL_ROOTS:
        base = REPO_ROOT / root

        if not base.is_dir():
            continue

        found.extend(sorted(base.rglob("SOURCES.json")))
        found.extend(sorted(base.rglob("SOURCE.json")))

    return found


def load_manifest() -> dict:
    assert MANIFEST_PATH.is_file(), (
        f"{_relative(MANIFEST_PATH)} não existe. Ele é o manifesto que separa "
        "skill própria de skill herdada do upstream."
    )

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def iter_declared_sources() -> list[tuple[Path, dict]]:
    """(arquivo, entrada) para cada fonte declarada."""
    entries: list[tuple[Path, dict]] = []

    for source_file in discover_source_files():
        payload = json.loads(source_file.read_text(encoding="utf-8"))
        sources = payload.get("sources") or [payload]

        for source in sources:
            entries.append((source_file, source))

    return entries


@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_manifest()


@pytest.fixture(scope="module")
def declared_local_paths() -> set[str]:
    covered: set[str] = set()

    for _, source in iter_declared_sources():
        for local in source.get("localPaths", []):
            covered.add(local.strip("/"))

    return covered


def test_every_skill_has_declared_provenance(manifest, declared_local_paths):
    """O portão. Uma skill nova sem proveniência falha aqui, pelo nome."""
    first_party = set(manifest.get("firstParty", []))
    upstream = set(manifest.get("upstreamInherited", []))

    undeclared = [
        skill
        for skill in discover_skill_dirs()
        if skill not in first_party
        and skill not in upstream
        and not any(skill == local or skill.startswith(f"{local}/") for local in declared_local_paths)
    ]

    assert not undeclared, (
        "Estas skills não declaram de onde vieram. Escolha um dos três casos e "
        "registre no mesmo commit que trouxe a skill:\n"
        "  · própria      -> firstParty em skills/PROVENANCE.json\n"
        "  · do upstream  -> upstreamInherited em skills/PROVENANCE.json\n"
        "  · de terceiro  -> SOURCES.json com repository, commit, license e localPaths\n\n"
        + "\n".join(f"  {skill}" for skill in undeclared)
    )


def test_declared_sources_carry_the_fields_that_make_them_auditable():
    """Declaração sem repositório, commit ou licença não é declaração."""
    incomplete: list[str] = []

    for source_file, source in iter_declared_sources():
        missing = [field for field in REQUIRED_SOURCE_FIELDS if not source.get(field)]

        if missing:
            incomplete.append(f"  {_relative(source_file)} :: {source.get('id', '<sem id>')} — falta {', '.join(missing)}")

    assert not incomplete, "Fontes declaradas de forma incompleta:\n" + "\n".join(incomplete)


def test_declared_local_paths_point_at_something_real():
    """Uma declaração que aponta para um caminho que não existe mais é pior que
    nenhuma: dá a impressão de cobertura sem cobrir nada."""
    orphans: list[str] = []

    for source_file, source in iter_declared_sources():
        for local in source.get("localPaths", []):
            if not (REPO_ROOT / local).is_dir():
                orphans.append(f"  {_relative(source_file)} :: {source['id']} -> {local}")

    assert not orphans, (
        "Estes localPaths não existem no disco. Ou a skill foi movida e a "
        "declaração ficou para trás, ou foi removida e a declaração sobrou:\n"
        + "\n".join(orphans)
    )


def test_third_party_sources_name_a_license():
    """Redistribuir sem saber a licença é o risco que este arquivo todo existe
    para evitar. Um campo `license` vazio ou `"unknown"` não passa."""
    unlicensed: list[str] = []

    for source_file, source in iter_declared_sources():
        license_text = str(source.get("license", "")).strip()

        if not license_text or license_text.lower() in {"unknown", "tbd", "n/a", "none"}:
            unlicensed.append(f"  {_relative(source_file)} :: {source['id']} — license={license_text!r}")

    assert not unlicensed, "Fontes de terceiro sem licença declarada:\n" + "\n".join(unlicensed)


def test_manifest_does_not_list_skills_that_no_longer_exist(manifest):
    """Manifesto que acumula entradas mortas deixa de ser lido."""
    existing = set(discover_skill_dirs())
    stale = [
        entry
        for key in ("firstParty", "upstreamInherited")
        for entry in manifest.get(key, [])
        if entry not in existing
    ]

    assert not stale, (
        "skills/PROVENANCE.json lista skills que não existem mais. Remova as "
        "entradas no mesmo commit que removeu as skills:\n"
        + "\n".join(f"  {entry}" for entry in stale)
    )


def test_a_skill_cannot_be_first_party_and_upstream_at_the_same_time(manifest):
    overlap = sorted(set(manifest.get("firstParty", [])) & set(manifest.get("upstreamInherited", [])))

    assert not overlap, (
        "Estas skills estão declaradas como próprias E como herdadas do "
        "upstream. As duas coisas não podem ser verdade:\n"
        + "\n".join(f"  {entry}" for entry in overlap)
    )


def test_bundled_third_party_licenses_are_present_on_disk():
    """Uma licença citada no JSON mas ausente do disco não cumpre a MIT.

    A MIT — e praticamente toda licença permissiva — exige que o texto viaje
    junto com a cópia redistribuída. Citar "MIT" num JSON não é o texto.
    """
    missing: list[str] = []

    for source_file, source in iter_declared_sources():
        local_paths = source.get("localPaths", [])

        if not local_paths:
            continue

        # O arquivo de licença pode viver junto da skill ou no diretório do
        # lote vendorizado (é onde `LICENSE.daymade` e afins ficam).
        search_dirs = {source_file.parent}
        search_dirs.update((REPO_ROOT / local) for local in local_paths)
        search_dirs.update((REPO_ROOT / local).parent for local in local_paths)

        has_license = any(
            any(directory.glob(pattern))
            for directory in search_dirs
            if directory.is_dir()
            for pattern in ("LICENSE*", "COPYING*", "license*")
        )

        if not has_license:
            missing.append(f"  {_relative(source_file)} :: {source['id']} ({source.get('license')})")

    assert not missing, (
        "Estas fontes declaram uma licença mas não trazem o texto dela junto. "
        "A MIT exige que o aviso acompanhe a cópia redistribuída:\n"
        + "\n".join(missing)
    )
