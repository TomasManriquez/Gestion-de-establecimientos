import os

class Settings:
    PROJECT_NAME: str = "SLEP Llanquihue - Gestión de Establecimientos"
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "slep_llanquihue")
    
    # Security config
    # Use a secure default key in development
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-slep-key-2026-llanquihue-digital-management")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "180")) # 3 hours

settings = Settings()
