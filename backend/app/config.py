import os
import re
from typing import List, Mapping, Optional
from urllib.parse import urlsplit


class ConfigError(RuntimeError):
    """Configuración inválida o incompleta. Impide el arranque con un mensaje que nombra la variable."""


_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_EMAIL_RE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")
_LOCAL_HOSTS = ("localhost", "127.0.0.1")
MAIL_MODES = ("gmail", "console")


class Settings:
    """Lee la configuración del entorno al instanciarse (T9).

    Las variables de identidad y de secreto NO tienen default: si falta una, la app no
    arranca (D2). Lo que no es secreto (política de contraseñas) tiene default y se valida
    en rango. Se instancia con un mapeo para poder probar cada caso sin tocar `os.environ`.
    """

    # Variables que `Settings` lee, para que un test compruebe que cada una está
    # declarada en .env.production.template y en los dos docker-compose.
    ENV_VARS = (
        "MONGODB_URL", "DATABASE_NAME", "JWT_SECRET", "ACCESS_TOKEN_EXPIRE_MINUTES",
        "ADMIN_PASSWORD", "BOOTSTRAP_ADMIN_EMAIL", "ALLOWED_EMAIL_DOMAINS",
        "PASSWORD_MIN_LENGTH", "PASSWORD_MAX_LENGTH", "PASSWORD_REQUIRE_CHAR_CLASSES",
        "MAIL_MODE", "PUBLIC_BASE_URL", "GMAIL_SENDER_ADDRESS", "GMAIL_REFRESH_TOKEN",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    )

    PROJECT_NAME: str = "SLEP Llanquihue - Gestión de Establecimientos"
    ALGORITHM: str = "HS256"

    def __init__(self, env: Optional[Mapping[str, str]] = None):
        self._env = os.environ if env is None else env

        self.MONGODB_URL: str = self._get("MONGODB_URL", "mongodb://localhost:27017")
        self.DATABASE_NAME: str = self._get("DATABASE_NAME", "slep_llanquihue")

        # Seguridad: sin default (D2)
        self.JWT_SECRET: str = self._required("JWT_SECRET")
        self.ADMIN_PASSWORD: str = self._required("ADMIN_PASSWORD")
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = self._int("ACCESS_TOKEN_EXPIRE_MINUTES", 180, minimum=1)

        # Identidad: sin default
        self.ALLOWED_EMAIL_DOMAINS: List[str] = self._domains(self._required("ALLOWED_EMAIL_DOMAINS"))
        self.BOOTSTRAP_ADMIN_EMAIL: str = self._required("BOOTSTRAP_ADMIN_EMAIL").strip().lower()
        if self.BOOTSTRAP_ADMIN_EMAIL.rpartition("@")[2] not in self.ALLOWED_EMAIL_DOMAINS:
            raise ConfigError(
                "BOOTSTRAP_ADMIN_EMAIL debe pertenecer a un dominio de ALLOWED_EMAIL_DOMAINS "
                f"({', '.join(self.ALLOWED_EMAIL_DOMAINS)})"
            )

        # Política de contraseñas (C17). NIST SP 800-63B-4 §3.1.1.2: 15 caracteres como único
        # factor, permitir al menos 64, sin reglas de composición.
        self.PASSWORD_MIN_LENGTH: int = self._int("PASSWORD_MIN_LENGTH", 15, minimum=8)
        self.PASSWORD_MAX_LENGTH: int = self._int("PASSWORD_MAX_LENGTH", 64, minimum=64)
        self.PASSWORD_REQUIRE_CHAR_CLASSES: int = self._int("PASSWORD_REQUIRE_CHAR_CLASSES", 0, minimum=0, maximum=4)
        if self.PASSWORD_MIN_LENGTH > self.PASSWORD_MAX_LENGTH:
            raise ConfigError("PASSWORD_MIN_LENGTH no puede ser mayor que PASSWORD_MAX_LENGTH")

        # Correo (ADR-012). MAIL_MODE y PUBLIC_BASE_URL son obligatorias y sin default: el enlace
        # de invitación se arma con PUBLIC_BASE_URL. Las credenciales de Gmail solo se exigen en
        # modo `gmail`; en `console` (solo desarrollo) el mensaje se escribe en el log.
        self.MAIL_MODE: str = self._required("MAIL_MODE").strip().lower()
        if self.MAIL_MODE not in MAIL_MODES:
            raise ConfigError(f"MAIL_MODE debe ser uno de {', '.join(MAIL_MODES)} (recibido: {self.MAIL_MODE!r})")
        self.PUBLIC_BASE_URL: str = self._base_url(self._required("PUBLIC_BASE_URL"))
        host = urlsplit(self.PUBLIC_BASE_URL).hostname or ""
        local = host in _LOCAL_HOSTS
        self.GMAIL_SENDER_ADDRESS: str = self._get("GMAIL_SENDER_ADDRESS", "").strip().lower()
        self.GMAIL_REFRESH_TOKEN: str = self._get("GMAIL_REFRESH_TOKEN", "").strip()
        self.GOOGLE_CLIENT_ID: str = self._get("GOOGLE_CLIENT_ID", "").strip()
        self.GOOGLE_CLIENT_SECRET: str = self._get("GOOGLE_CLIENT_SECRET", "").strip()
        if self.MAIL_MODE == "console":
            # Que no pueda quedar activo en producción sin querer: el log sale con el enlace.
            if not local:
                raise ConfigError(
                    "MAIL_MODE=console solo se permite con PUBLIC_BASE_URL en localhost o 127.0.0.1 "
                    f"(recibido: {host!r}); usa MAIL_MODE=gmail"
                )
        else:
            for name in ("GMAIL_SENDER_ADDRESS", "GMAIL_REFRESH_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
                if not getattr(self, name):
                    raise ConfigError(f"Con MAIL_MODE=gmail es obligatoria la variable: {name}")
            if not _EMAIL_RE.match(self.GMAIL_SENDER_ADDRESS):
                raise ConfigError("GMAIL_SENDER_ADDRESS debe ser una dirección de correo válida")
            if urlsplit(self.PUBLIC_BASE_URL).scheme != "https" and not local:
                raise ConfigError("Con MAIL_MODE=gmail, PUBLIC_BASE_URL debe usar https (el enlace lleva un token)")

    def __repr__(self) -> str:  # nunca volcar secretos en logs ni en tracebacks
        return "<Settings (valores ocultos)>"

    # ── lectura ──
    def _get(self, name: str, default: str) -> str:
        value = self._env.get(name)
        return default if value is None or value.strip() == "" else value

    def _required(self, name: str) -> str:
        value = self._env.get(name)
        if value is None or value.strip() == "":
            raise ConfigError(f"Variable de entorno obligatoria sin definir: {name}")
        return value

    def _int(self, name: str, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
        raw = self._env.get(name)
        if raw is None or raw.strip() == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            raise ConfigError(f"{name} debe ser un entero (recibido: {raw!r})")
        if minimum is not None and value < minimum:
            raise ConfigError(f"{name} debe ser >= {minimum} (recibido: {value})")
        if maximum is not None and value > maximum:
            raise ConfigError(f"{name} debe ser <= {maximum} (recibido: {value})")
        return value

    @staticmethod
    def _base_url(raw: str) -> str:
        """Origen público sin barra final ni ruta: se le añade `/definir-contrasena#token=…`."""
        value = raw.strip().rstrip("/")
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ConfigError(f"PUBLIC_BASE_URL debe ser una URL http(s) con host (recibido: {raw.strip()!r})")
        if parts.path or parts.query or parts.fragment or parts.username or parts.password:
            raise ConfigError("PUBLIC_BASE_URL debe ser solo el origen (esquema, host y puerto), sin ruta ni credenciales")
        return value

    @staticmethod
    def _domains(raw: str) -> List[str]:
        domains: List[str] = []
        for part in raw.split(","):
            d = part.strip().lstrip("@").lower()
            if not d:
                continue
            if not _DOMAIN_RE.match(d):
                raise ConfigError(f"ALLOWED_EMAIL_DOMAINS contiene un dominio inválido: {part.strip()!r}")
            if d not in domains:
                domains.append(d)
        if not domains:
            raise ConfigError("ALLOWED_EMAIL_DOMAINS no contiene ningún dominio")
        return domains


settings = Settings()
