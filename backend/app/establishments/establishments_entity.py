from pydantic import BaseModel, Field
from typing import List, Optional, Any

# Printers sub-models
class OwnedPrinter(BaseModel):
    model: str
    qty: int
    type: str  # COLOR / BN
    provider: str
    licitation: str
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
class BamEntry(BaseModel):
    number: str
    oc: str
    imei: str
    device: str
    holder: str
    start: Optional[str] = ""
    term: Optional[str] = ""
    end: Optional[str] = ""

class Starlink(BaseModel):
    installed: bool = False
    date: Optional[str] = ""

class InternalNetwork(BaseModel):
    installed_year: Optional[str] = ""
    points_count: Optional[str] = ""
    status: Optional[str] = ""
    obs: Optional[str] = ""

class Connectivity(BaseModel):
    internet_provider: Optional[str] = ""
    internet_status: Optional[str] = ""
    ssid: Optional[str] = ""
    ssid_password: Optional[str] = ""
    test_date: Optional[str] = ""
    download_speed_2030: Optional[str] = ""
    bam: List[BamEntry] = []
    starlink: Starlink = Starlink()
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

# Main License sub-model
class LicenseCredential(BaseModel):
    name: str
    email: str
    password: str
    url: Optional[str] = ""
    obs: Optional[str] = ""
    is_new: Optional[bool] = False

# Main Models
class Establishment(BaseModel):
    rbd: str
    rbd_dv: str = ""
    rbd_full: str
    name: str
    comuna: str
    area_type: str  # URBANO / RURAL
    address: str
    general_info: GeneralInfo = GeneralInfo()
    connectivity: Connectivity = Connectivity()
    printers: Printers = Printers()
    licenses: List[LicenseCredential] = []

class EstablishmentUpdate(BaseModel):
    name: Optional[str] = None
    comuna: Optional[str] = None
    area_type: Optional[str] = None
    address: Optional[str] = None
    general_info: Optional[GeneralInfo] = None
    connectivity: Optional[Connectivity] = None
    printers: Optional[Printers] = None
    licenses: Optional[List[LicenseCredential]] = None
