"""
Vetorizador SVG
Converte imagens binárias processadas em SVGs otimizados para extrusão 3D.

Usa potrace para vetorização de alta qualidade.
Fallback para contornos OpenCV se potrace não disponível.
"""

import cv2
import numpy as np
import subprocess
import os
import re
import logging
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class SVGVectorizer:
    """
    Vetoriza imagens binárias para SVG usando potrace.
    
    Parâmetros otimizados para:
    - Carimbos 3D alimentícios
    - Impressão FDM
    - Poucos pontos de controle (curvas suaves)
    - Caminhos fechados
    """
    
    def __init__(
        self,
        alphamax: float = 1.0,      # Suavidade das curvas (0-4/3)
        opttolerance: float = 0.2,  # Tolerância de otimização
        turdsize: int = 5,          # Remover componentes < N px
        target_size_mm: float = 50.0  # Tamanho alvo em mm
    ):
        self.alphamax = alphamax
        self.opttolerance = opttolerance
        self.turdsize = turdsize
        self.target_size_mm = target_size_mm
    
    async def vectorize(
        self,
        binary_image_path: str,
        output_svg_path: str,
        progress_callback=None
    ) -> dict:
        """Vetoriza imagem para SVG de forma assíncrona"""
        
        def _sync_vectorize():
            return self._vectorize_sync(binary_image_path, output_svg_path, progress_callback)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_vectorize)
    
    def _vectorize_sync(
        self, 
        binary_image_path: str, 
        output_svg_path: str,
        progress_callback=None
    ) -> dict:
        """Vetorização síncrona"""
        
        def update(step, pct):
            if progress_callback:
                progress_callback(step, pct)
            logger.info(f"  [{pct:.0f}%] {step}")
        
        update("Preparando para vetorização", 5)
        
        # Converter para BMP (formato nativo do potrace)
        bmp_path = binary_image_path.replace(Path(binary_image_path).suffix, ".bmp")
        img = cv2.imread(binary_image_path, cv2.IMREAD_GRAYSCALE)
        
        if img is None:
            raise ValueError(f"Não foi possível carregar imagem: {binary_image_path}")
        
        # Inverter: potrace espera preto=objeto
        img_for_potrace = cv2.bitwise_not(img)
        cv2.imwrite(bmp_path, img_for_potrace)
        
        update("Vetorizando com potrace", 30)
        
        # Tentar potrace
        svg_content = self._run_potrace(bmp_path, output_svg_path)
        
        if svg_content is None:
            update("Fallback: vetorizando com OpenCV", 30)
            svg_content = self._vectorize_opencv_fallback(img, output_svg_path)
        
        # Limpar BMP temporário
        if os.path.exists(bmp_path):
            os.remove(bmp_path)
        
        update("Otimizando caminhos SVG", 60)
        svg_content = self._optimize_svg(svg_content, img.shape)
        
        update("Validando para impressão 3D", 80)
        validation = self._validate_for_3d_printing(svg_content)
        
        update("Salvando SVG", 90)
        with open(output_svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        
        update("Vetorização concluída", 100)
        
        stats = self._get_svg_stats(svg_content)
        logger.info(f"✅ SVG gerado: {output_svg_path}")
        logger.info(f"  Paths: {stats['path_count']}, Pontos: {stats['point_count']}")
        
        return {
            "output_path": output_svg_path,
            "stats": stats,
            "validation": validation
        }
    
    def _run_potrace(self, bmp_path: str, output_svg_path: str) -> Optional[str]:
        """Executa potrace para vetorização de alta qualidade"""
        try:
            result = subprocess.run(
                [
                    "potrace",
                    "--svg",
                    f"--alphamax={self.alphamax}",
                    f"--opttolerance={self.opttolerance}",
                    f"--turdsize={self.turdsize}",
                    "--longcurve",       # Curvas mais longas (menos pontos)
                    "--output", output_svg_path,
                    bmp_path
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and os.path.exists(output_svg_path):
                with open(output_svg_path, "r") as f:
                    content = f.read()
                logger.info("  ✓ potrace bem-sucedido")
                return content
            else:
                logger.warning(f"  ⚠️ potrace falhou: {result.stderr}")
                return None
                
        except FileNotFoundError:
            logger.warning("  ⚠️ potrace não encontrado, usando fallback")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("  ⚠️ potrace timeout")
            return None
    
    def _vectorize_opencv_fallback(self, binary_img: np.ndarray, output_svg_path: str) -> str:
        """
        Vetorização via contornos OpenCV.
        Fallback quando potrace não disponível.
        """
        logger.info("  Usando vetorização OpenCV (fallback)")
        
        h, w = binary_img.shape
        
        # Detectar contornos com hierarquia completa
        contours, hierarchy = cv2.findContours(
            cv2.bitwise_not(binary_img),
            cv2.RETR_CCOMP,  # Contornos e buracos
            cv2.CHAIN_APPROX_TC89_KCOS  # Aproximação suave
        )
        
        if not contours:
            logger.warning("  Nenhum contorno encontrado")
            return self._empty_svg(w, h)
        
        # Construir SVG
        paths = []
        
        for i, contour in enumerate(contours):
            # Simplificar contorno (menos pontos)
            epsilon = 0.005 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) < 3:
                continue
            
            # Converter pontos para path SVG
            path_d = self._contour_to_svg_path(approx, h)
            if path_d:
                paths.append(f'  <path d="{path_d}" />')
        
        # SVG final
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{w}" height="{h}"
     viewBox="0 0 {w} {h}">
  <g id="stamp-design" fill="black" fill-rule="evenodd" stroke="none">
{chr(10).join(paths)}
  </g>
</svg>'''
        
        return svg
    
    def _contour_to_svg_path(self, contour: np.ndarray, height: int) -> str:
        """Converte contorno OpenCV para string de path SVG"""
        if len(contour) < 2:
            return ""
        
        points = contour.reshape(-1, 2)
        
        # Inverter Y (SVG tem Y invertido em relação a OpenCV)
        # Não inverter aqui - será tratado no SVG
        
        d_parts = []
        
        # Ponto inicial
        x, y = points[0]
        d_parts.append(f"M {x:.2f},{y:.2f}")
        
        # Curvas cúbicas de Bézier através dos pontos
        if len(points) >= 4:
            i = 1
            while i < len(points) - 2:
                p1 = points[i]
                p2 = points[i + 1]
                p3 = points[i + 2] if i + 2 < len(points) else points[-1]
                
                # Pontos de controle
                cp1x = p1[0] + (p2[0] - points[i-1][0]) / 6
                cp1y = p1[1] + (p2[1] - points[i-1][1]) / 6
                cp2x = p2[0] - (p3[0] - p1[0]) / 6
                cp2y = p2[1] - (p3[1] - p1[1]) / 6
                
                d_parts.append(f"C {cp1x:.2f},{cp1y:.2f} {cp2x:.2f},{cp2y:.2f} {p2[0]:.2f},{p2[1]:.2f}")
                i += 2
        else:
            # Linhas simples para contornos pequenos
            for p in points[1:]:
                d_parts.append(f"L {p[0]:.2f},{p[1]:.2f}")
        
        d_parts.append("Z")  # Fechar caminho
        return " ".join(d_parts)
    
    def _optimize_svg(self, svg_content: str, img_shape: tuple) -> str:
        """
        Otimiza SVG para uso em 3D:
        - Normaliza viewBox para escala real em mm
        - Remove metadados desnecessários
        - Garante grupo principal nomeado
        """
        h, w = img_shape[:2]
        
        # Adicionar atributo de tamanho real em mm se não existir
        # O viewBox é mantido em pixels, mas adicionamos metadata
        
        # Garantir que há um grupo com id "stamp-design"
        if 'id="stamp-design"' not in svg_content:
            svg_content = svg_content.replace(
                '<g ',
                '<g id="stamp-design" ',
                1
            )
            if 'id="stamp-design"' not in svg_content:
                # Wrapping de emergência
                svg_content = svg_content.replace(
                    '</svg>',
                    f'</svg>'
                )
        
        # Normalizar dimensões para mm (50mm = tamanho padrão do carimbo)
        # Isso é importante para o pipeline 3D
        svg_content = re.sub(
            r'width="[\d.]+(?:px)?"',
            f'width="{self.target_size_mm}mm"',
            svg_content
        )
        svg_content = re.sub(
            r'height="[\d.]+(?:px)?"',
            f'height="{self.target_size_mm}mm"',
            svg_content
        )
        
        return svg_content
    
    def _validate_for_3d_printing(self, svg_content: str) -> dict:
        """
        Valida SVG para impressão 3D alimentícia.
        Detecta problemas potenciais.
        """
        issues = []
        warnings = []
        
        # Verificar se tem caminhos fechados
        if "Z" not in svg_content and "z" not in svg_content:
            issues.append("Caminhos não fechados detectados - pode causar problemas na extrusão")
        
        # Verificar tamanho do arquivo (SVG muito complexo)
        size_kb = len(svg_content) / 1024
        if size_kb > 500:
            warnings.append(f"SVG complexo ({size_kb:.0f}KB) - processamento 3D pode ser lento")
        
        # Contar paths
        path_count = svg_content.count("<path")
        if path_count > 200:
            warnings.append(f"Muitos caminhos ({path_count}) - simplificar pode melhorar qualidade de impressão")
        
        if path_count == 0:
            issues.append("Nenhum caminho encontrado no SVG - imagem pode estar vazia")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "path_count": path_count,
            "size_kb": round(size_kb, 2)
        }
    
    def _get_svg_stats(self, svg_content: str) -> dict:
        """Estatísticas do SVG gerado"""
        path_count = svg_content.count("<path")
        
        # Contar pontos aproximadamente
        m_count = len(re.findall(r'[ML]\s', svg_content))
        c_count = len(re.findall(r'[C]\s', svg_content))
        point_count = m_count + c_count * 3
        
        return {
            "path_count": path_count,
            "point_count": point_count,
            "file_size_kb": round(len(svg_content) / 1024, 2)
        }
    
    def _empty_svg(self, width: int, height: int) -> str:
        """SVG vazio para casos de falha"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <g id="stamp-design" fill="black">
    <rect x="10" y="10" width="{width-20}" height="{height-20}" rx="5" />
  </g>
</svg>'''
