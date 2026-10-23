from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional, Any

# Printers sub-models
class OwnedPrinter(BaseModel):
    model: str
    qty: int
    type: str  # COLOR / BN
    provider: str
    licitation: Optional[str] = ""
    expiry_date: Optional[str] = ""
    obs: Optional[str] = ""

class LeasedPrinter(BaseModel):
    type: str  # COLOR / BN
    brand: str
    model: str
    serie: str
    bandeja_serial: Optional[str] = ""
    oc_equipo: Optional[str] = ""
    oc_bandeja: Optional[str] = ""
    has_furniture: Optional[bool] = False
    location: str
    support_contact: Optional[str] = ""
    support_mail: Optional[str] = ""
    support_phone: Optional[str] = ""
    director: Optional[str] = ""
    director_email: Optional[str] = ""
    director_phone2: Optional[str] = ""
    ip_address: Optional[str] = ""
    sds_kfs: Optional[str] = ""
    obs: Optional[str] = ""
    install_date: Optional[str] = ""
    initial_counter: Optional[int] = 0

class Printers(BaseModel):
    owned: List[OwnedPrinter] = []
    leased: List[LeasedPrinter] = []

# Connectivity sub-models
# Tres bloques independientes (un establecimiento puede tener los tres): programa 2030, BAM y
# otro tipo de conexión. «Sin internet» no se guarda: se calcula (`connectivity_migration.without_internet`).
Status2030 = Literal["fibra_optica", "microondas", "starlink", "satelital", "pendiente_instalacion", "sin_internet"]
OtherType = Literal["fibra_optica", "starlink", "microondas", "satelital", "movil", "otro"]


class BamEntry(BaseModel):
    number: str = ""
    oc: str = ""
    imei: str = ""
    device: str = ""
    holder: str = ""
    carrier: Optional[str] = ""          # operador (Movistar, Entel…) cuando viene del contrato
    qty: Optional[int] = Field(None, ge=0, le=1000)
    start: Optional[str] = ""
    term: Optional[str] = ""
    end: Optional[str] = ""


class Program2030(BaseModel):
    """Conectividad 2030 (Telsur). Starlink financiado por el programa es un `status`, no un bloque aparte."""
    enabled: bool = False
    status: Optional[Status2030] = None
    download_speed: Optional[str] = Field("", max_length=20)
    test_date: Optional[str] = ""


class OtherConnection(BaseModel):
    """Conexión contratada fuera del 2030 (incluido Starlink independiente). Vacía = no tiene."""
    provider: Optional[str] = Field("", max_length=80)
    type: Optional[OtherType] = None
    download_speed: Optional[str] = Field("", max_length=20)
    oc: Optional[str] = Field("", max_length=80)
    expiry_date: Optional[str] = Field("", max_length=10)          # AAAA-MM-DD
    support_whatsapp: Optional[str] = Field("", max_length=30)


class InternalNetwork(BaseModel):
    installed_year: Optional[str] = ""
    points_count: Optional[str] = ""
    status: Optional[str] = ""
    obs: Optional[str] = ""


class Connectivity(BaseModel):
    program_2030: Program2030 = Program2030()
    ssid: Optional[str] = ""             # red wifi del 2030
    ssid_password: Optional[str] = ""    # secreta: redactada para `viewer` (04 §3)
    bam: List[BamEntry] = []
    other: OtherConnection = OtherConnection()
    internal_network: InternalNetwork = InternalNetwork()
    phone_extensions: List[str] = []

# General Info sub-model
class GeneralInfo(BaseModel):
    director: Optional[str] = ""
    director_email: Optional[str] = ""
    director_phone: Optional[str] = ""
    category: Optional[str] = ""
    covertura: Optional[str] = ""
    adp: Optional[str] = ""
    pame: Optional[str] = ""
    uni_bi_tridocente: Optional[str] = ""
    microcentro: Optional[str] = ""
    coordinador_microcentro: Optional[str] = ""
    detalle_niveles_combinados: Optional[str] = ""
    nivel_transicion_nt: Optional[str] = ""
    priorizado_asistencia: Optional[str] = ""
    distancia_cafra: Optional[str] = ""

# Geolocation sub-model
class Location(BaseModel):
    lat: float
    lng: float

# Estado del establecimiento. Uno cerrado no se borra: conserva su ficha y su historia, y deja
# de recibir métricas de años posteriores. `closed_year` es el año en que cerró.
EstablishmentStatus = Literal["active", "closed"]


# Main Models
class Establishment(BaseModel):
    rbd: str
    rbd_dv: str = ""
    rbd_full: str
    name: str
    comuna: str
    area_type: str  # URBANO / RURAL
    address: str
    location: Optional[Location] = None
    status: EstablishmentStatus = "active"
    closed_year: Optional[int] = None
    general_info: GeneralInfo = GeneralInfo()
    connectivity: Connectivity = Connectivity()
    printers: Printers = Printers()

class EstablishmentUpdate(BaseModel):
    name: Optional[str] = None
    comuna: Optional[str] = None
    area_type: Optional[str] = None
    address: Optional[str] = None
    location: Optional[Location] = None
    status: Optional[EstablishmentStatus] = None
    closed_year: Optional[int] = Field(None, ge=2000, le=2100)
    general_info: Optional[GeneralInfo] = None
    connectivity: Optional[Connectivity] = None
    printers: Optional[Printers] = None

    @model_validator(mode="after")
    def _closing_needs_a_year(self):
        if self.closed_year is not None and self.status is None:
            raise ValueError("closed_year se envía junto con status")
        if self.status == "closed" and self.closed_year is None:
            raise ValueError("un establecimiento cerrado necesita closed_year")
        if self.status == "active" and self.closed_year is not None:
            raise ValueError("un establecimiento activo no lleva closed_year")
        return self

class EstablishmentSummary(BaseModel):
    rbd: str
    rbd_full: str
    name: str
    comuna: str
    area_type: str
    address: str = ""
    category: Optional[str] = ""
    adp: Optional[str] = ""
    covertura: Optional[str] = ""
    status: EstablishmentStatus = "active"
    closed_year: Optional[int] = None

class EstablishmentListResponse(BaseModel):
    items: List[EstablishmentSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class RedactedPlaceholderError(Exception):
    """Llegó "[REDACTED]" en un campo secreto y no hay un valor almacenado equivalente al que
    corresponda. El backend no adivina: rechaza (422) en vez de guardar el marcador."""
    def __init__(self, field: str):
        super().__init__(f"El valor de {field} es el marcador [REDACTED] y no hay un valor almacenado equivalente")
        self.field = field
