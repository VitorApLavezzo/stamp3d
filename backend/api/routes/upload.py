"""
Rotas de Upload
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import os, uuid, shutil, logging
from typing import Optional

from core.config import settings
from core.database import get_db, Project, ProjectStatus
from processing.image.processor import ImageValidator
from services.pipeline import PipelineService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_name: Optional[str] = Form(None),
    stamp_diameter: float = Form(default=50.0),
    base_height: float = Form(default=4.0),
    relief_height: float = Form(default=6.0),
    min_line_width: float = Form(default=1.2),
    auto_process: bool = Form(default=True),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"📤 Upload: {file.filename}")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, f"Formato não suportado: {ext}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(413, "Arquivo muito grande. Máximo: 50MB.")
    if len(content) == 0:
        raise HTTPException(400, "Arquivo vazio")

    unique_id = uuid.uuid4().hex[:8]
    safe_name = f"{unique_id}_{Path(file.filename).stem}{ext}"
    upload_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    with open(upload_path, "wb") as f:
        f.write(content)

    is_valid, error_msg = ImageValidator.validate(upload_path, len(content))
    if not is_valid:
        os.remove(upload_path)
        raise HTTPException(400, error_msg)

    name = project_name or f"Carimbo {Path(file.filename).stem}"
    project = Project(
        name=name,
        original_image_path=upload_path,
        status=ProjectStatus.PENDING,
        progress=0.0,
        current_step="Upload concluído",
        stamp_diameter=stamp_diameter,
        base_height=base_height,
        relief_height=relief_height,
        scale_x=settings.STAMP_SCALE_X,
        scale_y=settings.STAMP_SCALE_Y,
        scale_z=settings.STAMP_SCALE_Z,
        location_z=settings.STAMP_LOCATION_Z,
        min_line_width=min_line_width
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    if auto_process:
        project_id = project.id

        async def run_pipeline():
            from core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as pipeline_db:
                svc = PipelineService(pipeline_db)
                try:
                    await svc.run_full_pipeline(project_id)
                except Exception as e:
                    logger.error(f"Pipeline #{project_id} falhou: {e}")

        background_tasks.add_task(run_pipeline)

    return {"success": True, "project": project.to_dict()}


@router.post("/upload-svg/{project_id}")
async def upload_svg(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Recebe SVG externo (gerado pelo ChatGPT) e pula direto para geração 3D.
    """
    if not file.filename.endswith('.svg'):
        raise HTTPException(400, "Arquivo deve ser .svg")

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, f"Projeto {project_id} não encontrado")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "SVG vazio")

    # Salvar SVG
    svg_path = os.path.join(settings.EXPORT_DIR, f"project_{project_id}_design.svg")
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    with open(svg_path, "wb") as f:
        f.write(content)

    # Atualizar projeto
    project.svg_path = svg_path
    project.status = ProjectStatus.GENERATING_3D
    project.progress = 50.0
    project.current_step = "SVG recebido — gerando 3D"
    await db.commit()

    logger.info(f"📐 SVG recebido para projeto #{project_id}: {svg_path}")

    # Iniciar apenas a geração 3D
    async def run_3d_only():
        from core.database import AsyncSessionLocal
        from processing.cad.generator import StampGenerator3D
        from services.pipeline import _update_project_isolated
        from core.database import ProjectStatus

        async with AsyncSessionLocal() as pipeline_db:
            r = await pipeline_db.execute(select(Project).where(Project.id == project_id))
            p = r.scalar_one_or_none()
            if not p:
                return

            stl_path = os.path.join(settings.EXPORT_DIR, f"project_{project_id}_stamp.stl")

            def cb(step, pct):
                total = 50.0 + pct * 0.45
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    _update_project_isolated(project_id, {
                        "current_step": f"3D: {step}",
                        "progress": round(total, 1),
                    }),
                    asyncio.get_event_loop()
                )

            try:
                gen = StampGenerator3D(
                    diameter_mm=p.stamp_diameter,
                    base_height_mm=p.base_height,
                    relief_height_mm=p.relief_height,
                    scale_x=p.scale_x, scale_y=p.scale_y,
                    scale_z=p.scale_z, location_z_mm=p.location_z,
                    min_wall_mm=p.min_line_width
                )
                result = await gen.generate(svg_path, stl_path)

                await _update_project_isolated(project_id, {
                    "stl_path": stl_path,
                    "status": ProjectStatus.COMPLETED,
                    "progress": 100.0,
                    "current_step": "Concluído ✅",
                })
                logger.info(f"✅ 3D gerado para projeto #{project_id}")
            except Exception as e:
                await _update_project_isolated(project_id, {
                    "status": ProjectStatus.FAILED,
                    "error_message": str(e),
                    "current_step": "Falhou ❌",
                })
                logger.error(f"3D falhou para #{project_id}: {e}")

    background_tasks.add_task(run_3d_only)

    return {
        "success": True,
        "message": "SVG recebido. Gerando modelo 3D...",
        "project_id": project_id
    }