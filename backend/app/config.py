import os
import re
from typing import List, Mapping, Optional


class ConfigError(RuntimeError):
    """Configuración inválida o incompleta. Impide el arranque con un mensaje que nombra la variable."""


_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


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
