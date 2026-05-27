"""
Banco de dados - Modelos e inicialização
SQLite para desenvolvimento / PostgreSQL para produção
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Text, Enum
from datetime import datetime
from typing import Optional
import enum

from core.config import settings

# Engine assíncrono
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VECTORIZING = "vectorizing"
    GENERATING_3D = "generating_3d"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base):
    """Modelo de projeto - cada carimbo processado"""
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    
    # Arquivos
    original_image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    processed_image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    svg_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stl_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Status do pipeline
    status: Mapped[str] = mapped_column(
        String(50), 
        default=ProjectStatus.PENDING
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[str] = mapped_column(String(100), default="Aguardando")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Parâmetros do carimbo
    stamp_diameter: Mapped[float] = mapped_column(Float, default=50.0)
    base_height: Mapped[float] = mapped_column(Float, default=4.0)
    relief_height: Mapped[float] = mapped_column(Float, default=6.0)
    scale_x: Mapped[float] = mapped_column(Float, default=0.1)
    scale_y: Mapped[float] = mapped_column(Float, default=0.1)
    scale_z: Mapped[float] = mapped_column(Float, default=0.2)
    location_z: Mapped[float] = mapped_column(Float, default=15.0)
    min_line_width: Mapped[float] = mapped_column(Float, default=1.2)
    
    # Metadados
    processing_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "current_step": self.current_step,
            "error_message": self.error_message,
            "original_image_path": self.original_image_path,
            "processed_image_path": self.processed_image_path,
            "svg_path": self.svg_path,
            "stl_path": self.stl_path,
            "stamp_diameter": self.stamp_diameter,
            "base_height": self.base_height,
            "relief_height": self.relief_height,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "scale_z": self.scale_z,
            "location_z": self.location_z,
            "min_line_width": self.min_line_width,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


async def init_db():
    """Inicializa o banco de dados criando as tabelas"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency para obter sessão do banco"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
