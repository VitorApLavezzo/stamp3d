"""
Rotas de Exportação
Download de STL, SVG, ZIP
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import zipfile
import io
import logging

from core.database import get_db, Project, ProjectStatus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/export/stl/{project_id}")
async def download_stl(project_id: int, db: AsyncSession = Depends(get_db)):
    """Download do arquivo STL gerado"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    
    if project.status != ProjectStatus.COMPLETED:
        raise HTTPException(400, f"Projeto não concluído. Status: {project.status}")
    
    if not project.stl_path or not os.path.exists(project.stl_path):
        raise HTTPException(404, "Arquivo STL não encontrado")
    
    filename = f"{project.name.replace(' ', '_')}.stl"
    
    return FileResponse(
        path=project.stl_path,
        media_type="application/octet-stream",
        filename=filename
    )


@router.get("/export/svg/{project_id}")
async def download_svg(project_id: int, db: AsyncSession = Depends(get_db)):
    """Download do arquivo SVG processado"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    
    if not project.svg_path or not os.path.exists(project.svg_path):
        raise HTTPException(404, "Arquivo SVG não encontrado")
    
    filename = f"design_{project.name.replace(' ', '_')}_{project_id}.svg"
    
    return FileResponse(
        path=project.svg_path,
        media_type="image/svg+xml",
        filename=filename
    )


@router.get("/export/zip/{project_id}")
async def download_zip(project_id: int, db: AsyncSession = Depends(get_db)):
    """Download de todos os arquivos do projeto em ZIP"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    
    # Criar ZIP em memória
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        files_added = 0
        
        # Adicionar STL
        if project.stl_path and os.path.exists(project.stl_path):
            zf.write(project.stl_path, f"stamp_{project_id}.stl")
            files_added += 1
        
        # Adicionar SVG
        if project.svg_path and os.path.exists(project.svg_path):
            zf.write(project.svg_path, f"design_{project_id}.svg")
            files_added += 1
        
        # Adicionar imagem processada
        if project.processed_image_path and os.path.exists(project.processed_image_path):
            zf.write(project.processed_image_path, f"processed_{project_id}.png")
            files_added += 1
        
        # Adicionar README do projeto
        readme_content = f"""# Projeto: {project.name}
        
## Parâmetros do Carimbo
- Diâmetro: {project.stamp_diameter}mm
- Altura da base: {project.base_height}mm  
- Altura do relevo: {project.relief_height}mm
- Escala X: {project.scale_x}
- Escala Y: {project.scale_y}
- Escala Z: {project.scale_z}
- Location Z: {project.location_z}mm

## Arquivos
- stamp_{project_id}.stl — Modelo 3D para impressão (imprimir com PETG/ABS alimentício)
- design_{project_id}.svg — Desenho vetorial
- processed_{project_id}.png — Imagem processada

## Configurações de Impressão Recomendadas
- Material: PETG alimentício ou PLA
- Layer Height: 0.2mm
- Infill: 20%
- Perimeters: 3
- Supports: Não necessário

## Gerado por Stamp3D
"""
        zf.writestr("README.txt", readme_content)
    
    if files_added == 0:
        raise HTTPException(404, "Nenhum arquivo disponível para download")
    
    zip_buffer.seek(0)
    filename = f"stamp3d_{project.name.replace(' ', '_')}_{project_id}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
