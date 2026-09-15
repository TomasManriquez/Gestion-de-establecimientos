"""
test_BE08_lifecycle_verification.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verifica el ciclo de vida completo (Creación y Modificación) de:
  - Contrapartes Técnicas
  - Impresoras (Propias y Arrendadas)
  - Configuración de Internet
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from tests.conftest import SAMPLE_ESTABLISHMENT, SAMPLE_COUNTERPART
from app.establishments.establishments_entity import (
    EstablishmentUpdate, Connectivity, Printers, OwnedPrinter, LeasedPrinter
)
from app.counterparts.counterparts_entity import CounterpartCreate, CounterpartUpdate

# ─── Technical Counterparts Lifecycle ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_counterpart_lifecycle_create_and_update():
    """Verifica que una contraparte técnica pueda ser creada y luego actualizada."""
    from app.counterparts.counterparts_service import CounterpartsService

    # Arrange
    svc = CounterpartsService()
    new_cp_id = ObjectId()
    cp_create_payload = CounterpartCreate(
        rbd="7722",
        role="TI",
        origin="SLEP",
        name="Juan Tech",
        email="juan@slep.cl",
        phone="+56911111111"
    )
    updated_cp_data = {**SAMPLE_COUNTERPART, "_id": str(new_cp_id), "name": "Juan Tech Updated"}
    
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_cp_id))
    mock_collection.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    mock_collection.find_one = AsyncMock(return_value=updated_cp_data)

    with patch("app.counterparts.counterparts_service.db_service") as mock_db_svc:
        mock_db_svc.db.counterparts = mock_collection

        # Act - Create
        created_cp = await svc.create(cp_create_payload)
        
        # Act - Update
        update_payload = CounterpartUpdate(name="Juan Tech Updated")
        updated_cp = await svc.update(str(new_cp_id), update_payload)

    # Assert
    assert created_cp["name"] == "Juan Tech"
    assert "_id" in created_cp
    assert updated_cp["name"] == "Juan Tech Updated"
    assert updated_cp["_id"] == str(new_cp_id)


# ─── Printers Lifecycle (Owned and Leased) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_printers_lifecycle_update_owned_and_leased():
    """Verifica que se puedan añadir y actualizar impresoras, probando que 'licitation' sea opcional."""
    from app.establishments.establishments_service import EstablishmentsService

    # Arrange
    svc = EstablishmentsService()
    rbd = "7722"
    
    # Create printer data: one owned with licitation, one owned without (testing optionality), one leased
    printers_data = Printers(
        owned=[
            OwnedPrinter(model="HP-1", qty=1, type="COLOR", provider="Prov1", licitation="LIC-123"),
            OwnedPrinter(model="HP-2", qty=1, type="BN", provider="Prov2", licitation=None), # Optional
        ],
        leased=[
            LeasedPrinter(type="COLOR", brand="Kyocera", model="K1", serie="S1", location="Oficina 1")
        ]
    )
    
    updated_doc = {**SAMPLE_ESTABLISHMENT, "printers": printers_data.model_dump()}
    
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1, matched_count=1))
    mock_collection.find_one = AsyncMock(return_value=updated_doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        # Act
        update_payload = EstablishmentUpdate(printers=printers_data)
        result = await svc.update_by_rbd(rbd, update_payload)

    # Assert
    assert result is not None
    assert len(result["printers"]["owned"]) == 2
    assert result["printers"]["owned"][0]["licitation"] == "LIC-123"
    assert result["printers"]["owned"][1]["licitation"] is None or result["printers"]["owned"][1]["licitation"] == ""
    assert len(result["printers"]["leased"]) == 1
    assert result["printers"]["leased"][0]["brand"] == "Kyocera"


# ─── Internet Settings Lifecycle ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_internet_settings_lifecycle_update():
    """Verifica la actualización de datos de conectividad/internet."""
    from app.establishments.establishments_service import EstablishmentsService

    # Arrange
    svc = EstablishmentsService()
    rbd = "7722"
    
    new_connectivity = Connectivity(
        internet_provider="STARLINK",
        internet_status="ACTIVO",
        ssid="Starlink_Wifi",
        ssid_password="new-password",
        test_date="2026-09-04",
        download_speed_2030="200"
    )
    
    updated_doc = {**SAMPLE_ESTABLISHMENT, "connectivity": new_connectivity.model_dump()}
    
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1, matched_count=1))
    mock_collection.find_one = AsyncMock(return_value=updated_doc)

    with patch("app.establishments.establishments_service.db_service") as mock_db_svc:
        mock_db_svc.db.establishments = mock_collection

        # Act
        update_payload = EstablishmentUpdate(connectivity=new_connectivity)
        result = await svc.update_by_rbd(rbd, update_payload)

    # Assert
    assert result is not None
    assert result["connectivity"]["internet_provider"] == "STARLINK"
    assert result["connectivity"]["download_speed_2030"] == "200"
    assert result["connectivity"]["ssid"] == "Starlink_Wifi"
