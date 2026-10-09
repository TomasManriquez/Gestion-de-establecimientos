"""
test_BE45_module_dependency_graph.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-47 · Dirección de dependencias entre módulos (ADR-013 §4, L5)

Verifica que los imports entre módulos de `backend/app` respetan el grafo aprobado:

    auth → users → units → audit
                ├→ platforms → audit
                ├→ establishments
                └→ audit
    counterparts → users            mail (infraestructura) ← auth

La regla se aplica a services y entities (la capa de negocio). Los controllers, que solo
componen, pueden importar services de otros módulos y `auth` (para `require_access`).
Falla ante un ciclo o una arista que ADR-013 no declara.
"""
import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
SHARED = {"config", "database"}          # base común: cualquier módulo puede usarla

# Aristas permitidas entre services/entities (módulo -> módulos que puede importar)
ALLOWED = {
    "auth": {"users", "mail", "audit"},
    "users": {"units", "platforms", "establishments", "audit"},
    "units": {"audit"},
    "platforms": {"audit"},
    "counterparts": {"users"},
    "establishments": set(),
    "metrics": set(),
    "analytics": set(),
    "audit": set(),
    "mail": set(),
}


def _imported_modules(path: Path):
    mods = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            parts = name.split(".")
            if parts[0] == "app" and len(parts) > 1:
                mods.add(parts[1])
    return mods


def _business_files(module: str):
    return [p for p in (APP / module).glob("*.py") if p.name.endswith(("_service.py", "_entity.py")) or p.name == "mail_service.py"]


def _graph():
    return {m: set().union(*(_imported_modules(f) for f in _business_files(m)), set()) - {m} - SHARED for m in ALLOWED}


def test_BE45_every_app_module_is_declared():
    on_disk = {p.name for p in APP.iterdir() if p.is_dir() and p.name not in ("__pycache__", "database")}
    assert on_disk == set(ALLOWED), f"módulo sin declarar en ADR-013 / este test: {on_disk ^ set(ALLOWED)}"


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_BE45_service_and_entity_imports_follow_adr_013(module):
    actual = _graph()[module]
    assert actual <= ALLOWED[module], f"{module} importa {actual - ALLOWED[module]}, que ADR-013 no declara"


def test_BE45_graph_has_no_cycles():
    graph = _graph()
    visiting, done = set(), set()

    def visit(node, path):
        assert node not in visiting, f"ciclo: {' → '.join([*path, node])}"
        if node in done:
            return
        visiting.add(node)
        for nxt in graph[node]:
            visit(nxt, [*path, node])
        visiting.discard(node)
        done.add(node)

    for module in graph:
        visit(module, [])


# Excepción conocida desde F3: `require_access` (una dependencia de FastAPI) vive en auth_service.
FASTAPI_EXCEPTIONS = {"auth_service.py"}


def test_BE45_services_do_not_import_fastapi():
    for module in ALLOWED:
        for f in _business_files(module):
            if f.name in FASTAPI_EXCEPTIONS:
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"))
            mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            assert not any(m == "fastapi" or m.startswith("fastapi.") for m in mods), f"{f.name} importa fastapi (L2)"
