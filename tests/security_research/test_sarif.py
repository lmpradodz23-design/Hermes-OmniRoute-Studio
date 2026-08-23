"""Ingestão de SARIF como entrada hostil — malformado, gigante, e apontando
para fora do projeto. Inclui a normalização do SARIF REAL do RAPTOR.
"""

import json
from pathlib import Path

import pytest

from security_research.boundary import AuthorizedTarget
from security_research.findings import FindingState, Severity
from security_research.sarif import (
    MAX_SARIF_BYTES,
    SarifError,
    load_sarif_bytes,
    load_sarif_file,
    normalize_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "raptor_semgrep_real.sarif"


@pytest.fixture
def target(tmp_path):
    # O SARIF real aponta para /tmp/vuln-target/app.py. Recriamos essa árvore
    # sob um alvo autorizado para a normalização ter onde resolver.
    (tmp_path / "app.py").write_text("import subprocess\n")
    return AuthorizedTarget.create(str(tmp_path))


# ── validação de entrada hostil ──────────────────────────────────────────


def test_rejects_non_json():
    with pytest.raises(SarifError):
        load_sarif_bytes(b"isto nao e json {{{")


def test_rejects_non_object_root():
    with pytest.raises(SarifError):
        load_sarif_bytes(b"[1, 2, 3]")


def test_rejects_unsupported_version():
    with pytest.raises(SarifError):
        load_sarif_bytes(json.dumps({"version": "9.9.9", "runs": []}).encode())


def test_rejects_missing_runs():
    with pytest.raises(SarifError):
        load_sarif_bytes(json.dumps({"version": "2.1.0"}).encode())


def test_rejects_oversized_file(tmp_path):
    big = tmp_path / "big.sarif"
    big.write_bytes(b"{}" + b" " * (MAX_SARIF_BYTES + 10))
    with pytest.raises(SarifError, match="grande demais"):
        load_sarif_file(big)


def test_oversized_is_rejected_before_parsing(tmp_path):
    # Um arquivo grande NÃO precisa ser JSON válido para ser recusado — a
    # checagem de tamanho vem antes, que é o ponto (não estourar a memória).
    big = tmp_path / "big.sarif"
    big.write_bytes(b"x" * (MAX_SARIF_BYTES + 1))
    with pytest.raises(SarifError, match="grande demais"):
        load_sarif_file(big)


def test_malformed_result_does_not_crash(target):
    doc = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "t"}}, "results": [None, 42, "x", {}]}],
    }
    findings, dropped = normalize_document(doc, target=target)
    assert findings == []  # nenhum resultado válido, mas sem exceção


# ── path traversal via uri do SARIF ──────────────────────────────────────


def test_result_pointing_outside_target_is_dropped(target):
    doc = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "evil"}},
                "results": [
                    {
                        "ruleId": "r1",
                        "level": "error",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "../../etc/passwd"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    findings, dropped = normalize_document(doc, target=target)
    assert findings == []
    assert "../../etc/passwd" in dropped  # registrado, não seguido


# ── normalização do SARIF REAL do RAPTOR ─────────────────────────────────


def test_normalizes_real_raptor_sarif(target):
    """Prova de integração: o SARIF que o RAPTOR realmente produziu, normalizado.

    O fixture é a saída real de `python3 raptor.py scan` sobre um alvo com
    command injection — 4 findings do Semgrep, todos em app.py. Reescrevemos os
    uris para o alvo de teste, preservando regra/estrutura reais.
    """
    doc = json.loads(FIXTURE.read_text())
    # o SARIF real referencia /tmp/vuln-target/app.py; reescreve para relativo.
    for run in doc["runs"]:
        for res in run.get("results", []):
            for loc in res.get("locations", []):
                art = loc.get("physicalLocation", {}).get("artifactLocation", {})
                if "uri" in art:
                    art["uri"] = "app.py"

    findings, dropped = normalize_document(doc, target=target, project="vuln-target")

    assert len(findings) == 4, "os 4 findings reais do Semgrep foram normalizados"
    assert all(f.file == "app.py" for f in findings)
    assert all(f.state == FindingState.CANDIDATE for f in findings), (
        "finding de scanner nasce CANDIDATE, nunca CONFIRMED"
    )
    # regras reais do Semgrep preservadas
    rules = {f.rule for f in findings}
    assert any("subprocess" in r or "injection" in r for r in rules)
    # cada um carrega evidência FACT com a origem
    assert all(any(e.kind.value == "fact" for e in f.evidence) for f in findings)
