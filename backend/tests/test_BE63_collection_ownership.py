"""
test_BE63_collection_ownership.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: límites entre módulos (ADR-019, L11)

`test_BE45_*` vigila los `import` entre módulos; esta prueba vigila lo que esa no ve: que un módulo lea
o escriba la colección de otro con `db_service.db.<colección>`. Cada colección tiene un solo módulo dueño;
los demás la consumen por su servicio.

Excepciones declaradas, ambas de infraestructura de arranque:
  - `database/`: crea los índices de todas las colecciones y siembra la carga inicial.
  - `database/seed_service.py` puede importar `establishments.connectivity_service` (función pura).
"""
import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

OWNER = {
    "auth": {"auth_tokens", "rate_limits"},
    "users": {"users"},
    "units": {"units", "subrogations"},
    "platforms": {"platforms"},
    "audit": {"audit_log"},
    "access": {"resource_grants"},
    "establishments": {"establishments"},
    "counterparts": {"counterparts"},
    "metrics": {"metrics"},
    "analytics": set(),
    "mail": set(),
}
INFRASTRUCTURE = {"database"}


def _collections_used(path: Path):
    """Nombres `X` en expresiones `db_service.db.X` o `<algo>.db.X` dentro del archivo."""
    used = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) and node.value.attr == "db":
            used.add(node.attr)
    return used


def _module_dirs():
    return sorted(p.name for p in APP.iterdir() if p.is_dir() and p.name != "__pycache__")


def test_BE63_every_module_is_declared():
    assert set(_module_dirs()) == set(OWNER) | INFRASTRUCTURE, "módulo nuevo sin dueño de colecciones declarado"


@pytest.mark.parametrize("module", sorted(OWNER))
def test_BE63_module_only_touches_its_own_collections(module):
    foreign = {}
    for f in (APP / module).glob("*.py"):
        extra = _collections_used(f) - OWNER[module]
        if extra:
            foreign[f.name] = sorted(extra)
    assert not foreign, f"{module} usa colecciones de otro módulo: {foreign} (consúmelas por el servicio dueño)"


def test_BE63_every_collection_has_one_owner():
    owners = [c for cols in OWNER.values() for c in cols]
    assert len(owners) == len(set(owners)), "una colección con dos dueños"


def test_BE63_database_only_imports_the_declared_exception():
    allowed = {("seed_service.py", "app.establishments.connectivity_service")}
    found = set()
    for f in (APP / "database").glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[:2] != ["app", "database"] \
                    and node.module.startswith("app.") and node.module != "app.config":
                found.add((f.name, node.module))
    assert found <= allowed, f"database importa módulos de dominio no declarados: {found - allowed}"
