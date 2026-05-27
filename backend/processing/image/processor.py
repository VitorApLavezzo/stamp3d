"""
Pipeline de Processamento de Imagem para Carimbos 3D
Extrai apenas o desenho principal, sem sombras nem gradientes do fundo
"""

import cv2
import numpy as np
from PIL import Image
import logging
from pathlib import Path
from typing import Tuple, Optional
import asyncio

logger = logging.getLogger(__name__)


class ImageProcessor:
    def __init__(self, min_line_width_px: int = 6):
        self.min_line_width_px = min_line_width_px

    async def process(self, input_path: str, output_path: str, progress_callback=None) -> dict:
        def _sync():
            return self._process_sync(input_path, output_path, progress_callback)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync)

    def _process_sync(self, input_path: str, output_path: str, progress_callback=None) -> dict:
        def update(step: str, pct: float):
            if progress_callback:
                try:
                    progress_callback(step, pct)
                except Exception:
                    pass
            logger.info(f"  [{pct:.0f}%] {step}")

        update("Carregando imagem", 5)
        img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            pil = Image.open(input_path).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

        update("Upscale para qualidade", 12)
        img = self._upscale(img, 512)

        update("Extraindo desenho", 40)
        binary = self._extract(img)

        update("Limpando ruído", 72)
        binary = self._denoise(binary)

        update("Engrossando linhas", 82)
        binary = self._thicken(binary)

        update("Salvando", 95)
        cv2.imwrite(output_path, binary)
        update("Concluído", 100)

        metrics = self._metrics(binary)
        logger.info(f"✅ {metrics}")
        return {"output_path": output_path, "metrics": metrics}

    # ── Resize ────────────────────────────────────────────────────────────

    def _upscale(self, img, target):
        h, w = img.shape[:2]
        if max(h, w) >= target:
            # Redimensionar proporcionalmente para target
            scale = target / max(h, w)
            return cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
        scale = target / max(h, w)
        return cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LANCZOS4)

    # ── Extração ──────────────────────────────────────────────────────────

    def _extract(self, img: np.ndarray) -> np.ndarray:
        """
        Escolhe automaticamente a melhor estratégia de extração.
        Prioriza resultados com 5-35% de cobertura.
        """
        # Canal alpha (PNG transparente)
        if len(img.shape) == 3 and img.shape[2] == 4:
            r = self._from_alpha(img)
            cov = self._cov(r)
            if 0.03 < cov < 0.80:
                logger.info(f"  ✓ alpha: {cov*100:.1f}%")
                return r

        bgr = img[:,:,:3] if (len(img.shape)==3 and img.shape[2]==4) else img

        # Testar estratégias em ordem de preferência
        candidates = []
        for name, fn in [
            ("percentil",  lambda: self._extract_percentile(bgr)),
            ("hsv_escuro", lambda: self._extract_hsv_dark(bgr)),
            ("adaptativo", lambda: self._extract_adaptive(bgr)),
            ("otsu",       lambda: self._extract_otsu(bgr)),
        ]:
            try:
                result = fn()
                if result is None:
                    continue
                cov = self._cov(result)
                logger.info(f"  {name}: {cov*100:.1f}%")
                # Cobertura ideal para carimbo: 5% a 35%
                if 0.05 <= cov <= 0.35:
                    # Preferir coberturas próximas de 15-25%
                    score = 1.0 - abs(cov - 0.20)
                    candidates.append((score, name, result))
            except Exception as e:
                logger.warning(f"  {name} falhou: {e}")

        if candidates:
            candidates.sort(key=lambda x: -x[0])
            best = candidates[0]
            logger.info(f"  ✓ Escolhida: {best[1]} ({self._cov(best[2])*100:.1f}%)")
            return best[2]

        # Fallback: otsu simples
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return b

    def _extract_percentile(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Threshold em p75*0.75 do canal cinza.
        Ideal para renders 3D: captura apenas o núcleo escuro do objeto,
        excluindo gradientes/sombras do fundo.
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        p75 = float(np.percentile(gray, 75))
        threshold = p75 * 0.75

        obj = (gray < threshold).astype(np.uint8) * 255

        # Remover exterior (flood fill das bordas)
        flood = obj.copy()
        ff = np.zeros((h+2, w+2), np.uint8)
        for j in range(0, w, 8):
            for row in [0, h-1]:
                if flood[row, j] < 128:
                    cv2.floodFill(flood, ff, (j, row), 0)
        for i in range(0, h, 8):
            for col in [0, w-1]:
                if flood[i, col] < 128:
                    cv2.floodFill(flood, ff, (col, i), 0)

        # Fechar lacunas internas
        k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        flood = cv2.morphologyEx(flood, cv2.MORPH_CLOSE, k7, iterations=3)
        flood = cv2.morphologyEx(flood, cv2.MORPH_OPEN,  k3, iterations=1)

        # Manter apenas componentes com > 3% da maior área
        n, labels, stats, _ = cv2.connectedComponentsWithStats(flood)
        clean = np.zeros_like(flood)
        if n > 1:
            max_a = stats[1:, cv2.CC_STAT_AREA].max()
            for lbl in range(1, n):
                if stats[lbl, cv2.CC_STAT_AREA] >= max_a * 0.03:
                    clean[labels == lbl] = 255

        # objeto=preto, fundo=branco
        return np.where(clean > 0, 0, 255).astype(np.uint8)

    def _extract_hsv_dark(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        """Pixels mais escuros que o fundo (por brilho HSV)."""
        h, w = bgr.shape[:2]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:,:,2]; s = hsv[:,:,1]

        corners_v = [v[0,0], v[0,w//2], v[0,w-1],
                     v[h//2,0], v[h//2,w-1],
                     v[h-1,0], v[h-1,w//2], v[h-1,w-1]]
        bg_v = int(np.median(corners_v))
        if bg_v < 150:
            return None

        # Mais restritivo: bg_v - 50 em vez de bg_v - 30
        thr_v = bg_v - 50
        obj = ((v < thr_v) & (s > 40)).astype(np.uint8) * 255

        flood = obj.copy()
        ff = np.zeros((h+2, w+2), np.uint8)
        for j in range(0, w, 8):
            for row in [0, h-1]:
                if flood[row, j] < 128: cv2.floodFill(flood, ff, (j, row), 0)
        for i in range(0, h, 8):
            for col in [0, w-1]:
                if flood[i, col] < 128: cv2.floodFill(flood, ff, (col, i), 0)

        k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        flood = cv2.morphologyEx(flood, cv2.MORPH_CLOSE, k5, iterations=2)

        return np.where(flood > 0, 0, 255).astype(np.uint8)

    def _extract_adaptive(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        """Threshold adaptativo — bom para logos e ícones."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 10
        )

        flood = adaptive.copy()
        ff = np.zeros((h+2, w+2), np.uint8)
        for j in range(0, w, 10):
            if flood[0, j] == 255: cv2.floodFill(flood, ff, (j, 0), 0)
            if flood[h-1, j] == 255: cv2.floodFill(flood, ff, (j, h-1), 0)
        for i in range(0, h, 10):
            if flood[i, 0] == 255: cv2.floodFill(flood, ff, (0, i), 0)
            if flood[i, w-1] == 255: cv2.floodFill(flood, ff, (w-1, i), 0)

        return np.where(flood > 0, 0, 255).astype(np.uint8)

    def _extract_otsu(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return b

    def _from_alpha(self, img: np.ndarray) -> np.ndarray:
        alpha = img[:,:,3]
        bgr = img[:,:,:3]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        result = gray.copy()
        result[alpha < 128] = 255
        _, b = cv2.threshold(result, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return b

    # ── Pós-processamento ─────────────────────────────────────────────────

    def _thicken(self, binary: np.ndarray) -> np.ndarray:
        inv = cv2.bitwise_not(binary)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
            (self.min_line_width_px, self.min_line_width_px))
        return cv2.bitwise_not(cv2.dilate(inv, k, iterations=1))

    def _denoise(self, binary: np.ndarray) -> np.ndarray:
        inv = cv2.bitwise_not(binary)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
        if n <= 1:
            return binary
        areas = stats[1:, cv2.CC_STAT_AREA]
        if len(areas) == 0:
            return binary
        thr = max(areas.max() * 0.005, 20)
        clean = np.zeros_like(inv)
        for lbl in range(1, n):
            if stats[lbl, cv2.CC_STAT_AREA] >= thr:
                clean[labels == lbl] = 255
        return cv2.bitwise_not(clean)

    def _cov(self, binary: np.ndarray) -> float:
        if binary is None:
            return 0.0
        return float((binary == 0).mean())

    def _metrics(self, binary: np.ndarray) -> dict:
        total = binary.shape[0] * binary.shape[1]
        black = int(np.sum(binary == 0))
        contours, _ = cv2.findContours(cv2.bitwise_not(binary),
                                        cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return {
            "object_coverage_pct": round(black / total * 100, 2),
            "contour_count": len(contours),
        }


class ImageValidator:
    ALLOWED_FORMATS = {".png", ".jpg", ".jpeg", ".webp"}
    MAX_SIZE = 50 * 1024 * 1024

    @classmethod
    def validate(cls, file_path: str, file_size: int) -> Tuple[bool, str]:
        ext = Path(file_path).suffix.lower()
        if ext not in cls.ALLOWED_FORMATS:
            return False, f"Formato não suportado: {ext}. Use PNG, JPG ou WEBP."
        if file_size > cls.MAX_SIZE:
            return False, "Arquivo muito grande. Máximo: 50MB."
        try:
            img = Image.open(file_path)
            w, h = img.size
            if w < 100 or h < 100:
                return False, f"Imagem muito pequena: {w}x{h}px."
        except Exception as e:
            return False, f"Erro ao ler imagem: {str(e)}"
        return True, ""