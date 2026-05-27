"""
Orquestrador do Pipeline
Prioridade: Gemini Vision → OpenAI Vision → Anthropic Vision → OpenCV
"""

import os
import logging
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from core.database import Project, ProjectStatus, AsyncSessionLocal
from processing.image.processor import ImageProcessor
from processing.vector.vectorizer import SVGVectorizer
from processing.cad.generator import StampGenerator3D

logger = logging.getLogger(__name__)


async def _update_project_isolated(project_id: int, updates: dict):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if project:
                for key, value in updates.items():
                    setattr(project, key, value)
                project.updated_at = datetime.utcnow()
                await db.commit()
        except Exception as e:
            logger.error(f"Erro ao atualizar #{project_id}: {e}")
            await db.rollback()


def _detect_vision_provider() -> tuple[bool, str]:
    """
    Detecta qual provider de vision está disponível.
    Prioridade: Gemini (grátis) → OpenAI → Anthropic → None
    """
    def valid(key: str) -> bool:
        return bool(key and len(key) > 20 and "sua-chave" not in key)

    gemini = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if valid(gemini):
        return True, "gemini"

    openai = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")
    if valid(openai):
        return True, "openai"

    anthropic = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if valid(anthropic):
        return True, "anthropic"

    return False, "none"


class PipelineService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.vision_available, self.vision_provider = _detect_vision_provider()

        labels = {"gemini": "Gemini Vision (grátis)", "openai": "GPT-4 Vision",
                  "anthropic": "Claude Vision", "none": "OpenCV (fallback)"}
        logger.info(f"🔍 Vision: {labels.get(self.vision_provider, self.vision_provider)}")

        self.image_processor = ImageProcessor(min_line_width_px=8)
        self.vectorizer = SVGVectorizer(
            alphamax=1.0, opttolerance=0.2,
            turdsize=5, target_size_mm=settings.STAMP_DIAMETER
        )

    async def run_full_pipeline(self, project_id: int) -> dict:
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Projeto {project_id} não encontrado")

        log_entries = []
        loop = asyncio.get_event_loop()

        def log(msg):
            log_entries.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
            logger.info(f"  Pipeline #{project_id}: {msg}")

        def make_cb(label, r0, r1):
            def cb(step, pct):
                total = r0 + pct * (r1 - r0) / 100.0
                log(f"  [{label}] {step} ({pct:.0f}%)")
                asyncio.run_coroutine_threadsafe(
                    _update_project_isolated(project_id, {
                        "current_step": f"{label}: {step}",
                        "progress": round(total, 1),
                    }), loop
                )
            return cb

        try:
            await _update_project_isolated(project_id, {
                "status": ProjectStatus.PROCESSING,
                "progress": 0.0, "current_step": "Iniciando",
            })
            log("Pipeline iniciado")

            svg_path = self._get_svg_path(project_id)
            processed_path = self._get_processed_path(project_id)

            # ── ROTA A: Vision API ────────────────────────────────────────
            if self.vision_available:
                labels = {"gemini": "Gemini Vision", "openai": "GPT-4 Vision",
                          "anthropic": "Claude Vision"}
                lbl = labels[self.vision_provider]
                log(f"=== {lbl} ===")

                await _update_project_isolated(project_id, {
                    "status": ProjectStatus.VECTORIZING,
                    "current_step": f"{lbl}: analisando imagem",
                    "progress": 5.0,
                })

                svg_result = await self._run_vision(
                    project.original_image_path, svg_path,
                    make_cb(lbl, 5, 55)
                )

                import shutil
                shutil.copy2(project.original_image_path, processed_path)

                await _update_project_isolated(project_id, {
                    "processed_image_path": processed_path,
                    "svg_path": svg_path,
                    "progress": 55.0,
                    "current_step": f"SVG gerado via {lbl}",
                })
                log(f"SVG: {svg_result['stats']}")

            # ── ROTA B: OpenCV fallback ───────────────────────────────────
            else:
                log("=== Pipeline OpenCV ===")
                await _update_project_isolated(project_id, {
                    "current_step": "Processando imagem", "progress": 2.0,
                })
                img_result = await self.image_processor.process(
                    project.original_image_path, processed_path,
                    progress_callback=make_cb("Imagem", 2, 25)
                )
                await _update_project_isolated(project_id, {
                    "processed_image_path": processed_path,
                    "progress": 25.0, "current_step": "Imagem processada",
                })
                log(f"Imagem: {img_result['metrics']}")

                await _update_project_isolated(project_id, {
                    "status": ProjectStatus.VECTORIZING,
                    "current_step": "Vetorizando SVG", "progress": 25.0,
                })
                svg_result = await self.vectorizer.vectorize(
                    processed_path, svg_path,
                    progress_callback=make_cb("SVG", 25, 55)
                )
                await _update_project_isolated(project_id, {
                    "svg_path": svg_path,
                    "progress": 55.0, "current_step": "SVG gerado",
                })
                log(f"SVG: {svg_result['stats']}")

            # ── GERAÇÃO 3D ────────────────────────────────────────────────
            log("=== Gerando modelo 3D ===")
            await _update_project_isolated(project_id, {
                "status": ProjectStatus.GENERATING_3D,
                "current_step": "Gerando modelo 3D", "progress": 55.0,
            })

            stl_path = self._get_stl_path(project_id)
            generator = StampGenerator3D(
                diameter_mm=project.stamp_diameter,
                base_height_mm=project.base_height,
                relief_height_mm=project.relief_height,
                scale_x=project.scale_x, scale_y=project.scale_y,
                scale_z=project.scale_z, location_z_mm=project.location_z,
                min_wall_mm=project.min_line_width
            )
            gen_result = await generator.generate(
                svg_path, stl_path,
                progress_callback=make_cb("3D", 55, 95)
            )
            log(f"STL: {gen_result['triangle_count']} triângulos ({gen_result['method']})")

            await _update_project_isolated(project_id, {
                "stl_path": stl_path,
                "status": ProjectStatus.COMPLETED,
                "progress": 100.0,
                "current_step": "Concluído ✅",
                "processing_log": "\n".join(log_entries),
            })
            log("Concluído!")
            return {"success": True, "project_id": project_id,
                    "stl_path": stl_path, "svg_path": svg_path}

        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            logger.error(error_msg, exc_info=True)
            log(f"❌ {error_msg}")
            await _update_project_isolated(project_id, {
                "status": ProjectStatus.FAILED,
                "error_message": error_msg,
                "current_step": "Falhou ❌",
                "processing_log": "\n".join(log_entries),
            })
            raise

    async def _run_vision(self, image_path, svg_path, cb):
        from services.vision_service import VisionSVGService
        svc = VisionSVGService()
        return await svc.image_to_svg(image_path, svg_path, cb)

    def _get_processed_path(self, pid):
        p = os.path.join(settings.TEMP_DIR, f"project_{pid}_processed.png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _get_svg_path(self, pid):
        p = os.path.join(settings.EXPORT_DIR, f"project_{pid}_design.svg")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _get_stl_path(self, pid):
        p = os.path.join(settings.EXPORT_DIR, f"project_{pid}_stamp.stl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    async def _get_project(self, pid):
        r = await self.db.execute(select(Project).where(Project.id == pid))
        return r.scalar_one_or_none()