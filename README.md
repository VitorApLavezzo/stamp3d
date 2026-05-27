# 🍪 Stamp3D — Sistema Automático de Carimbos 3D para Doces

Sistema web completo que transforma imagens em carimbos 3D prontos para impressão FDM.

```
Upload de Imagem → Pipeline Automático → STL Pronto para Imprimir
```

---

## 🎯 O que faz

| Etapa | Manual (antes) | Stamp3D (agora) |
|-------|---------------|-----------------|
| Remover fundo | Photoshop manual | Automático (rembg) |
| Limpar imagem | Manual | Automático (OpenCV) |
| Engrossar linhas | Manual | Automático (mín. 1.2mm) |
| Fechar contornos | Manual | Automático |
| Vetorizar SVG | Inkscape manual | Automático (potrace) |
| Gerar relevo 3D | Blender manual | Automático (CadQuery/OpenSCAD) |
| Montar carimbo | Blender manual | Automático |
| Exportar STL | Manual | Automático |

---

## 🏗️ Arquitetura

```
stamp3d/
├── frontend/          # React + Vite + Three.js
│   └── src/
│       ├── pages/     # Dashboard, NewStamp, Project, Projects
│       ├── components/ # Layout, Preview3D
│       └── utils/     # API client
│
├── backend/           # FastAPI + Python
│   ├── api/routes/    # upload, process, export, projects
│   ├── core/          # config, database
│   ├── processing/
│   │   ├── image/     # Processamento OpenCV + rembg
│   │   ├── vector/    # Vetorização potrace + fallback
│   │   └── cad/       # Geração 3D CadQuery/OpenSCAD/trimesh
│   └── services/      # Pipeline orchestrator
│
├── storage/
│   ├── uploads/       # Imagens originais
│   ├── exports/       # SVG + STL gerados
│   └── temp/          # Processamento temporário
│
└── docker-compose.yml
```

---

## 🚀 Instalação Rápida

### Pré-requisitos

- Python 3.10+
- Node.js 18+
- potrace (`apt install potrace` / `brew install potrace`)
- (Opcional) CadQuery ou OpenSCAD para geração 3D avançada

### 1. Clone e configure

```bash
git clone <repo>
cd stamp3d
```

### 2. Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Criar .env (opcional)
cp .env.example .env

# Iniciar
uvicorn main:app --reload --port 8000
```

Backend disponível em: http://localhost:8000  
Documentação Swagger: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend disponível em: http://localhost:5173

---

## 🐳 Docker (Alternativa)

```bash
# Iniciar tudo com Docker
docker-compose up -d

# Ver logs
docker-compose logs -f backend

# Parar
docker-compose down
```

---

## 📐 Parâmetros Técnicos do Carimbo

Replicando exatamente o fluxo Blender:

| Parâmetro | Valor Padrão | Descrição |
|-----------|-------------|-----------|
| Diâmetro | 50mm | Topo circular |
| Base | 4mm | Altura da base |
| Relevo | 6mm | Altura do relevo SVG |
| Scale X | 0.1 | Escala horizontal do SVG |
| Scale Y | 0.1 | Escala vertical do SVG |
| Scale Z | 0.2 | Altura relativa do relevo |
| Location Z | 15mm | Posição Z do desenho |
| Esp. mín. linha | 1.2mm | Linhas mais finas são engrossadas |

---

## 🔌 API Endpoints

```
POST /api/v1/upload              → Upload + início do pipeline
GET  /api/v1/projects            → Listar projetos
GET  /api/v1/projects/{id}       → Status + detalhes do projeto
POST /api/v1/projects/{id}/reprocess → Re-processar
DELETE /api/v1/projects/{id}     → Remover

GET  /api/v1/export/stl/{id}     → Download STL
GET  /api/v1/export/svg/{id}     → Download SVG
GET  /api/v1/export/zip/{id}     → Download ZIP (tudo)
```

---

## 🎛️ Pipeline de Processamento

### Etapa 1: Processamento de Imagem (0-20%)
1. Carregar imagem (PNG/JPG/WEBP)
2. Remover fundo com **rembg** (IA)
3. Extrair objeto principal
4. Converter para escala de cinza
5. Aumentar contraste (CLAHE)
6. **Engrossar linhas < 1.2mm** (regra para FDM)
7. Fechar contornos abertos
8. Remover ruído e artefatos
9. Binarizar (Otsu)

### Etapa 2: Vetorização (20-50%)
1. Converter para BMP
2. Vetorizar com **potrace** (ou fallback OpenCV)
3. Otimizar caminhos SVG
4. Validar para impressão 3D

### Etapa 3: Geração 3D (50-90%)
Método 1: **CadQuery** (paramétrico, mais preciso)
Método 2: **OpenSCAD** (via script gerado automaticamente)
Método 3: **trimesh + numpy** (fallback garantido)

---

## ⚙️ Configurações (`.env`)

```env
# Banco de dados
DATABASE_URL=sqlite+aiosqlite:///./stamp3d.db
# Para produção:
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/stamp3d

# CORS
ALLOWED_ORIGINS=["http://localhost:5173"]

# Parâmetros padrão do carimbo
STAMP_DIAMETER=50.0
STAMP_BASE_HEIGHT=4.0
STAMP_RELIEF_HEIGHT=6.0
STAMP_SCALE_X=0.1
STAMP_SCALE_Y=0.1
STAMP_SCALE_Z=0.2
STAMP_LOCATION_Z=15.0
MIN_LINE_WIDTH_MM=1.2

# Debug
DEBUG=true
```

---

## 🖨️ Configurações de Impressão Recomendadas

| Parâmetro | Valor |
|-----------|-------|
| Material | PETG alimentício ou PLA |
| Layer Height | 0.2mm |
| Infill | 20% |
| Perimeters | 3 |
| Supports | Não necessário |
| Bed Adhesion | Brim (recomendado) |

---

## 🗺️ Roadmap (Futuras funcionalidades)

- [ ] IA treinada para tipos específicos de imagens
- [ ] Geração automática de GCODE
- [ ] Integração com Octoprint
- [ ] Fila de impressão com priorização
- [ ] Múltiplos formatos de carimbo (quadrado, coração, etc.)
- [ ] Geração em lote + ZIP
- [ ] Painel administrativo
- [ ] Pedidos automáticos por cliente
- [ ] Celery + Redis para processamento distribuído

---

## 🐛 Troubleshooting

**rembg não funciona:**
```bash
pip install rembg onnxruntime
# O modelo será baixado automaticamente na primeira execução
```

**potrace não encontrado:**
```bash
# Ubuntu/Debian
sudo apt install potrace

# macOS
brew install potrace

# Windows
# Baixar de: http://potrace.sourceforge.net/
```

**CadQuery não instala via pip:**
```bash
# Usar conda (recomendado)
conda install -c conda-forge cadquery
```

**Erro de CORS:**
Verificar `ALLOWED_ORIGINS` no `.env` ou `core/config.py`

---

## 📄 Licença

MIT — Use livremente para seu negócio de carimbos para doces! 🍪
