"""
Gerador 3D de Carimbos
Base cilíndrica + relevo binário limpo e sem falhas
"""

import os
import math
import logging
import asyncio
import struct
import numpy as np
from typing import List
import subprocess

logger = logging.getLogger(__name__)


class StampGenerator3D:
    def __init__(
        self,
        diameter_mm: float = 50.0,
        base_height_mm: float = 4.0,
        relief_height_mm: float = 6.0,
        scale_x: float = 0.1,
        scale_y: float = 0.1,
        scale_z: float = 0.2,
        location_z_mm: float = 15.0,
        min_wall_mm: float = 1.2
    ):
        self.diameter = diameter_mm
        self.radius = diameter_mm / 2
        self.base_height = base_height_mm
        self.relief_height = relief_height_mm
        self.min_wall = min_wall_mm

    async def generate(self, svg_path: str, output_stl_path: str, progress_callback=None) -> dict:
        def _sync():
            return self._generate_sync(svg_path, output_stl_path, progress_callback)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync)

    def _generate_sync(self, svg_path, output_path, progress_callback):
        def update(step, pct):
            if progress_callback:
                try:
                    progress_callback(step, pct)
                except Exception:
                    pass
            logger.info(f"  [{pct:.0f}%] {step}")

        update("Tentando OpenSCAD", 5)
        if self._try_openscad(svg_path, output_path, update):
            method = "openscad"
        else:
            update("Gerando STL manual", 10)
            self._generate_manual(svg_path, output_path, update)
            method = "manual"

        update("Concluído", 100)
        triangles = self._count_triangles(output_path)
        logger.info(f"✅ STL via {method}: {triangles} triângulos")
        return {
            "output_path": output_path,
            "method": method,
            "file_size_bytes": os.path.getsize(output_path),
            "triangle_count": triangles,
            "parameters": {
                "diameter_mm": self.diameter,
                "base_height_mm": self.base_height,
                "relief_height_mm": self.relief_height,
            }
        }

    # ── OpenSCAD ──────────────────────────────────────────────────────────

    def _try_openscad(self, svg_path, output_path, update):
        try:
            scad_path = output_path.replace(".stl", ".scad")
            abs_svg = os.path.abspath(svg_path).replace("\\", "/")
            svg_scale = (self.diameter * 0.85) / 1000.0
            scad = f"""$fn=128;
union() {{
    cylinder(h={self.base_height}, r={self.radius});
    translate([0,0,{self.base_height}])
    intersection() {{
        cylinder(h={self.relief_height}, r={self.radius * 0.95});
        translate([{-self.radius * 0.85},{-self.radius * 0.85},0])
        scale([{svg_scale:.6f},{svg_scale:.6f},1])
        linear_extrude(height={self.relief_height})
        import("{abs_svg}");
    }}
}}"""
            with open(scad_path, "w") as f:
                f.write(scad)
            result = subprocess.run(
                ["openscad", "-o", output_path, scad_path],
                capture_output=True, text=True, timeout=120
            )
            ok = result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000
            if ok:
                logger.info("  ✓ OpenSCAD OK")
            else:
                logger.warning(f"  OpenSCAD falhou: {result.stderr[:100]}")
            return ok
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.warning(f"  OpenSCAD: {e}")
            return False

    # ── Geração manual ────────────────────────────────────────────────────

    def _generate_manual(self, svg_path, output_path, update):
        update("Criando estrutura do carimbo", 20)
        tris = []

        # Dimensões do topo do carimbo
        r      = self.radius        # raio do topo (padrão 25mm)
        h_base = self.base_height   # 4mm
        h_rel  = self.relief_height # 6mm
        z_top  = h_base + h_rel     # 10mm

        # Fator de escala baseado no diâmetro configurado
        # Perfil do cabo extraído do STL de referência (diâmetro 21mm topo → 50mm altura)
        # Normalizado para diâmetro=1, altura total=1
        # Perfil: (z_norm, r_norm) — z e r normalizados para 0-1
        PROFILE_REF_D  = 21.0   # diâmetro de referência do cabo
        PROFILE_REF_H  = 40.0   # altura do cabo (sem o topo do carimbo)

        # Perfil ergonômico extraído do STL real
        # (z_frac 0=início cabo, 1=topo; r_frac relativo ao diâm. do cabo)
        profile = [
            (0.000, 0.384),  # base do cabo (fino)
            (0.037, 0.498),
            (0.074, 0.589),
            (0.110, 0.641),
            (0.147, 0.683),
            (0.184, 0.716),
            (0.221, 0.746),
            (0.257, 0.765),
            (0.294, 0.775),  # máximo do bojo inferior
            (0.330, 0.776),
            (0.368, 0.769),
            (0.404, 0.751),
            (0.441, 0.717),
            (0.478, 0.676),
            (0.515, 0.634),
            (0.551, 0.591),
            (0.588, 0.557),
            (0.625, 0.537),
            (0.662, 0.533),  # pescoço (mínimo)
            (0.699, 0.545),
            (0.735, 0.567),
            (0.772, 0.601),
            (0.809, 0.637),
            (0.846, 0.679),
            (0.882, 0.717),
            (0.919, 0.747),
            (0.956, 0.775),
            (0.993, 0.796),  # bojo superior
            (1.000, 1.000),  # cabeça (máximo — borda superior)
        ]

        # Escalar para o diâmetro configurado
        scale_r = (self.diameter / PROFILE_REF_D)
        h_cabo  = PROFILE_REF_H * scale_r

        logger.info(f"  Carimbo: topo_d={self.diameter:.0f}mm, cabo_h={h_cabo:.0f}mm, total={z_top+h_cabo:.0f}mm")

        # Estrutura correta (de baixo para cima):
        # Z=0            → base do cabo (topo da cabeça — o que você segura)
        # Z=h_cabo       → fim do cabo, início do topo do carimbo
        # Z=h_cabo+h_base → superfície de carimbar (onde fica o relevo)
        # Z=h_cabo+z_top → topo do relevo

        z_cabo_bot = 0.0
        z_cabo_top = h_cabo
        z_topo_bot = h_cabo
        z_topo_top = h_cabo + z_top
        z_rel_bot  = h_cabo + h_base
        z_rel_top  = h_cabo + z_top

        # 1. Cabo com perfil ergonômico (de baixo para cima)
        tris += self._make_profile_solid(profile, z_cabo_bot, h_cabo, scale_r, segments=64)

        # 2. Topo circular (base + área de relevo) em cima do cabo
        tris += self._make_cylinder(r, z_topo_bot, z_topo_top, segments=128)

        update("Carregando e limpando máscara", 40)
        mask = self._load_mask(svg_path)

        update("Extrudando relevo", 65)
        if mask is not None:
            # Ajustar z_base do relevo para ficar no topo correto
            self._relief_z_offset = z_rel_bot
            tris += self._extrude_mask(mask)
            logger.info("  ✓ Relevo extrudado")
        else:
            tris += self._make_cylinder(r * 0.7, z_rel_bot, z_rel_top, segments=64)
            logger.warning("  ⚠ Usando relevo placeholder")

        update("Escrevendo STL", 88)
        self._write_stl(tris, output_path)

    def _make_profile_solid(self, profile, z_offset, total_height, scale_r, segments=64) -> List:
        """
        Gera sólido de revolução a partir de perfil 2D.
        profile: lista de (z_frac, r_frac) normalizados 0-1
        Raio máximo de referência = 10.5mm * scale_r
        """
        R_REF = 10.5  # raio da cabeça de referência
        tris = []

        # Converter frações para mm
        points = []
        for z_frac, r_frac in profile:
            z_mm = z_offset + z_frac * total_height
            r_mm = r_frac * R_REF * scale_r
            points.append((z_mm, r_mm))

        angles = [2 * math.pi * i / segments for i in range(segments)]

        for seg_idx in range(len(points) - 1):
            z0, r0 = points[seg_idx]
            z1, r1 = points[seg_idx + 1]

            for i in range(segments):
                j = (i + 1) % segments
                a0, a1 = angles[i], angles[j]

                # 4 vértices do segmento
                p00 = (math.cos(a0)*r0, math.sin(a0)*r0, z0)
                p10 = (math.cos(a1)*r0, math.sin(a1)*r0, z0)
                p01 = (math.cos(a0)*r1, math.sin(a0)*r1, z1)
                p11 = (math.cos(a1)*r1, math.sin(a1)*r1, z1)

                # Parede lateral (2 triângulos)
                tris.append((p00, p10, p11))
                tris.append((p00, p11, p01))

            # Tampas nos extremos do perfil
            if seg_idx == 0:
                # Tampa inferior
                for i in range(segments):
                    j = (i + 1) % segments
                    tris.append(((0, 0, z0),
                                 (math.cos(angles[j])*r0, math.sin(angles[j])*r0, z0),
                                 (math.cos(angles[i])*r0, math.sin(angles[i])*r0, z0)))
            if seg_idx == len(points) - 2:
                # Tampa superior
                for i in range(segments):
                    j = (i + 1) % segments
                    tris.append(((0, 0, z1),
                                 (math.cos(angles[i])*r1, math.sin(angles[i])*r1, z1),
                                 (math.cos(angles[j])*r1, math.sin(angles[j])*r1, z1)))

        return tris

    # ── Cilindro ──────────────────────────────────────────────────────────

    def _make_cylinder(self, radius, z_bot, z_top, segments=64) -> List:
        tris = []
        a = [2 * math.pi * i / segments for i in range(segments)]
        cx = [math.cos(x) * radius for x in a]
        cy = [math.sin(x) * radius for x in a]
        for i in range(segments):
            j = (i + 1) % segments
            ax, ay = cx[i], cy[i]
            bx, by = cx[j], cy[j]
            tris.append(((0,0,z_top), (ax,ay,z_top), (bx,by,z_top)))
            tris.append(((0,0,z_bot), (bx,by,z_bot), (ax,ay,z_bot)))
            tris.append(((ax,ay,z_bot), (bx,by,z_bot), (bx,by,z_top)))
            tris.append(((ax,ay,z_bot), (bx,by,z_top), (ax,ay,z_top)))
        return tris

    # ── Máscara ───────────────────────────────────────────────────────────

    def _load_mask(self, svg_path: str):
        import cv2

        img = None

        # Tentar imagem processada
        basename = os.path.basename(svg_path)
        parts = basename.split("_")
        if len(parts) >= 2:
            pid = parts[1]
            temp_dir = os.path.dirname(svg_path).replace("exports", "temp")
            proc_path = os.path.join(temp_dir, f"project_{pid}_processed.png")
            if os.path.exists(proc_path):
                img = cv2.imread(proc_path, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    logger.info(f"  ✓ Máscara: {proc_path}")

        # Tentar cairosvg
        if img is None:
            try:
                import cairosvg
                png = cairosvg.svg2png(url=svg_path, output_width=512, output_height=512)
                arr = np.frombuffer(png, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    logger.info("  ✓ Máscara via cairosvg")
            except Exception:
                pass

        if img is None:
            return None

        return self._prepare_mask(img)

    def _prepare_mask(self, img: np.ndarray) -> np.ndarray:
        """
        Prepara máscara binária limpa para extrusão.
        Alta resolução + morfologia para fechar falhas.
        """
        import cv2

        # Alta resolução para bordas suaves: 300x300
        SIZE = 300

        # ── CASO 1: imagem RGBA (SVG rasterizado com canal alpha) ─────────
        # O SVG do ChatGPT tem objeto em alpha=255, fundo em alpha=0
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha_ch = img[:,:,3]
            alpha_resized = cv2.resize(alpha_ch, (SIZE, SIZE), interpolation=cv2.INTER_LANCZOS4)
            # Objeto = onde tem alpha (> 0) → branco para extrudar
            _, binary = cv2.threshold(alpha_resized, 127, 255, cv2.THRESH_BINARY)
            obj_pct = (binary == 255).mean() * 100
            import logging
            logging.getLogger(__name__).info(f"  Máscara via alpha: {obj_pct:.1f}% objeto")
            if 2 < obj_pct < 80:
                # Alpha válido — usar direto
                pass
            else:
                # Alpha inválido — cair no gray
                img = img[:,:,:3]

        # ── CASO 2: imagem grayscale ou RGB ───────────────────────────────
        if len(img.shape) == 2 or (len(img.shape) == 3 and img.shape[2] <= 3):
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            gray = cv2.resize(gray, (SIZE, SIZE), interpolation=cv2.INTER_LANCZOS4)

            _, binary_normal = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            _, binary_inv    = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            white_normal = (binary_normal == 255).mean()
            white_inv    = (binary_inv == 255).mean()

            # Escolher a versão onde objeto (branco) é minoria
            if white_inv < white_normal and white_inv < 0.55:
                binary = binary_inv
            elif white_normal < 0.55:
                binary = binary_normal
            else:
                binary = binary_inv

            import logging
            logging.getLogger(__name__).info(
                f"  Máscara gray: normal={white_normal*100:.1f}% inv={white_inv*100:.1f}%"
            )
        else:
            # Garantir que img é 300x300 para continuar
            if len(img.shape) == 3 and img.shape[2] == 4:
                img = cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_LANCZOS4)

        # ── Limpeza morfológica ──────────────────────────────────────────

        # 1. Fechar falhas pequenas nas linhas (conectar traços quebrados)
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k_close, iterations=2)

        # 2. Remover ruído pontual pequeno
        k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_open, iterations=1)

        # 3. Dilatar levemente para engrossar linhas finas
        #    (garante espessura mínima de impressão)
        min_px = max(2, int(self.min_wall / (self.diameter / SIZE)))
        k_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (min_px, min_px))
        binary = cv2.dilate(binary, k_dilate, iterations=1)

        # ── Máscara circular ─────────────────────────────────────────────
        cx, cy = SIZE // 2, SIZE // 2
        Y, X = np.ogrid[:SIZE, :SIZE]
        circle = (X - cx)**2 + (Y - cy)**2 <= (SIZE * 0.44)**2
        binary[~circle] = 0

        # ── Remover componentes pequenos (ruído residual) ─────────────────
        n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if n > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            threshold = max(areas.max() * 0.005, 10)
            clean = np.zeros_like(binary)
            for lbl in range(1, n):
                if stats[lbl, cv2.CC_STAT_AREA] >= threshold:
                    clean[labels == lbl] = 255
            binary = clean

        mask = binary > 0
        logger.info(f"  ✓ Máscara {SIZE}x{SIZE}, cobertura: {mask.mean()*100:.1f}%")
        return mask

    # ── Extrusão binária otimizada ────────────────────────────────────────

    def _extrude_mask(self, mask: np.ndarray) -> List:
        """
        Extrusão binária com bordas otimizadas.
        Só gera paredes nas bordas reais (transição ativo→inativo).
        Faces superiores e inferiores agrupadas por linhas para reduzir triângulos.
        """
        import cv2

        SIZE = mask.shape[0]
        tris = []

        # mm por pixel
        scale = (self.diameter * 0.88) / SIZE
        # Usar offset dinâmico se definido (cabo + topo), senão usar padrão
        z_offset = getattr(self, '_relief_z_offset', self.base_height)
        z_base = z_offset
        z_top  = z_offset + self.relief_height

        logger.info(f"  _extrude_mask: SIZE={SIZE} scale={scale:.3f}mm/px z_base={z_base:.1f} z_top={z_top:.1f} mask_cov={mask.mean()*100:.1f}%")

        # Pad para verificar vizinhos nas bordas
        padded = np.pad(mask.astype(np.uint8), 1, constant_values=0)

        def x0y0x1y1(r, c):
            """Coordenadas dos cantos da célula (r,c) em mm."""
            px0 = (c     - SIZE / 2) * scale
            px1 = (c + 1 - SIZE / 2) * scale
            py0 = (SIZE / 2 - r - 1) * scale
            py1 = (SIZE / 2 - r    ) * scale
            return px0, py0, px1, py1

        for r in range(SIZE):
            for c in range(SIZE):
                if not mask[r, c]:
                    continue

                x0, y0, x1, y1 = x0y0x1y1(r, c)

                # Face superior
                tris.append(((x0,y0,z_top),(x1,y0,z_top),(x1,y1,z_top)))
                tris.append(((x0,y0,z_top),(x1,y1,z_top),(x0,y1,z_top)))

                # Face inferior
                tris.append(((x0,y0,z_base),(x1,y1,z_base),(x1,y0,z_base)))
                tris.append(((x0,y0,z_base),(x0,y1,z_base),(x1,y1,z_base)))

                # Paredes — usar padded (r+1, c+1 no sistema padded)
                pr, pc = r + 1, c + 1

                # Esquerda
                if not padded[pr, pc-1]:
                    tris.append(((x0,y0,z_base),(x0,y1,z_base),(x0,y1,z_top)))
                    tris.append(((x0,y0,z_base),(x0,y1,z_top),(x0,y0,z_top)))
                # Direita
                if not padded[pr, pc+1]:
                    tris.append(((x1,y0,z_base),(x1,y1,z_top),(x1,y1,z_base)))
                    tris.append(((x1,y0,z_base),(x1,y0,z_top),(x1,y1,z_top)))
                # Cima
                if not padded[pr-1, pc]:
                    tris.append(((x0,y1,z_base),(x1,y1,z_top),(x1,y1,z_base)))
                    tris.append(((x0,y1,z_base),(x0,y1,z_top),(x1,y1,z_top)))
                # Baixo
                if not padded[pr+1, pc]:
                    tris.append(((x0,y0,z_base),(x1,y0,z_base),(x1,y0,z_top)))
                    tris.append(((x0,y0,z_base),(x1,y0,z_top),(x0,y0,z_top)))

        logger.info(f"  ✓ Extrusão: {len(tris)} triângulos")
        return tris

    # ── STL binário ───────────────────────────────────────────────────────

    def _write_stl(self, triangles: list, output_path: str):
        n = len(triangles)
        with open(output_path, "wb") as f:
            f.write(b"Stamp3D" + b" " * 73)
            f.write(struct.pack("<I", n))
            for tri in triangles:
                p1 = np.array(tri[0], dtype=np.float32)
                p2 = np.array(tri[1], dtype=np.float32)
                p3 = np.array(tri[2], dtype=np.float32)
                v1, v2 = p2 - p1, p3 - p1
                normal = np.cross(v1, v2)
                nlen = np.linalg.norm(normal)
                if nlen > 0:
                    normal /= nlen
                f.write(struct.pack("<3f", *normal))
                f.write(struct.pack("<3f", *p1))
                f.write(struct.pack("<3f", *p2))
                f.write(struct.pack("<3f", *p3))
                f.write(b"\x00\x00")

    def _count_triangles(self, stl_path: str) -> int:
        try:
            with open(stl_path, "rb") as f:
                f.read(80)
                return int.from_bytes(f.read(4), "little")
        except Exception:
            return 0