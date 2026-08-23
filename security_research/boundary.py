"""Fronteira de projeto — o alvo de análise é escolhido explicitamente e nada
escapa dele.

O Security Research só pode ler/analisar o `AUTHORIZED_SECURITY_TARGET` que o
usuário selecionou. Toda a defesa de path traversal do módulo mora aqui, num só
lugar, porque um caminho que escapa do alvo é como uma análise "do meu projeto"
vira leitura de `~/.ssh` ou de outro repositório.

Regras (todas testadas em tests/security_research/test_boundary.py):

  * o root do alvo é resolvido para um caminho real (symlinks resolvidos) e tem
    que ser um diretório existente;
  * qualquer caminho relativo é resolvido SOB o root e reconferido depois de
    resolver symlinks — um symlink dentro do projeto apontando para fora é
    rejeitado, não seguido;
  * `..`, caminhos absolutos, raízes alternativas (drive/UNC no Windows),
    NUL bytes e nomes vazios são recusados antes de tocar o filesystem.

Nada aqui executa nada. É só resolução de caminho — de propósito.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


class ProjectBoundaryError(Exception):
    """Um caminho tentou sair do alvo autorizado, ou o alvo é inválido."""


def validate_target_root(raw: str) -> Path:
    """Valida e canoniza a raiz do alvo de análise.

    Devolve o caminho real (symlinks resolvidos). Levanta
    ``ProjectBoundaryError`` se não for um diretório existente ou se contiver
    um NUL byte (que trunca caminhos em várias syscalls).
    """
    if not raw or not str(raw).strip():
        raise ProjectBoundaryError("alvo vazio")
    text = str(raw)
    if "\x00" in text:
        raise ProjectBoundaryError("NUL byte no caminho do alvo")

    try:
        # strict=True: o alvo TEM que existir; resolve symlinks até o real.
        resolved = Path(text).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProjectBoundaryError(f"alvo inacessível: {exc}") from exc

    if not resolved.is_dir():
        raise ProjectBoundaryError("o alvo precisa ser um diretório")
    return resolved


def _looks_absolute_or_rooted(rel: str) -> bool:
    """True se ``rel`` for absoluto em POSIX OU Windows, ou tiver drive/UNC.

    Checar as duas gramáticas de propósito: um caminho vindo de um projeto
    Windows analisado num host POSIX (ou o contrário) não pode escapar só
    porque a gramática nativa não reconheceu a raiz.
    """
    if PurePosixPath(rel).is_absolute():
        return True
    win = PureWindowsPath(rel)
    if win.is_absolute() or win.drive or win.root:
        return True
    # `C:foo` (drive-relative no Windows) e `\\server\share`.
    if len(rel) >= 2 and rel[1] == ":":
        return True
    if rel[:2] in ("\\\\", "//"):
        return True
    return False


@dataclass(frozen=True)
class AuthorizedTarget:
    """O alvo de segurança autorizado — a única árvore que o módulo pode tocar.

    Construa via :func:`validate_target_root`. `resolve` é o ÚNICO jeito
    sancionado de transformar um caminho relativo (vindo de um scanner, de um
    SARIF, de saída de LLM — tudo não confiável) num caminho absoluto usável.
    """

    root: Path

    @classmethod
    def create(cls, raw: str) -> "AuthorizedTarget":
        return cls(root=validate_target_root(raw))

    def resolve(self, relative: str) -> Path:
        return resolve_within_target(self.root, relative)

    def contains(self, path: str | os.PathLike[str]) -> bool:
        try:
            resolved = Path(path).resolve()
        except (OSError, RuntimeError):
            return False
        return self._is_under(resolved)

    def _is_under(self, resolved: Path) -> bool:
        try:
            resolved.relative_to(self.root)
            return True
        except ValueError:
            return False


def resolve_within_target(root: Path, relative: str) -> Path:
    """Resolve ``relative`` sob ``root``, recusando qualquer escape.

    O ``relative`` é NÃO CONFIÁVEL: vem de saída de scanner, de um SARIF, de um
    LLM. A checagem é feita DEPOIS de resolver symlinks (`os.path.realpath`),
    porque um `..` textual é o ataque fácil e um symlink interno apontando para
    fora é o ataque que passa por uma checagem só textual.
    """
    if relative is None:
        raise ProjectBoundaryError("caminho relativo nulo")
    text = str(relative)
    if "\x00" in text:
        raise ProjectBoundaryError("NUL byte no caminho")
    if not text.strip():
        raise ProjectBoundaryError("caminho relativo vazio")
    if _looks_absolute_or_rooted(text):
        raise ProjectBoundaryError(f"caminho absoluto/rooted rejeitado: {text!r}")

    root_real = os.path.realpath(root)
    # Junta como caminho e resolve symlinks. `..` sobra é colapsado pelo
    # realpath; se o resultado sair da raiz, rejeita.
    candidate = os.path.realpath(os.path.join(root_real, text))

    if candidate != root_real and not candidate.startswith(root_real + os.sep):
        raise ProjectBoundaryError(
            f"caminho escapa do alvo autorizado: {text!r} -> {candidate!r}"
        )
    return Path(candidate)
