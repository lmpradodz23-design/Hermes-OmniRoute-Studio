"""Ingestão de SARIF — tratado como ENTRADA HOSTIL do início ao fim.

Um scan de UM arquivo de 6 linhas produziu 3,2 MB de SARIF no teste real. Um
parser permissivo aqui é um vetor de DoS e de path traversal (o `uri` de cada
resultado é um caminho controlado pela ferramenta). Por isso:

  * o arquivo tem tamanho máximo (`MAX_SARIF_BYTES`) — acima disso é recusado
    ANTES de parsear, não depois de estourar a memória;
  * a estrutura é validada campo a campo; um SARIF malformado vira erro
    claro, nunca um finding pela metade nem uma exceção crua;
  * cada `uri` é resolvido pelo `AuthorizedTarget` — um resultado apontando
    para fora do projeto é descartado, não seguido;
  * a contagem de resultados é limitada (`MAX_RESULTS`) para um SARIF hostil
    não gerar findings infinitos.

Nada de `severity` inventada: o nível vem do SARIF; ausente, é UNKNOWN.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .boundary import AuthorizedTarget, ProjectBoundaryError
from .findings import Confidence, Evidence, EvidenceKind, Finding, FindingState, Severity

# Um SARIF real de scan pequeno já passou de 3 MB (metadados de regra). 64 MB é
# folgado para projetos reais e ainda barra um arquivo hostil de gigabytes.
MAX_SARIF_BYTES = 64 * 1024 * 1024
MAX_RESULTS = 100_000


class SarifError(Exception):
    """SARIF ausente, grande demais, ou estruturalmente inválido."""


# Mapeamento SARIF level -> Severity. `warning`/`error`/`note` é o vocabulário
# do SARIF; `security-severity` (0-10, convenção do GitHub) refina quando presente.
_LEVEL_TO_SEV = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "note": Severity.LOW,
    "none": Severity.INFO,
}


def _security_severity_to_sev(score: float) -> Severity:
    if score >= 9.0:
        return Severity.CRITICAL
    if score >= 7.0:
        return Severity.HIGH
    if score >= 4.0:
        return Severity.MEDIUM
    if score > 0.0:
        return Severity.LOW
    return Severity.INFO


def load_sarif_bytes(raw: bytes) -> Dict[str, Any]:
    """Parseia bytes de SARIF com teto de tamanho e validação de topo."""
    if len(raw) > MAX_SARIF_BYTES:
        raise SarifError(f"SARIF grande demais: {len(raw)} bytes (máx {MAX_SARIF_BYTES})")
    try:
        doc = json.loads(raw.decode("utf-8", "strict"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SarifError(f"SARIF ilegível: {exc}") from exc
    except RecursionError as exc:
        # JSON hostil profundamente aninhado — falha fechada, não estoura a pilha.
        raise SarifError("SARIF aninhado demais") from exc
    if not isinstance(doc, dict):
        raise SarifError("SARIF raiz não é um objeto")
    if doc.get("version") not in ("2.1.0", "2.0.0"):
        raise SarifError(f"versão SARIF não suportada: {doc.get('version')!r}")
    if not isinstance(doc.get("runs"), list):
        raise SarifError("SARIF sem 'runs' válido")
    return doc


def load_sarif_file(path: Path, *, max_bytes: int = MAX_SARIF_BYTES) -> Dict[str, Any]:
    """Lê e valida um arquivo SARIF, checando o tamanho ANTES de ler tudo."""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise SarifError(f"SARIF inacessível: {exc}") from exc
    if size > max_bytes:
        raise SarifError(f"SARIF grande demais: {size} bytes (máx {max_bytes})")
    return load_sarif_bytes(p.read_bytes())


def _rule_index(driver: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rules = driver.get("rules")
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(rules, list):
        for rule in rules:
            if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                out[rule["id"]] = rule
    return out


def _severity_for(result: Dict[str, Any], rule: Dict[str, Any]) -> Severity:
    # security-severity numérica tem prioridade (mais informativa).
    for holder in (result.get("properties"), rule.get("properties")):
        if isinstance(holder, dict) and "security-severity" in holder:
            try:
                return _security_severity_to_sev(float(holder["security-severity"]))
            except (TypeError, ValueError):
                pass
    level = result.get("level")
    if not isinstance(level, str):
        default = rule.get("defaultConfiguration")
        if isinstance(default, dict):
            level = default.get("level")
    return _LEVEL_TO_SEV.get(str(level or "").lower(), Severity.UNKNOWN)


def normalize_run(
    run: Dict[str, Any],
    *,
    target: AuthorizedTarget,
    project: str = "",
    dropped: List[str] | None = None,
) -> List[Finding]:
    """Converte um `run` SARIF em findings normalizados, dentro da fronteira.

    Resultados cujo `uri` cai fora do alvo autorizado são DESCARTADOS (e o
    caminho registrado em ``dropped`` para observabilidade), nunca seguidos.
    """
    driver = (run.get("tool") or {}).get("driver") or {}
    scanner = str(driver.get("name") or "unknown-scanner")
    rules = _rule_index(driver)
    results = run.get("results")
    if not isinstance(results, list):
        return []
    if len(results) > MAX_RESULTS:
        raise SarifError(f"resultados demais no SARIF: {len(results)} (máx {MAX_RESULTS})")

    findings: List[Finding] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        rule_id = result.get("ruleId")
        if not isinstance(rule_id, str) or not rule_id:
            rule_id = "unknown-rule"
        rule = rules.get(rule_id, {})

        uri, line = _first_location(result)
        if uri is None:
            continue
        try:
            # Resolve o uri (não confiável) DENTRO do alvo. Fora → descarta.
            resolved = target.resolve(uri)
            rel = str(resolved.relative_to(target.root))
        except (ProjectBoundaryError, ValueError):
            if dropped is not None:
                dropped.append(uri)
            continue

        message = ""
        msg = result.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("text"), str):
            message = msg["text"][:2000]

        finding = Finding(
            scanner=scanner,
            rule=rule_id,
            severity=_severity_for(result, rule),
            confidence=Confidence.UNKNOWN,
            file=rel,
            line=line,
            message=message,
            project=project,
            state=FindingState.CANDIDATE,
        )
        # A origem é FACT: o scanner realmente reportou isto. Não é confirmação.
        finding.add_evidence(
            EvidenceKind.FACT,
            f"{scanner} regra {rule_id} em {rel}:{line}",
            source=scanner,
        )
        findings.append(finding)
    return findings


def _first_location(result: Dict[str, Any]) -> Tuple[str | None, int]:
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        return None, 0
    phys = (locations[0] or {}).get("physicalLocation") if isinstance(locations[0], dict) else None
    if not isinstance(phys, dict):
        return None, 0
    art = phys.get("artifactLocation")
    uri = art.get("uri") if isinstance(art, dict) else None
    if not isinstance(uri, str) or not uri:
        return None, 0
    region = phys.get("region")
    line = 0
    if isinstance(region, dict):
        try:
            line = int(region.get("startLine") or 0)
        except (TypeError, ValueError):
            line = 0
    return uri, line


def normalize_document(
    doc: Dict[str, Any], *, target: AuthorizedTarget, project: str = ""
) -> Tuple[List[Finding], List[str]]:
    """Normaliza todos os runs de um SARIF já validado. Devolve (findings, dropped)."""
    dropped: List[str] = []
    out: List[Finding] = []
    for run in doc.get("runs", []):
        if isinstance(run, dict):
            out.extend(normalize_run(run, target=target, project=project, dropped=dropped))
    return out, dropped
