"""
Vision Service - Pipeline OpenCV melhorado
Gera SVG a partir da imagem processada
"""

import os, re, logging, asyncio, subprocess, cv2, numpy as np
from pathlib import Path
from typing import Optional
from PIL import Image as PILImage

logger = logging.getLogger(__name__)


class VisionSVGService:

    def __init__(self):
        pass  # Sem dependências externas

    async def image_to_svg(self, image_path, output_svg_path, progress_callback=None) -> dict:
        def update(step, pct):
            if progress_callback:
                try: progress_callback(step, pct)
                except: pass
            logger.info(f"  [{pct:.0f}%] {step}")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(image_path, output_svg_path, update))

    def _run(self, image_path, output_svg_path, update) -> dict:
        update("Carregando imagem", 5)

        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            pil = PILImage.open(image_path).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

        # Redimensionar para 512
        h, w = img.shape[:2]
        scale = 512 / max(h, w)
        img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LANCZOS4)
        h, w = img.shape[:2]

        update("Extraindo desenho", 20)
        binary = self._extract(img, h, w)

        # Verificar se extraiu algo útil
        cov = (binary == 0).mean()
        logger.info(f"  Cobertura extraída: {cov*100:.1f}%")

        if cov < 0.02:
            logger.warning("  Cobertura muito baixa — usando threshold simples")
            gray = cv2.cvtColor(img[:,:,:3] if img.shape[2]==4 else img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # Garantir que objeto é preto
            if (binary == 0).mean() > 0.5:
                binary = cv2.bitwise_not(binary)

        update("Vetorizando", 55)
        bmp_path = image_path + "_tmp.bmp"
        cv2.imwrite(bmp_path, binary)
        svg_content = self._to_svg(bmp_path, binary, w, h)
        if os.path.exists(bmp_path):
            os.remove(bmp_path)

        # Verificar se SVG tem paths
        path_count = svg_content.count('<path')
        logger.info(f"  SVG gerado: {path_count} paths, {len(svg_content)//1024}KB")

        if path_count == 0:
            logger.warning("  SVG sem paths — gerando fallback com contornos")
            svg_content = self._opencv_svg(binary, w, h)

        update("Salvando", 90)
        os.makedirs(os.path.dirname(output_svg_path), exist_ok=True)
        with open(output_svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        update("Concluído", 100)
        logger.info(f"  ✓ SVG salvo: {output_svg_path} ({path_count} paths)")

        return {
            "output_path": output_svg_path,
            "method": "opencv_enhanced",
            "stats": {"path_count": path_count, "file_size_kb": round(len(svg_content)/1024, 2)},
            "validation": {"is_valid": path_count > 0, "issues": [] if path_count > 0 else ["SVG vazio"]}
        }

    def _extract(self, img, h, w) -> np.ndarray:
        """Pipeline melhorado: enhanced Canny + percentile + melhor seleção."""

        bgr = img[:,:,:3] if (len(img.shape)==3 and img.shape[2]==4) else img

        # Canal alpha (PNG transparente)
        if len(img.shape)==3 and img.shape[2]==4:
            alpha = img[:,:,3]
            if np.mean(alpha) < 250:
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                r = np.full_like(gray, 255)
                r[alpha > 128] = gray[alpha > 128]
                _, b = cv2.threshold(r, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
                cov = (b==0).mean()
                if 0.04 < cov < 0.80:
                    logger.info(f"  alpha: {cov*100:.1f}%")
                    return b

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Pré-processamento: unsharp + CLAHE
        blur9 = cv2.GaussianBlur(gray, (9,9), 0)
        unsharp = np.clip(cv2.addWeighted(gray, 2.5, blur9, -1.5, 0), 0, 255).astype(np.uint8)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4,4))
        enhanced = cv2.addWeighted(unsharp, 0.5, clahe.apply(gray), 0.5, 0)

        candidates = []

        # Canny no enhanced
        for lo, hi, close in [(40,120,5),(50,150,5),(40,150,6),(35,100,5)]:
            r = self._canny_fill(enhanced, h, w, lo, hi, close)
            if r is not None:
                cov = (r==0).mean()
                if 0.05 <= cov <= 0.45:
                    candidates.append((abs(cov-0.18), f"enhanced({lo},{hi},{close})", r))

        # Canny no gray
        for lo, hi, close in [(40,150,5),(50,150,5),(40,120,5)]:
            r = self._canny_fill(gray, h, w, lo, hi, close)
            if r is not None:
                cov = (r==0).mean()
                if 0.05 <= cov <= 0.45:
                    candidates.append((abs(cov-0.18)*1.1, f"gray({lo},{hi},{close})", r))

        # Percentile
        p75 = float(np.percentile(gray, 75))
        obj = (gray < p75*0.75).astype(np.uint8)*255
        flood = obj.copy(); ff = np.zeros((h+2,w+2),np.uint8)
        for j in range(0,w,8):
            for row in [0,h-1]:
                if flood[row,j]<128: cv2.floodFill(flood,ff,(j,row),0)
        for i in range(0,h,8):
            for col in [0,w-1]:
                if flood[i,col]<128: cv2.floodFill(flood,ff,(col,i),0)
        k7=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7))
        flood=cv2.morphologyEx(flood,cv2.MORPH_CLOSE,k7,iterations=3)
        n,labels,stats,centroids=cv2.connectedComponentsWithStats(flood)
        clean=np.zeros((h,w),np.uint8)
        if n>1:
            max_a=stats[1:,cv2.CC_STAT_AREA].max()
            for lbl in range(1,n):
                cx,cy=centroids[lbl]
                dist=np.sqrt((cx-w//2)**2+(cy-h//2)**2)
                if stats[lbl,cv2.CC_STAT_AREA]>=max_a*0.03 and dist<=min(w,h)*0.46:
                    clean[labels==lbl]=255
        r_perc = np.where(clean>0,0,255).astype(np.uint8)
        cov_perc = (r_perc==0).mean()
        if 0.05 <= cov_perc <= 0.45:
            candidates.append((abs(cov_perc-0.18)*1.2, "percentile", r_perc))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            name, result = candidates[0][1], candidates[0][2]
            cov = (result==0).mean()
            logger.info(f"  ✓ {name}: {cov*100:.1f}%")
            # Pós-processamento
            inv = cv2.bitwise_not(result)
            n2,labels2,stats2,_=cv2.connectedComponentsWithStats(inv,connectivity=8)
            if n2>1:
                areas=stats2[1:,cv2.CC_STAT_AREA]
                thr=max(areas.max()*0.005,20)
                clean2=np.zeros_like(inv)
                for lbl in range(1,n2):
                    if stats2[lbl,cv2.CC_STAT_AREA]>=thr:
                        clean2[labels2==lbl]=255
                result=cv2.bitwise_not(clean2)
            # Engrossar linhas finas
            inv2=cv2.bitwise_not(result)
            k5=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
            result=cv2.bitwise_not(cv2.dilate(inv2,k5,iterations=1))
            return result

        logger.warning("  Nenhum candidato bom — usando Otsu simples")
        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        if (b==0).mean() > 0.5:
            b = cv2.bitwise_not(b)
        return b

    def _canny_fill(self, gray, h, w, lo, hi, close):
        try:
            edges = cv2.Canny(cv2.GaussianBlur(gray,(3,3),0), lo, hi)
            k2=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2,2))
            k5=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
            e=cv2.dilate(edges,k2,iterations=2)
            e=cv2.morphologyEx(e,cv2.MORPH_CLOSE,k5,iterations=close)
            inv=cv2.bitwise_not(e); fl=inv.copy(); ff=np.zeros((h+2,w+2),np.uint8)
            cv2.floodFill(fl,ff,(0,0),0)
            interior=np.where(fl==255,0,255).astype(np.uint8)
            n,labels,stats,centroids=cv2.connectedComponentsWithStats(cv2.bitwise_not(interior))
            clean=np.zeros((h,w),np.uint8)
            if n>1:
                max_a=stats[1:,cv2.CC_STAT_AREA].max()
                for lbl in range(1,n):
                    cx,cy=centroids[lbl]
                    dist=np.sqrt((cx-w//2)**2+(cy-h//2)**2)
                    if stats[lbl,cv2.CC_STAT_AREA]>=max_a*0.03 and dist<=min(w,h)*0.46:
                        clean[labels==lbl]=255
            return np.where(clean>0,0,255).astype(np.uint8)
        except Exception as e:
            logger.warning(f"  canny_fill({lo},{hi},{close}) erro: {e}")
            return None

    def _to_svg(self, bmp_path, binary, w, h) -> str:
        svg_path = bmp_path.replace(".bmp", ".svg")
        try:
            r = subprocess.run(
                ["potrace","--svg","--alphamax=1.0","--opttolerance=0.2",
                 "--turdsize=5","--longcurve","--output", svg_path, bmp_path],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode==0 and os.path.exists(svg_path):
                with open(svg_path) as f: content = f.read()
                os.remove(svg_path)
                if 'xmlns=' not in content:
                    content = content.replace('<svg','<svg xmlns="http://www.w3.org/2000/svg"',1)
                if content.count('<path') > 0:
                    logger.info("  ✓ potrace OK")
                    return content
                else:
                    logger.warning("  potrace gerou SVG sem paths")
        except Exception as e:
            logger.warning(f"  potrace: {e}")

        return self._opencv_svg(binary, w, h)

    def _opencv_svg(self, binary, w, h) -> str:
        """Fallback: contornos OpenCV."""
        contours, _ = cv2.findContours(cv2.bitwise_not(binary), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
        paths = []
        for c in contours:
            if cv2.contourArea(c) < 30: continue
            eps = 0.003 * cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, eps, True)
            if len(approx) < 3: continue
            pts = approx.reshape(-1,2)
            d = f"M {pts[0][0]},{pts[0][1]} " + " ".join(f"L {p[0]},{p[1]}" for p in pts[1:]) + " Z"
            paths.append(f'  <path d="{d}"/>')
        logger.info(f"  opencv_svg: {len(paths)} paths")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
                f'  <g fill="black" fill-rule="evenodd">\n'
                + "\n".join(paths) +
                f'\n  </g>\n</svg>')