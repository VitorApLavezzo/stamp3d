from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STORAGE_ROOT = _PROJECT_ROOT / "storage"


class Settings(BaseSettings):
    APP_NAME: str = "Stamp3D"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./stamp3d.db"

    UPLOAD_DIR: str = str(_STORAGE_ROOT / "uploads")
    EXPORT_DIR: str = str(_STORAGE_ROOT / "exports")
    TEMP_DIR:   str = str(_STORAGE_ROOT / "temp")
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # ── Vision APIs ────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""       # Google Gemini (gratuito)
    OPENAI_API_KEY: str = ""       # OpenAI GPT-4 Vision
    ANTHROPIC_API_KEY: str = ""    # Anthropic Claude Vision

    # Processamento de imagem
    IMAGE_SIZE: int = 1024
    MIN_LINE_WIDTH_MM: float = 1.2
 
    # Parâmetros padrão do carimbo (replicando fluxo Blender)
    STAMP_BASE_HEIGHT: float = 4.0
    STAMP_RELIEF_HEIGHT: float = 6.0
    STAMP_DIAMETER: float = 21.0       # mm — diâmetro real (210 * scale 0.1)
    STAMP_SCALE_X: float = 0.1
    STAMP_SCALE_Y: float = 0.1
    STAMP_SCALE_Z: float = 0.2
    STAMP_LOCATION_Z: float = 15.0
 
    # Impressão FDM / alimentício
    MIN_WALL_THICKNESS: float = 1.2
    MIN_DETAIL_DISTANCE: float = 0.8
    LAYER_HEIGHT: float = 0.2


    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()