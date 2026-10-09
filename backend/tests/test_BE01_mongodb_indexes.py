"""
test_BE01_mongodb_indexes.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: BE-01 · Crear índices MongoDB en startup para colecciones críticas
Correlaciones: Prerequisito de BE-02, BE-03, BE-04, BE-07

Verifica que:
  - El método ensure_indexes() existe y es invocable
  - Crea los índices correctos en cada colección
  - Es idempotente (puede ejecutarse múltiples veces sin error)
  - Se llama automáticamente durante connect()
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call


# ─── Tests de existencia del método ──────────────────────────────────────────

def test_BE01_ensure_indexes_method_exists():
    """BE-01: database_service debe exponer el método ensure_indexes()."""
    from app.database.database_service import DatabaseService
    svc = DatabaseService()
    assert hasattr(svc, "ensure_indexes"), (
        "DatabaseService no tiene el método ensure_indexes(). "
        "Debe agregarse para crear índices al startup."
    )
    assert callable(svc.ensure_indexes), "ensure_indexes debe ser callable (coroutine)."


# ─── Tests de índices creados ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE01_indexes_created_on_establishments_rbd():
    """BE-01: Debe existir índice ÚNICO sobre establishments.rbd."""
    from app.database.database_service import DatabaseService

    mock_db = MagicMock()
    mock_db.establishments = MagicMock()
    mock_db.counterparts = MagicMock()
    mock_db.metrics = MagicMock()

    mock_db.establishments.create_index = AsyncMock()
    mock_db.counterparts.create_index = AsyncMock()
    mock_db.metrics.create_index = AsyncMock()
    mock_db.users = MagicMock(); mock_db.users.create_index = AsyncMock()
    mock_db.units = MagicMock(); mock_db.units.create_index = AsyncMock()

    svc = DatabaseService()
    svc.db = mock_db

    await svc.ensure_indexes()

    # Verificar que se creó índice único en rbd
    calls_est = [str(c) for c in mock_db.establishments.create_index.call_args_list]
    assert any("rbd" in c for c in calls_est), (
        "No se creó índice sobre establishments.rbd. "
        "Añadir: await self.db.establishments.create_index('rbd', unique=True)"
    )


@pytest.mark.asyncio
async def test_BE01_indexes_created_on_metrics_rbd_year_compound():
    """BE-01: Debe existir índice compuesto ÚNICO sobre metrics.{rbd, year}."""
    from app.database.database_service import DatabaseService

    mock_db = MagicMock()
    mock_db.establishments = MagicMock()
    mock_db.counterparts = MagicMock()
    mock_db.metrics = MagicMock()

    mock_db.establishments.create_index = AsyncMock()
    mock_db.counterparts.create_index = AsyncMock()
    mock_db.metrics.create_index = AsyncMock()
    mock_db.users = MagicMock(); mock_db.users.create_index = AsyncMock()
    mock_db.units = MagicMock(); mock_db.units.create_index = AsyncMock()

    svc = DatabaseService()
    svc.db = mock_db

    await svc.ensure_indexes()

    calls_met = [str(c) for c in mock_db.metrics.create_index.call_args_list]
    # El índice compuesto se pasa como lista de tuplas: [("rbd", 1), ("year", -1)]
    assert any("rbd" in c and "year" in c for c in calls_met), (
        "No se creó índice compuesto sobre metrics.{rbd, year}. "
        "Añadir: await self.db.metrics.create_index([('rbd', 1), ('year', -1)], unique=True)"
    )


@pytest.mark.asyncio
async def test_BE01_indexes_created_on_counterparts_rbd():
    """BE-01: Debe existir índice sobre counterparts.rbd."""
    from app.database.database_service import DatabaseService

    mock_db = MagicMock()
    mock_db.establishments = MagicMock()
    mock_db.counterparts = MagicMock()
    mock_db.metrics = MagicMock()

    mock_db.establishments.create_index = AsyncMock()
    mock_db.counterparts.create_index = AsyncMock()
    mock_db.metrics.create_index = AsyncMock()
    mock_db.users = MagicMock(); mock_db.users.create_index = AsyncMock()
    mock_db.units = MagicMock(); mock_db.units.create_index = AsyncMock()

    svc = DatabaseService()
    svc.db = mock_db

    await svc.ensure_indexes()

    calls_cp = [str(c) for c in mock_db.counterparts.create_index.call_args_list]
    assert any("rbd" in c for c in calls_cp), (
        "No se creó índice sobre counterparts.rbd. "
        "Añadir: await self.db.counterparts.create_index('rbd')"
    )


@pytest.mark.asyncio
async def test_BE01_indexes_created_on_metrics_year_for_analytics():
    """BE-01: Debe existir índice sobre metrics.year para soportar analytics pipelines."""
    from app.database.database_service import DatabaseService

    mock_db = MagicMock()
    mock_db.establishments = MagicMock()
    mock_db.counterparts = MagicMock()
    mock_db.metrics = MagicMock()

    mock_db.establishments.create_index = AsyncMock()
    mock_db.counterparts.create_index = AsyncMock()
    mock_db.metrics.create_index = AsyncMock()
    mock_db.users = MagicMock(); mock_db.users.create_index = AsyncMock()
    mock_db.units = MagicMock(); mock_db.units.create_index = AsyncMock()

    svc = DatabaseService()
    svc.db = mock_db

    await svc.ensure_indexes()

    calls_met = [str(c) for c in mock_db.metrics.create_index.call_args_list]
    # El índice simple en year debe existir (separado del compuesto rbd+year)
    has_year_index = any(
        ("year" in c and "rbd" not in c) or ("'year'" in c)
        for c in calls_met
    )
    assert has_year_index, (
        "No se creó índice simple sobre metrics.year. "
        "Añadir: await self.db.metrics.create_index('year')"
    )


# ─── Test de idempotencia ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE01_ensure_indexes_is_idempotent():
    """BE-01: ensure_indexes() puede ejecutarse múltiples veces sin lanzar excepciones."""
    from app.database.database_service import DatabaseService

    mock_db = MagicMock()
    mock_db.establishments.create_index = AsyncMock()
    mock_db.counterparts.create_index = AsyncMock()
    mock_db.metrics.create_index = AsyncMock()
    mock_db.users = MagicMock(); mock_db.users.create_index = AsyncMock()
    mock_db.units = MagicMock(); mock_db.units.create_index = AsyncMock()

    svc = DatabaseService()
    svc.db = mock_db

    # Ejecutar dos veces
    try:
        await svc.ensure_indexes()
        await svc.ensure_indexes()
    except Exception as e:
        pytest.fail(
            f"ensure_indexes() lanzó excepción al ejecutarse múltiples veces: {e}. "
            "Usar create_index con background=True o capturar DuplicateKeyError."
        )


# ─── Test de integración con connect() ───────────────────────────────────────

@pytest.mark.asyncio
async def test_BE01_ensure_indexes_called_during_connect():
    """BE-01: connect() debe llamar a ensure_indexes() automáticamente."""
    from app.database.database_service import DatabaseService

    svc = DatabaseService()

    with patch.object(svc, "ensure_indexes", new_callable=AsyncMock) as mock_ei, \
         patch.object(svc, "seed_if_empty", new_callable=AsyncMock) as mock_seed, \
         patch("app.database.database_service.AsyncIOMotorClient") as mock_client:

        mock_client.return_value.__getitem__ = MagicMock(return_value=MagicMock())

        await svc.connect()

        mock_ei.assert_called_once(), (
            "connect() no llama a ensure_indexes(). "
            "Añadir: await self.ensure_indexes() dentro de connect(), después de seed_if_empty()."
        )
