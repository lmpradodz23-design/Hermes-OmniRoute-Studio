"""Incremental ProjectModel — the real system found (Wave 4, §40).

ProductSpec describes the *desired* product; ProjectModel describes the *actual*
system discovered in a repo. This derives a shallow-but-useful model (languages,
frameworks, entrypoints, routes/db/migrations/CI heuristics) from a file listing
+ manifests, and supports incremental per-file update. Pure heuristics — a later
increment can enrich it via the code graph / LSP. Kept distinct from ProductSpec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


_LANG_BY_EXT = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".rs": "rust", ".go": "go", ".java": "java", ".rb": "ruby",
    ".sql": "sql",
}

# manifest dependency substring -> framework
_FRAMEWORK_MARKERS = {
    "django": "django", "flask": "flask", "fastapi": "fastapi", "next": "nextjs",
    "react": "react", "express": "express", "vite": "vite", "capacitor": "capacitor",
    "electron": "electron",
}

_ENTRYPOINT_NAMES = frozenset({"main.py", "app.py", "manage.py", "index.js", "index.ts",
                               "server.py", "wsgi.py", "asgi.py", "run.py"})


def _ext(path: str) -> str:
    i = path.rfind(".")
    return path[i:].lower() if i >= 0 else ""


def _base(path: str) -> str:
    return path.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class ProjectModel:
    languages: dict[str, int] = field(default_factory=dict)   # lang -> file count
    frameworks: frozenset[str] = frozenset()
    entrypoints: tuple[str, ...] = ()
    routes: tuple[str, ...] = ()
    db_engines: frozenset[str] = frozenset()
    migrations: tuple[str, ...] = ()
    has_ci: bool = False
    test_dirs: frozenset[str] = frozenset()
    integrations: frozenset[str] = frozenset()

    @property
    def primary_language(self) -> str | None:
        return max(self.languages, key=self.languages.get) if self.languages else None


def detect(files: Iterable[str], manifest_deps: Iterable[str] = ()) -> ProjectModel:
    files = list(files)
    langs: dict[str, int] = {}
    entrypoints: list[str] = []
    migrations: list[str] = []
    routes: list[str] = []
    test_dirs: set[str] = set()
    has_ci = False
    db_engines: set[str] = set()

    for f in files:
        lang = _LANG_BY_EXT.get(_ext(f))
        if lang:
            langs[lang] = langs.get(lang, 0) + 1
        b = _base(f)
        if b in _ENTRYPOINT_NAMES:
            entrypoints.append(f)
        if "/migrations/" in f or f.startswith("migrations/"):
            migrations.append(f)
        if "route" in b.lower() or "urls.py" == b:
            routes.append(f)
        if f.startswith("tests/") or "/tests/" in f or b.startswith("test_"):
            test_dirs.add(f.rsplit("/", 1)[0] if "/" in f else "tests")
        if f.startswith(".github/workflows/"):
            has_ci = True

    frameworks: set[str] = set()
    integrations: set[str] = set()
    for dep in manifest_deps:
        low = dep.lower()
        for marker, fw in _FRAMEWORK_MARKERS.items():
            if marker in low:
                frameworks.add(fw)
        for db in ("postgres", "psycopg", "mysql", "sqlite", "mongo", "redis"):
            if db in low:
                db_engines.add("postgres" if db == "psycopg" else db)
        for integ in ("stripe", "twilio", "supabase", "vercel", "openai", "anthropic"):
            if integ in low:
                integrations.add(integ)

    return ProjectModel(
        languages=langs, frameworks=frozenset(frameworks), entrypoints=tuple(entrypoints),
        routes=tuple(routes), db_engines=frozenset(db_engines), migrations=tuple(migrations),
        has_ci=has_ci, test_dirs=frozenset(test_dirs), integrations=frozenset(integrations),
    )


__all__ = ["ProjectModel", "detect"]
