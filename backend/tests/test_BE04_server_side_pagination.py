"""
test_BE04_server_side_pagination.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: BE-04 · Implementar paginación server-side en find_all()
Correlaciones: Requiere BE-02, BE-03 · Complementa FE-01

Verifica que:
  - find_all() acepta parámetros page y page_size
  - El resultado incluye metadatos: {items, total, page, page_size, total_pages}
  - skip se calcula correctamente: (page - 1) * page_size
  - page_size respeta el límite máximo de 200 (validado en controller)
  - Default page_size=100 carga todos los 79 establecimientos actuales
  - total_pages se calcula con ceil(total / page_size)
"""
import pytest
import math
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import SAMPLE_ESTABLISHMENT, SAMPLE_ESTABLISHMENT_2


def make_async_cursor(docs):
    class FakeAsyncCursor:
        def __init__(self, items):
            self._items = iter(items)
            self._sorted = self
            self._skipped = self
            self._limited = self

        def sort(self, *args, **kwargs):
            return self

        def skip(self, n):
            return self

        def limit(self, n):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    return FakeAsyncCursor(docs)


# ─── Tests de firma del método ────────────────────────────────────────────────

def test_BE04_find_all_accepts_page_and_page_size_params():
    """BE-04: find_all() debe aceptar parámetros page y page_size."""
    import inspect
    from app.establishments.establishments_service import EstablishmentsService

    sig = inspect.signature(EstablishmentsService.find_all)
    params = sig.parameters

    assert "page" in params, (
        "find_all() no tiene el parámetro 'page'. "
        "Añadir: async def find_all(self, ..., page: int = 1, page_size: int = 100)"
    )
    assert "page_size" in params, (
        "find_all() no tiene el parámetro 'page_size'. "
        "Añadir: async def find_all(self, ..., page: int = 1, page_size: int = 100)"
    )


def test_BE04_page_default_is_1():
    """BE-04: El valor por defecto de page debe ser 1."""
    import inspect
    from app.establishments.establishments_service import EstablishmentsService

    sig = inspect.signature(EstablishmentsService.find_all)
    page_param = sig.parameters.get("page")

    assert page_param is not None
    assert page_param.default == 1, (
        f"El valor por defecto de 'page' es {page_param.default}, se esperaba 1."
    )


def test_BE04_page_size_default_covers_all_current_establishments():
    """BE-04: El page_size por defecto debe ser >= 100 para cargar todos los 79 establecimientos."""
    import inspect
    from app.establishments.establishments_service import EstablishmentsService

    sig = inspect.signature(EstablishmentsService.find_all)
    ps_param = sig.parameters.get("page_size")

    assert ps_param is not None
    assert ps_param.default >= 100, (
        f"page_size default es {ps_param.default}. "
        "Debe ser >= 100 para no romper el UX actual con 79 establecimientos."
    )


# ─── Tests de estructura de respuesta ────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE04_find_all_returns_paginated_dict_structure():
    """BE-04: find_all() debe retornar un dict con {items, total, page, page_size, total_pages}."""
    from app.establishments.establishments_service import EstablishmentsService

    docs = [
        {**SAMPLE_ESTABLISHMENT, "_id": "id1"},
        {**SAMPLE_ESTABLISHMENT_2, "_id": "id2"},
    ]

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor(docs))
    mock_collection.count_documents = AsyncMock(return_value=2)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_all(page=1, page_size=25)

    assert isinstance(result, dict), (
        f"find_all() devolvió {type(result).__name__} en lugar de dict. "
        "El resultado paginado debe ser: {'items': [...], 'total': N, 'page': 1, ...}"
    )

    required_keys = {"items", "total", "page", "page_size", "total_pages"}
    missing = required_keys - set(result.keys())
    assert not missing, (
        f"La respuesta paginada le faltan las claves: {missing}. "
        "El dict debe contener: items, total, page, page_size, total_pages."
    )


@pytest.mark.asyncio
async def test_BE04_total_pages_calculated_correctly():
    """BE-04: total_pages debe calcularse con ceil(total / page_size)."""
    from app.establishments.establishments_service import EstablishmentsService

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=make_async_cursor([]))
    mock_collection.count_documents = AsyncMock(return_value=79)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.find_all(page=1, page_size=25)

    expected_pages = math.ceil(79 / 25)  # = 4
    assert result["total_pages"] == expected_pages, (
        f"total_pages es {result['total_pages']}, se esperaba {expected_pages}. "
        f"Calcular con: math.ceil(total / page_size) = ceil(79/25) = {expected_pages}"
    )
    assert result["total"] == 79, (
        f"total es {result['total']}, se esperaba 79."
    )


# ─── Tests de skip/limit ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE04_skip_calculated_as_page_minus_one_times_page_size():
    """BE-04: skip debe calcularse como (page - 1) * page_size."""
    from app.establishments.establishments_service import EstablishmentsService

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = MagicMock(return_value=iter([]))
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.__aiter__ = lambda self: iter([])

    # Usar clase real con tracking
    class TrackingCursor:
        def __init__(self):
            self.skip_value = None
            self.limit_value = None

        def sort(self, *a, **kw): return self
        def skip(self, n): self.skip_value = n; return self
        def limit(self, n): self.limit_value = n; return self
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration

    tracking_cursor = TrackingCursor()

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=tracking_cursor)
    mock_collection.count_documents = AsyncMock(return_value=79)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        await svc.find_all(page=3, page_size=25)

    expected_skip = (3 - 1) * 25  # = 50
    assert tracking_cursor.skip_value == expected_skip, (
        f"skip es {tracking_cursor.skip_value}, se esperaba {expected_skip}. "
        "Calcular: skip = (page - 1) * page_size"
    )
    assert tracking_cursor.limit_value == 25, (
        f"limit es {tracking_cursor.limit_value}, se esperaba 25."
    )


# ─── Tests de controller (Query params) ───────────────────────────────────────

def test_BE04_controller_exposes_page_and_page_size_as_query_params():
    """BE-04: El controller debe exponer page y page_size como Query params de FastAPI."""
    import inspect
    from app.establishments.establishments_controller import get_establishments

    sig = inspect.signature(get_establishments)
    params = sig.parameters

    assert "page" in params, (
        "El controller get_establishments() no tiene 'page' como Query param. "
        "Añadir: page: int = Query(1, ge=1)"
    )
    assert "page_size" in params, (
        "El controller get_establishments() no tiene 'page_size' como Query param. "
        "Añadir: page_size: int = Query(100, ge=1, le=200)"
    )
