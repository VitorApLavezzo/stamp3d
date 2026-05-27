"""
Rotas de Processamento e Projetos
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import os
import logging
import zipfile
import tempfile

from core.database import get_db, Project, ProjectStatus
from services.pipeline import PipelineService

router = APIRouter()
logger = logging.getLogger(__name__)
