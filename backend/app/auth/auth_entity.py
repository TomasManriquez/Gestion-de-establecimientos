from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ─── Plataformas y roles (ADR-009) ───────────────────────────────────────────
PLATFORM_IAM = "iam"
PLATFORM_DATOS = "datos"
PLATFORM_SELLOVERDE = "selloverde"

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

# Combinaciones que declaran los controllers de `datos` (matriz de 04 §9.3)
DATOS_READ = (ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER)
DATOS_WRITE = (ROLE_ADMIN, ROLE_EDITOR)
DATOS_DELETE = (ROLE_ADMIN,)
IAM_ADMIN = (ROLE_ADMIN,)
# Roles que ven las credenciales en claro (C20): solo `viewer` las recibe redactadas.
SENSITIVE_ROLES = frozenset({ROLE_ADMIN, ROLE_EDITOR})


@dataclass
class AccessContext:
    """Resultado de `require_access`: quién es y qué rol tiene en la plataforma pedida.

    `user` es para el controller (por ejemplo `/me`). El service nunca recibe el usuario (L3):
    recibe `user_id` o booleanos como `include_sensitive`.
    """
    user_id: str
    role: Optional[str]
    user: dict = field(default_factory=dict, repr=False)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(..., min_length=1, max_length=254)   # correo, o username legado
    password: str = Field(..., min_length=1, max_length=1024)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class AccessSummary(BaseModel):
    platform_id: str
    role: str


class UserResponse(BaseModel):
    """Contrato de GET /api/auth/me. Los tres primeros campos son el contrato original;
    id, email y access son aditivos (no rompen a ningún cliente, 03 §8.2)."""
    username: str
    full_name: str
    role: str
    id: Optional[str] = None
    email: Optional[str] = None
    access: List[AccessSummary] = []


class PasswordPolicy(BaseModel):
    """Lo único que el cliente necesita para validar en vivo. Nunca incluye la lista de bloqueo."""
    min_length: int
    max_length: int
    require_char_classes: int


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(..., min_length=1, max_length=1024)
    new_password: str = Field(..., min_length=1, max_length=1024)


# ─── Política de contraseñas: listas de bloqueo (NIST SP 800-63B-4 §3.1.1.2) ─────────────
# Contraseñas comunes en español e inglés y variantes típicas de un SLEP. La lista de bloqueo
# real de un despliegue puede ampliarse; esta es la base mínima verificable por test.
COMMON_PASSWORDS = frozenset("""
password contrasena clave secreto admin administrador administrator qwerty qwertyuiop asdfgh asdfghjkl
zxcvbn zxcvbnm abc123 abcdef abcdefgh abcd1234 letmein welcome bienvenido bienvenida changeme cambiame
iloveyou monkey dragon master login passw0rd p4ssword pass1234 password1 password12 password123
password1234 contrasena1 contrasena12 contrasena123 contrasena1234 clave123 clave1234 clave12345
admin123 admin1234 admin12345 admin123456 administrador123 12345678 123456789 1234567890 12345678910
111111111 000000000 987654321 1q2w3e4r 1q2w3e4r5t 1qaz2wsx qazwsxedc q1w2e3r4 usuario usuario123
chile chile123 santiago santiago123 llanquihue puertovaras frutillar fresia losmuermos
slep slep123 slep1234 slep2026 slep2025 slepllanquihue slepllanquihue1 slepllanquihue123
slepllanquihue2026 slepllanquihue2025 slepllanquihue.cl educacion educacion123 colegio escuela
""".split())
# Palabras de contexto que no pueden formar parte de la contraseña
CONTEXT_WORDS = ("slepllanquihue", "llanquihue", "slepllan")
# Secuencias que un atacante prueba antes que nada: números, abecedario y filas del teclado
SEQUENCES = ("01234567890123456789", "98765432109876543210", "abcdefghijklmnopqrstuvwxyz",
             "zyxwvutsrqponmlkjihgfedcba", "qwertyuiopasdfghjklzxcvbnm", "mnbvcxzlkjhgfdsapoiuytrewq", "1q2w3e4r5t6y7u8i9o0p")
