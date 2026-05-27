"""
Stamp3D - Sistema de Geração Automática de Carimbos 3D para Doces
Backend FastAPI - Ponto de entrada principal
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from api.routes import upload, process, export, projects
from core.config import settings
from core.database import init_db

# Diretório raiz do projeto (pai de backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando Stamp3D Backend...")

    # Criar diretórios de storage com path absoluto
    for sub in ["uploads", "exports", "temp"]:
        (STORAGE_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Atualizar settings com paths absolutos
    settings.UPLOAD_DIR = str(STORAGE_DIR / "uploads")
    settings.EXPORT_DIR = str(STORAGE_DIR / "exports")
    settings.TEMP_DIR   = str(STORAGE_DIR / "temp")

    await init_db()
    logger.info("✅ Stamp3D pronto!")
    yield
    logger.info("🔴 Encerrando Stamp3D Backend...")


app = FastAPI(
    title="Stamp3D API",
    description="Sistema Automatizado de Carimbos 3D para Doces",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar storage com path absoluto (evita erro de diretório não encontrado)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

app.include_router(upload.router,   prefix="/api/v1", tags=["Upload"])
app.include_router(process.router,  prefix="/api/v1", tags=["Processamento"])
app.include_router(export.router,   prefix="/api/v1", tags=["Exportação"])
app.include_router(projects.router, prefix="/api/v1", tags=["Projetos"])


@app.get("/", tags=["Status"])
async def root():
    return {"service": "Stamp3D API", "version": "1.0.0", "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Status"])
async def health_check():
    return {"status": "healthy"}
