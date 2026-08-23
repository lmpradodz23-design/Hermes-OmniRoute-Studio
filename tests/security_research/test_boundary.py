"""Defesa de fronteira de projeto — o núcleo de segurança do módulo.

Estes testes são adversariais de propósito: cada um é uma forma real de fazer
"analise meu projeto" virar leitura de outro lugar. Se um passar a falhar, um
escape de path traversal foi aberto.
"""

import os

import pytest

from security_research.boundary import (
    AuthorizedTarget,
    ProjectBoundaryError,
    resolve_within_target,
    validate_target_root,
)


@pytest.fixture
def target(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    return AuthorizedTarget.create(str(tmp_path))


def test_valid_relative_path_resolves(target):
    resolved = target.resolve("src/app.py")
    assert resolved.name == "app.py"
    assert target.contains(resolved)


@pytest.mark.parametrize(
    "escape",
    [
        "../etc/passwd",
        "../../etc/passwd",
        "src/../../etc/passwd",
        "./../../etc/passwd",
        "src/../../../root/.ssh/id_rsa",
    ],
)
def test_dotdot_escape_is_rejected(target, escape):
    with pytest.raises(ProjectBoundaryError):
        target.resolve(escape)


@pytest.mark.parametrize(
    "absolute",
    [
        "/etc/passwd",
        "/root/.ssh/id_rsa",
        "C:\\Windows\\System32\\config\\SAM",
        "C:/Windows/System32",
        "\\\\server\\share\\secret",
        "//server/share/secret",
        "C:relativo",
    ],
)
def test_absolute_and_rooted_paths_are_rejected(target, absolute):
    # Testa gramática POSIX E Windows: um caminho Windows não pode escapar num
    # host POSIX só porque o os.path local não reconhece o drive.
    with pytest.raises(ProjectBoundaryError):
        target.resolve(absolute)


def test_symlink_pointing_outside_is_not_followed(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("SENHA")
    # symlink DENTRO do projeto apontando para fora — o ataque que uma checagem
    # só textual deixaria passar.
    link = root / "innocent.txt"
    try:
        os.symlink(secret, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink indisponível neste ambiente")
    target = AuthorizedTarget.create(str(root))
    with pytest.raises(ProjectBoundaryError):
        target.resolve("innocent.txt")


def test_nul_byte_is_rejected(target):
    with pytest.raises(ProjectBoundaryError):
        target.resolve("src/app\x00.py")


def test_empty_path_is_rejected(target):
    with pytest.raises(ProjectBoundaryError):
        target.resolve("   ")


def test_nonexistent_target_is_rejected(tmp_path):
    with pytest.raises(ProjectBoundaryError):
        validate_target_root(str(tmp_path / "nao-existe"))


def test_file_as_target_is_rejected(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(ProjectBoundaryError):
        validate_target_root(str(f))


def test_the_target_root_itself_resolves(target):
    # "." resolve para a própria raiz — dentro da fronteira, não um escape.
    assert resolve_within_target(target.root, ".") == target.root
