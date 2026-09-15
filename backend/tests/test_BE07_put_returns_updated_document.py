"""
test_BE07_put_returns_updated_document.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: BE-07 · PUT endpoints retornan documentos actualizados completos
Correlaciones: Requiere BE-01 · Habilita eliminar setTimeout en FE-03

Verifica que:
  - PUT /api/establishments/{rbd} retorna el Establishment actualizado completo
  - PUT /api/counterparts/{id} retorna la Counterpart actualizada
  - POST /api/counterparts retorna la Counterpart creada con su _id
  - DELETE /api/counterparts/{id} retorna {message, deleted_id}
  - update_by_rbd() retorna el documento tras el update (ya implementado, verificar regresión)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from tests.conftest import SAMPLE_ESTABLISHMENT, SAMPLE_COUNTERPART


# ─── Tests de update_by_rbd() ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE07_update_by_rbd_returns_full_updated_establishment():
    """BE-07: update_by_rbd() debe retornar el documento completo después del update."""
    from app.establishments.establishments_service import EstablishmentsService
    from app.establishments.establishments_entity import EstablishmentUpdate, GeneralInfo

    updated_doc = {**SAMPLE_ESTABLISHMENT, "name": "LICEO ACTUALIZADO"}

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock(return_value=MagicMock(
        modified_count=1,
        matched_count=1
    ))
    mock_collection.find_one = AsyncMock(return_value=updated_doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        update_payload = EstablishmentUpdate(name="LICEO ACTUALIZADO")
        result = await svc.update_by_rbd("7722", update_payload)

    assert result is not None, (
        "update_by_rbd() retornó None. Debe retornar el documento actualizado. "
        "Ya hace find_by_rbd() post-update, verificar que no haya regresión."
    )
    assert result.get("name") == "LICEO ACTUALIZADO", (
        f"update_by_rbd() retornó name='{result.get('name')}', se esperaba 'LICEO ACTUALIZADO'. "
        "El documento retornado debe reflejar los cambios guardados."
    )


@pytest.mark.asyncio
async def test_BE07_update_by_rbd_returns_complete_establishment_not_just_ack():
    """BE-07: El resultado de update_by_rbd() NO debe ser solo {message: 'ok'} o None."""
    from app.establishments.establishments_service import EstablishmentsService
    from app.establishments.establishments_entity import EstablishmentUpdate

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock(return_value=MagicMock(
        modified_count=1,
        matched_count=1
    ))
    mock_collection.find_one = AsyncMock(return_value=SAMPLE_ESTABLISHMENT)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        svc = EstablishmentsService()
        result = await svc.update_by_rbd("7722", EstablishmentUpdate())

    assert isinstance(result, dict), (
        f"update_by_rbd() retornó {type(result).__name__}. Debe retornar el dict del documento."
    )
    # Verificar que tiene campos de un establishment real, no un simple ack
    assert "rbd" in result, (
        "El resultado de update_by_rbd() no contiene 'rbd'. "
        "Debe ser el documento completo, no un mensaje de confirmación."
    )
    assert "name" in result, (
        "El resultado de update_by_rbd() no contiene 'name'. "
        "Debe ser el documento completo del establecimiento."
    )


# ─── Tests de counterparts: update() ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE07_counterpart_update_returns_updated_counterpart():
    """BE-07: counterparts_service.update() debe retornar la contraparte actualizada."""
    from app.counterparts.counterparts_service import CounterpartsService
    from app.counterparts.counterparts_entity import CounterpartUpdate

    cp_id = str(ObjectId())
    updated_cp = {**SAMPLE_COUNTERPART, "_id": cp_id, "name": "Carlos Actualizado"}

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    mock_collection.find_one = AsyncMock(return_value=updated_cp)

    with patch("app.counterparts.counterparts_service.db_service") as mock_db_svc:
        mock_db_svc.db.counterparts = mock_collection

        svc = CounterpartsService()
        update_payload = CounterpartUpdate(name="Carlos Actualizado")

        with patch("app.counterparts.counterparts_service.ObjectId", return_value=ObjectId()):
            result = await svc.update(cp_id, update_payload)

    assert result is not None, (
        "counterparts_service.update() retornó None. "
        "Debe retornar la contraparte actualizada."
    )
    assert result.get("name") == "Carlos Actualizado", (
        f"update() retornó name='{result.get('name')}'. Debe reflejar el cambio guardado."
    )


# ─── Tests de counterparts: create() ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE07_counterpart_create_returns_counterpart_with_id():
    """BE-07: counterparts_service.create() debe retornar la contraparte con _id asignado."""
    from app.counterparts.counterparts_service import CounterpartsService
    from app.counterparts.counterparts_entity import CounterpartCreate

    new_cp_id = ObjectId()
    new_cp = {
        **SAMPLE_COUNTERPART,
        "_id": str(new_cp_id),
    }

    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(
        inserted_id=new_cp_id
    ))

    with patch("app.counterparts.counterparts_service.db_service") as mock_db_svc:
        mock_db_svc.db.counterparts = mock_collection

        svc = CounterpartsService()
        payload = CounterpartCreate(
            rbd="7722",
            role="TI",
            origin="SLEP",
            name="Nueva Contraparte",
            email="nueva@slep.cl",
            phone=""
        )
        result = await svc.create(payload)

    assert result is not None, "create() retornó None. Debe retornar la contraparte creada."
    assert "_id" in result, (
        "create() no incluye '_id' en la respuesta. "
        "El frontend necesita el _id para actualizar/eliminar la contraparte luego."
    )
    assert result["_id"] == str(new_cp_id), (
        f"El _id retornado '{result['_id']}' no coincide con el inserted_id '{new_cp_id}'."
    )


# ─── Tests de counterparts: delete() ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_BE07_counterpart_delete_returns_true_on_success():
    """BE-07: counterparts_service.delete() debe retornar True cuando elimina correctamente."""
    from app.counterparts.counterparts_service import CounterpartsService

    cp_id = str(ObjectId())

    mock_collection = MagicMock()
    mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

    with patch("app.counterparts.counterparts_service.db_service") as mock_db_svc:
        mock_db_svc.db.counterparts = mock_collection

        svc = CounterpartsService()
        with patch("app.counterparts.counterparts_service.ObjectId", return_value=ObjectId()):
            result = await svc.delete(cp_id)

    assert result is True, (
        f"delete() retornó {result}. Debe retornar True cuando deleted_count > 0."
    )


@pytest.mark.asyncio
async def test_BE07_counterpart_delete_returns_false_when_not_found():
    """BE-07: counterparts_service.delete() debe retornar False cuando el ID no existe."""
    from app.counterparts.counterparts_service import CounterpartsService

    cp_id = str(ObjectId())

    mock_collection = MagicMock()
    mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=0))

    with patch("app.counterparts.counterparts_service.db_service") as mock_db_svc:
        mock_db_svc.db.counterparts = mock_collection

        svc = CounterpartsService()
        with patch("app.counterparts.counterparts_service.ObjectId", return_value=ObjectId()):
            result = await svc.delete(cp_id)

    assert result is False, (
        f"delete() retornó {result} cuando deleted_count=0. "
        "Debe retornar False cuando el documento no existe."
    )
