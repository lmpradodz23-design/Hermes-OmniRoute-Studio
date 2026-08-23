"""A skill `autonomous-mission-loop` está integrada ao catálogo real do Hermes.

── Por que este arquivo existe ──────────────────────────────────────────────

Uma skill que existe só como `SKILL.md` no disco não é uma skill: é um arquivo.
Ela precisa ser descoberta pelo scanner, aparecer na listagem que o agente lê,
carregar por `skill_view`, e sobreviver ao gate de proveniência. Cada um desses
passos falha em silêncio de um jeito diferente — frontmatter inválido some da
listagem sem erro, nome que não bate com o diretório passa no lint e falha no
lookup, e uma skill não declarada quebra o teste de licenças de outra pessoa.

Estes testes travam o caminho inteiro contra o mecanismo REAL: o mesmo
`tools.skills_tool` que o agente usa em produção, com `HERMES_HOME` apontando
para uma cópia semeada do diretório `skills/` empacotado — que é exatamente o
que a instalação faz.

Nada aqui reimplementa a descoberta. Se o Hermes mudar como acha skills, estes
testes mudam junto ou quebram — que é o ponto.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ID = "autonomous-mission-loop"
SKILL_DIR = REPO_ROOT / "skills" / "autonomous-ai-agents" / SKILL_ID
SKILL_MD = SKILL_DIR / "SKILL.md"

# Os conceitos que fazem esta skill ser o que ela é. Se um sumir do corpo, a
# skill continua carregando e passa a ensinar outra coisa — por isso são
# verificados um a um, e não por tamanho de arquivo.
REQUIRED_CONCEPTS = (
    "CANDIDATE_COMPLETED",
    "BLOCKED_BY_EXTERNAL_DEPENDENCY",
    "STRATEGY_CHANGE_REQUIRED",
    "ESCALATE_TO_DIAGNOSTIC_AGENT",
    "last_progress_at",
    "heartbeat",
    "checkpoint",
    "watchdog",
    "AUDITORIA INDEPENDENTE",
)


@pytest.fixture(scope="module")
def _seeded_skills_tree(tmp_path_factory):
    """Uma cópia do `skills/` empacotado, montada uma vez por módulo.

    É o que a instalação do Hermes faz: `SKILLS_DIR = HERMES_HOME / "skills"`,
    populado a partir do diretório empacotado. Testar contra o repositório
    direto não provaria nada sobre o caminho real.
    """
    home = tmp_path_factory.mktemp("hermes-home")
    shutil.copytree(REPO_ROOT / "skills", home / "skills", dirs_exist_ok=True)

    return home


@pytest.fixture
def skills_tool(_seeded_skills_tree, monkeypatch):
    """O módulo real, apontado para um HERMES_HOME semeado.

    `tests/conftest.py` tem um autouse `_hermetic_environment` que redireciona
    `HERMES_HOME` para um tempdir VAZIO a cada teste — é ele que impede a suíte
    de ler o `~/.hermes` da máquina. Esta fixture é function-scoped de
    propósito: fixtures autouse rodam primeiro no mesmo escopo, então o
    `setenv` abaixo é o último a falar e o catálogo passa a enxergar a árvore
    semeada. Um `setenv` de escopo de módulo seria sobrescrito de volta para o
    diretório vazio antes de cada teste — foi exatamente assim que a primeira
    versão deste arquivo falhou.

    Não há `importlib.reload`: `tools.skills_tool._skills_dir()` resolve
    `get_hermes_home()` A CADA CHAMADA justamente para runtimes que trocam de
    perfil. Recarregar o módulo testaria o import, não o caminho de produção.
    """
    monkeypatch.setenv("HERMES_HOME", str(_seeded_skills_tree))

    from tools import skills_tool as module

    assert module._skills_dir() == _seeded_skills_tree / "skills", (
        "a resolução ao vivo de HERMES_HOME não pegou o diretório semeado"
    )

    return module


# ── Schema ───────────────────────────────────────────────────────────────────


def test_skill_file_exists_where_the_catalog_looks():
    assert SKILL_MD.is_file(), (
        f"{SKILL_MD} não existe. O scanner acha skills por SKILL.md; sem o "
        "arquivo no lugar certo, a skill simplesmente não existe para o agente."
    )


def test_frontmatter_parses_and_names_the_skill():
    from agent.skill_utils import parse_frontmatter

    frontmatter, body = parse_frontmatter(SKILL_MD.read_text(encoding="utf-8"))

    assert frontmatter, (
        "frontmatter vazio. Um YAML inválido é descartado em silêncio pelo "
        "parser — a skill aparece sem nome e sem descrição, ou não aparece."
    )
    assert frontmatter["name"] == SKILL_ID
    assert frontmatter["name"] == SKILL_DIR.name, "o nome tem que bater com o diretório"
    assert frontmatter["description"].strip()
    assert body.strip(), "corpo vazio: não há instrução nenhuma para carregar"


def test_passes_the_repository_linter():
    """O linter é o gate que o próprio repositório aplica às suas skills."""
    from tools.skill_linter import format_findings, has_errors, lint_skill

    findings = lint_skill(SKILL_MD)

    assert not has_errors(findings), format_findings(findings)


def test_description_fits_the_routing_budget():
    """A descrição é o que o agente lê para decidir usar a skill.

    O índice trunca em 60 caracteres. Uma descrição longa perde sinal de
    roteamento exatamente no lugar onde ele decide.
    """
    from agent.skill_utils import parse_frontmatter
    from tools.skill_linter import SKILL_PROMPT_DESC_LIMIT

    frontmatter, _ = parse_frontmatter(SKILL_MD.read_text(encoding="utf-8"))

    assert len(frontmatter["description"].strip()) <= SKILL_PROMPT_DESC_LIMIT


def test_body_carries_the_concepts_that_define_the_skill():
    body = SKILL_MD.read_text(encoding="utf-8")
    missing = [concept for concept in REQUIRED_CONCEPTS if concept not in body]

    assert not missing, (
        "A skill carregaria, mas sem estes conceitos ela ensina outra coisa:\n  "
        + "\n  ".join(missing)
    )


# ── Descoberta no catálogo real ──────────────────────────────────────────────


def test_catalog_discovery(skills_tool):
    found = skills_tool._find_all_skills()
    names = [entry.get("name") for entry in found]

    assert SKILL_ID in names, (
        f"O scanner varreu {len(found)} skills e não achou {SKILL_ID}. "
        "Frontmatter inválido, plataforma incompatível ou caminho excluído."
    )
    assert names.count(SKILL_ID) == 1, "skill duplicada no catálogo"


def test_catalog_entry_carries_name_description_and_category(skills_tool):
    entry = next(e for e in skills_tool._find_all_skills() if e.get("name") == SKILL_ID)

    assert entry["category"] == "autonomous-ai-agents"
    assert entry["description"].strip()


def test_listed_for_the_agent(skills_tool):
    listing = json.loads(skills_tool.skills_list())

    assert listing["success"] is True
    assert SKILL_ID in {entry["name"] for entry in listing["skills"]}
    assert "autonomous-ai-agents" in listing["categories"]


def test_listed_under_its_category(skills_tool):
    listing = json.loads(skills_tool.skills_list(category="autonomous-ai-agents"))

    assert SKILL_ID in {entry["name"] for entry in listing["skills"]}


def test_skill_load(skills_tool):
    """`skill_view` é como o agente carrega as instruções."""
    content = skills_tool.skill_view(SKILL_ID)

    assert len(content) > 3000, "conteúdo suspeito de truncamento"

    missing = [concept for concept in REQUIRED_CONCEPTS if concept not in content]

    assert not missing, "carregou sem os conceitos:\n  " + "\n  ".join(missing)


def test_loading_an_unknown_skill_does_not_silently_succeed(skills_tool):
    """Erro adequado, não uma casca vazia — e nunca o conteúdo de outra skill.

    O payload de erro lista as skills disponíveis como dica, então o nome da
    nossa skill APARECE nele. Checar `SKILL_ID not in result` seria um teste
    que reprova o comportamento certo. O que importa é: `success: false`, e
    nenhuma instrução carregada por engano.
    """
    payload = json.loads(skills_tool.skill_view("skill-que-nao-existe-abc123"))

    assert payload["success"] is False
    assert "skill-que-nao-existe-abc123" in payload["error"]
    assert SKILL_ID in payload["available_skills"], (
        "a dica de skills disponíveis deveria listar a skill descoberta"
    )

    # O corpo da skill não pode vazar para dentro de um erro de lookup.
    for concept in REQUIRED_CONCEPTS:
        assert concept not in payload["error"]


# ── Proveniência e licença ───────────────────────────────────────────────────


def test_declared_in_the_provenance_manifest():
    """Sem isso, o gate de licenças de `test_skill_provenance.py` quebra —
    e quebrar o teste de outra pessoa é como uma skill nova entra sem revisão."""
    manifest = json.loads((REPO_ROOT / "skills" / "PROVENANCE.json").read_text(encoding="utf-8"))
    relative = SKILL_DIR.relative_to(REPO_ROOT).as_posix()

    assert relative in manifest["firstParty"], (
        f"{relative} não está em firstParty de skills/PROVENANCE.json"
    )
    assert relative not in manifest["upstreamInherited"], "não veio do upstream"


# ── Limites de autonomia ─────────────────────────────────────────────────────


def test_skill_does_not_claim_to_override_security():
    """Uma skill de autonomia é exatamente onde alguém escreveria 'ignore os
    guardrails'. O texto tem que dizer o contrário, explicitamente."""
    body = SKILL_MD.read_text(encoding="utf-8").lower()

    assert "hardline" in body, "falta a afirmação de que a skill não sobrepõe o piso hardline"

    for forbidden in (
        "ignore os guardrails",
        "ignorar os guardrails",
        "sem aprovação",
        "bypass",
        "desabilite a segurança",
        "desabilitar a segurança",
    ):
        assert forbidden not in body, f"a skill contém instrução perigosa: {forbidden!r}"


def test_skill_forbids_faking_green():
    """O modo mais fácil de 'terminar' uma missão é falsificar o verde."""
    body = SKILL_MD.read_text(encoding="utf-8").lower()

    for rule in ("remover", "ignorar", "engolir", "hardcode", "mock"):
        assert rule in body, f"a proibição de {rule!r} sumiu da seção de causa raiz"


def test_skill_requires_evidence_before_completion():
    body = SKILL_MD.read_text(encoding="utf-8")

    assert "CANDIDATE_COMPLETED" in body
    assert "O executor não declara `COMPLETED`" in body
    assert "BLOCKERS_INTERNAL = 0" in body


# ── Regressão do catálogo ────────────────────────────────────────────────────


def test_other_skills_still_discoverable(skills_tool):
    """Acrescentar uma skill não pode quebrar o resto do catálogo."""
    names = {entry.get("name") for entry in skills_tool._find_all_skills()}

    for peer in ("product-studio", "hermes-agent", "plan", "test-driven-development"):
        assert peer in names, f"a skill vizinha {peer} sumiu do catálogo"


def test_no_duplicate_skill_names_in_the_catalog(skills_tool):
    """Nome duplicado faz `skill_view` carregar a errada, sem avisar."""
    from collections import Counter

    counts = Counter(entry.get("name") for entry in skills_tool._find_all_skills())
    duplicates = sorted(name for name, count in counts.items() if count > 1)

    assert not duplicates, "nomes duplicados no catálogo: " + ", ".join(duplicates)


# ── Ativação ────────────────────────────────────────────────────────────────
#
# "Ativar" no Hermes não é copiar arquivo: toda skill descoberta já está ativa,
# e o usuário DESATIVA pela lista `skills.disabled` do config.yaml (via
# `hermes skills`). O runtime honra isso em dois lugares independentes —
# `_find_all_skills` some com ela da listagem, e `skill_view` recusa carregar.
# Os dois precisam ser testados: se só a listagem filtrasse, o agente ainda
# conseguiria carregar por nome uma skill que o usuário desligou.


def _write_disabled(home, names):
    """Escreve `skills.disabled` no config.yaml real do HERMES_HOME."""
    (home / "config.yaml").write_text(
        "skills:\n  disabled:\n" + "".join(f"    - {name}\n" for name in names),
        encoding="utf-8",
    )


def test_skill_is_active_by_default(skills_tool, _seeded_skills_tree):
    """Uma skill recém-instalada tem que servir sem o usuário ligar nada."""
    listing = json.loads(skills_tool.skills_list())

    assert SKILL_ID in {entry["name"] for entry in listing["skills"]}


def test_deactivation_removes_it_from_the_listing(skills_tool, _seeded_skills_tree):
    _write_disabled(_seeded_skills_tree, [SKILL_ID])

    try:
        names = {entry.get("name") for entry in skills_tool._find_all_skills()}

        assert SKILL_ID not in names, "desativada pelo usuário e ainda listada"

        # E as vizinhas continuam lá: desativar uma não pode derrubar o catálogo.
        assert "product-studio" in names
    finally:
        (_seeded_skills_tree / "config.yaml").unlink()


def test_deactivation_also_blocks_direct_load(skills_tool, _seeded_skills_tree):
    """Filtrar só a listagem seria meia proteção: o agente carrega por nome."""
    _write_disabled(_seeded_skills_tree, [SKILL_ID])

    try:
        result = skills_tool.skill_view(SKILL_ID)

        assert "disabled" in result.lower(), (
            "skill desativada ainda carregou instruções por acesso direto"
        )
        for concept in REQUIRED_CONCEPTS:
            assert concept not in result
    finally:
        (_seeded_skills_tree / "config.yaml").unlink()


def test_reactivation_restores_it(skills_tool, _seeded_skills_tree):
    """Um toggle que não volta é um botão quebrado."""
    _write_disabled(_seeded_skills_tree, [SKILL_ID])
    assert SKILL_ID not in {e.get("name") for e in skills_tool._find_all_skills()}

    _write_disabled(_seeded_skills_tree, [])

    assert SKILL_ID in {e.get("name") for e in skills_tool._find_all_skills()}
    assert len(skills_tool.skill_view(SKILL_ID)) > 3000

    (_seeded_skills_tree / "config.yaml").unlink()


def test_disabling_a_peer_does_not_disable_this_one(skills_tool, _seeded_skills_tree):
    _write_disabled(_seeded_skills_tree, ["product-studio"])

    try:
        names = {entry.get("name") for entry in skills_tool._find_all_skills()}

        assert "product-studio" not in names
        assert SKILL_ID in names
    finally:
        (_seeded_skills_tree / "config.yaml").unlink()
