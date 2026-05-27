"""
Rotas de Projetos - CRUD e status
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import os
import logging
import zipfile
import io

from core.database import get_db, Project, ProjectStatus
from services.pipeline import PipelineService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/projects")
async def list_projects(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Lista todos os projetos ordenados por data (mais recentes primeiro)"""
    result = await db.execute(
        select(Project)
        .order_by(desc(Project.created_at))
        .limit(limit)
        .offset(offset)
    )
    projects = result.scalars().all()
    
    return {
        "projects": [p.to_dict() for p in projects],
        "total": len(projects),
        "limit": limit,
        "offset": offset
    }


@router.get("/projects/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Retorna detalhes e status de um projeto"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, f"Projeto {project_id} não encontrado")
    
    data = project.to_dict()
    
    # Adicionar URLs de acesso aos arquivos
    base_url = "/storage"
    if project.original_image_path and os.path.exists(project.original_image_path):
        data["original_image_url"] = f"{base_url}/uploads/{os.path.basename(project.original_image_path)}"
    
    if project.processed_image_path and os.path.exists(project.processed_image_path):
        data["processed_image_url"] = f"{base_url}/temp/{os.path.basename(project.processed_image_path)}"
    
    if project.svg_path and os.path.exists(project.svg_path):
        data["svg_url"] = f"{base_url}/exports/{os.path.basename(project.svg_path)}"
    
    if project.stl_path and os.path.exists(project.stl_path):
        data["stl_url"] = f"{base_url}/exports/{os.path.basename(project.stl_path)}"
        data["stl_download_url"] = f"/api/v1/export/stl/{project_id}"
    
    return data


@router.post("/projects/{project_id}/reprocess")
async def reprocess_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Re-executa o pipeline para um projeto existente"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, f"Projeto {project_id} não encontrado")
    
    if not project.original_image_path or not os.path.exists(project.original_image_path):
        raise HTTPException(400, "Imagem original não encontrada")
    
    # Reset status
    project.status = ProjectStatus.PENDING
    project.progress = 0.0
    project.current_step = "Reprocessando..."
    project.error_message = None
    await db.commit()
    
    # Reiniciar pipeline
    async def run_task():
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as pipeline_db:
            service = PipelineService(pipeline_db)
            await service.run_full_pipeline(project_id)
    
    background_tasks.add_task(run_task)
    
    return {"success": True, "message": f"Reprocessamento iniciado para projeto #{project_id}"}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Remove projeto e seus arquivos"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, f"Projeto {project_id} não encontrado")
    
    # Remover arquivos
    for path_attr in ["original_image_path", "processed_image_path", "svg_path", "stl_path"]:
        path = getattr(project, path_attr, None)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"Não foi possível remover {path}: {e}")
    
    await db.delete(project)
    await db.commit()
    
    return {"success": True, "message": f"Projeto #{project_id} removido"}
