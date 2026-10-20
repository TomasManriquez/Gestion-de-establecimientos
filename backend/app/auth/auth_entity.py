from dataclasses import dataclass, field
from typing import List, Optional

from html import escape as html_escape
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


class GoogleLoginRequest(BaseModel):
    """Body de POST /api/auth/google: solo el `credential` (id_token) de Google Identity Services."""
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(..., min_length=1)    # sin max_length: un 422 devolvería el valor en el cuerpo


class AuthConfig(BaseModel):
    google_client_id: str


class PasswordPolicy(BaseModel):
    """Lo único que el cliente necesita para validar en vivo. Nunca incluye la lista de bloqueo."""
    min_length: int
    max_length: int
    require_char_classes: int


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(..., min_length=1, max_length=1024)
    new_password: str = Field(..., min_length=1, max_length=1024)


class SetPasswordRequest(BaseModel):
    """Canje del enlace de invitación o de restablecimiento. El token viaja en el cuerpo, nunca en la URL."""
    model_config = ConfigDict(extra="forbid")
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., min_length=1, max_length=1024)


# ─── Enlaces de un solo uso (ADR-012, 02 §9.7) ───────────────────────────────────────────
INVITE_TTL_HOURS = 72
RESET_TTL_HOURS = 24
PURPOSE_INVITE = "invite"
PURPOSE_RESET = "reset"
SET_PASSWORD_PATH = "/definir-contrasena"
# Rate limiting (ADR-014). Ventana fija; el contador vive en `rate_limits` con TTL.
LOGIN_ACCOUNT_LIMIT = 5        # fallos por (cuenta + IP) en la ventana: no bloquea la cuenta para todo el mundo
LOGIN_IP_LIMIT = 30            # fallos por IP, para frenar el recorrido de muchas cuentas
LOGIN_WINDOW_SECONDS = 15 * 60
GOOGLE_IP_LIMIT = 30           # rechazos de /auth/google por IP (probar credenciales robadas o dominios)
GOOGLE_WINDOW_SECONDS = 15 * 60
REDEEM_IP_LIMIT = 10           # canjes fallidos por IP (adivinar enlaces)
REDEEM_WINDOW_SECONDS = 15 * 60
SEND_TARGET_LIMIT = 5          # envíos (reenvío o restablecimiento) por usuario destinatario: no llenar su bandeja
SEND_ACTOR_LIMIT = 60          # envíos por administrador
SEND_WINDOW_SECONDS = 60 * 60
INVITE_BATCH_LIMIT = 200       # cuota de Gmail: el envío masivo se parte en lotes de 200, en serie


class InvalidLink(Exception):
    """El enlace no se puede canjear. Usado, vencido, inexistente o de un usuario en otro estado
    responden igual: no se distingue el motivo hacia afuera."""


class RateLimited(Exception):
    """Se superó un límite. `retry_after` son los segundos hasta que se libera la ventana."""

    def __init__(self, retry_after: int):
        super().__init__("rate limited")
        self.retry_after = retry_after


class PasswordPolicyError(Exception):
    def __init__(self, violations: list):
        super().__init__("password policy violated")
        self.violations = violations


# ─── Plantillas de correo ────────────────────────────────────────────────────────────────
# Viven en `auth` y no son un endpoint: nadie puede mandar un texto propio por la casilla del SLEP.
# Todo dato del usuario se escapa (el nombre llega de un formulario o de un CSV).
SYSTEM_NAME = "Sistema de Gestión de Establecimientos · SLEP Llanquihue"


def _email_layout(heading: str, paragraphs: list, button_label: str, link: str, footer: str) -> str:
    body = "".join(f'<p style="margin:0 0 14px;font-size:15px;line-height:1.5;color:#1e293b">{p}</p>' for p in paragraphs)
    href = html_escape(link, quote=True)
    return (
        '<!doctype html><html lang="es"><body style="margin:0;padding:24px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#ffffff;border-radius:12px;padding:32px">'
        f'<tr><td><p style="margin:0 0 4px;font-size:12px;font-weight:bold;letter-spacing:.08em;color:#0369a1">{html_escape(SYSTEM_NAME)}</p>'
        f'<h1 style="margin:0 0 20px;font-size:22px;color:#0f172a">{html_escape(heading)}</h1>{body}'
        f'<p style="margin:24px 0"><a href="{href}" style="display:inline-block;background:#0284c7;color:#ffffff;'
        f'text-decoration:none;font-weight:bold;padding:12px 24px;border-radius:8px">{html_escape(button_label)}</a></p>'
        f'<p style="margin:0 0 6px;font-size:12px;color:#64748b">Si el botón no funciona, copia este enlace en tu navegador:</p>'
        f'<p style="margin:0 0 18px;font-size:12px;word-break:break-all;color:#0369a1">{href}</p>'
        f'<p style="margin:0;font-size:12px;color:#64748b">{html_escape(footer)}</p>'
        '</td></tr></table></td></tr></table></body></html>'
    )


def render_invitation(first_name: str, link: str, hours: int = INVITE_TTL_HOURS):
    """(asunto, html, texto) de la invitación. `link` ya lleva el token en el fragmento."""
    name = html_escape(first_name or "")
    subject = "Define tu contraseña para ingresar al sistema del SLEP Llanquihue"
    html = _email_layout(
        "Te damos la bienvenida",
        [f"Hola {name}, el SLEP Llanquihue creó una cuenta para ti en el sistema de gestión.",
         f"Para activarla, define tu contraseña con el siguiente enlace. Es de un solo uso y vence en {hours} horas."],
        "Definir mi contraseña", link,
        "Si no esperabas este correo, ignóralo: sin definir la contraseña, la cuenta no se activa.")
    text = (f"Hola {first_name},\n\nEl SLEP Llanquihue creó una cuenta para ti en el sistema de gestión.\n"
            f"Define tu contraseña con este enlace (un solo uso, vence en {hours} horas):\n\n{link}\n\n"
            "Si no esperabas este correo, ignóralo: sin definir la contraseña, la cuenta no se activa.\n")
    return subject, html, text


def render_password_reset(first_name: str, link: str, hours: int = RESET_TTL_HOURS):
    name = html_escape(first_name or "")
    subject = "Restablece tu contraseña del sistema del SLEP Llanquihue"
    html = _email_layout(
        "Restablecer contraseña",
        [f"Hola {name}, un administrador solicitó restablecer tu contraseña.",
         f"Define una nueva con el siguiente enlace. Es de un solo uso y vence en {hours} horas. "
         "Tu contraseña actual sigue funcionando hasta que completes el cambio."],
        "Definir una nueva contraseña", link,
        "Si no esperabas este correo, avisa a quien administra el sistema; no necesitas hacer nada más.")
    text = (f"Hola {first_name},\n\nUn administrador solicitó restablecer tu contraseña.\n"
            f"Define una nueva con este enlace (un solo uso, vence en {hours} horas):\n\n{link}\n\n"
            "Tu contraseña actual sigue funcionando hasta que completes el cambio.\n"
            "Si no esperabas este correo, avisa a quien administra el sistema.\n")
    return subject, html, text


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
