#!/bin/bash
# Stamp3D - Script de inicialização para desenvolvimento
# Uso: cd stamp3d && ./start.sh

echo "🍪 Stamp3D — Iniciando..."
echo ""

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️ ${NC} $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }

# ── Verificar que está na raiz do projeto ────────────────────────────────
if [ ! -f "backend/main.py" ]; then
    fail "Execute da raiz do projeto: cd stamp3d && ./start.sh"
    exit 1
fi

# ── Detectar Python 3.10+ ────────────────────────────────────────────────
echo "📋 Verificando dependências:"
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        MINOR=$($cmd -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        MAJOR=$($cmd -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        if [ "${MAJOR}" -ge 3 ] && [ "${MINOR}" -ge 10 ] 2>/dev/null; then
            PYTHON="$cmd"
            ok "Python $($cmd --version 2>&1) → '$cmd'"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && { fail "Python 3.10+ não encontrado"; exit 1; }

command -v node &>/dev/null && ok "Node.js $(node --version)" || warn "Node.js não encontrado — frontend não iniciará"
command -v potrace &>/dev/null && ok "potrace encontrado" || warn "potrace não encontrado (fallback OpenCV será usado)"
echo ""

# ── Backend ──────────────────────────────────────────────────────────────
echo "🔧 Configurando Backend..."
cd backend

# Criar venv se não existir
if [ ! -f "venv/bin/activate" ] && [ ! -f "venv/Scripts/activate" ]; then
    echo "  Criando ambiente virtual..."
    $PYTHON -m venv venv || {
        fail "Falha ao criar venv. Tente: sudo apt install python3-venv"
        exit 1
    }
fi

# Ativar venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi
ok "Ambiente virtual ativado"

echo "  Instalando dependências Python..."
pip install -q --upgrade pip
pip install -q fastapi "uvicorn[standard]" python-multipart pydantic-settings \
    "sqlalchemy[asyncio]" aiosqlite aiofiles \
    opencv-python-headless Pillow numpy svgpathtools trimesh numpy-stl
pip install -q cairosvg 2>/dev/null && ok "cairosvg instalado" || warn "cairosvg opcional não instalado"
pip install -q rembg     2>/dev/null && ok "rembg instalado"    || warn "rembg opcional não instalado (usará fallback)"
ok "Dependências Python OK"

mkdir -p ../storage/uploads ../storage/exports ../storage/temp
ok "Diretórios de storage prontos"

echo "  Iniciando uvicorn na porta 8000..."
uvicorn main:app --reload --port 8000 --host 0.0.0.0 &
BACKEND_PID=$!
cd ..

# Aguardar backend
for i in {1..20}; do
    sleep 1
    curl -sf http://localhost:8000/health &>/dev/null && { ok "Backend pronto em http://localhost:8000"; break; }
    [ $i -eq 20 ] && warn "Backend demorou para responder, continuando..."
done

# ── Frontend ─────────────────────────────────────────────────────────────
echo ""
echo "🎨 Configurando Frontend..."
FRONTEND_PID=""

if command -v node &>/dev/null; then
    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "  Instalando dependências Node.js..."
        npm install
        ok "Dependências Node.js instaladas"
    else
        ok "node_modules já existe"
    fi

    echo "  Iniciando Vite na porta 5173..."
    # Usar o binário local do vite em vez de depender do PATH
    ./node_modules/.bin/vite --port 5173 --host &
    FRONTEND_PID=$!
    cd ..
else
    warn "Node.js não disponível — inicie o frontend manualmente"
fi

# ── Pronto ───────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}✨ Stamp3D rodando!${NC}"
echo ""
echo "  🌐 Frontend:  http://localhost:5173"
echo "  ⚙️  Backend:   http://localhost:8000"
echo "  📖 API Docs:  http://localhost:8000/docs"
echo ""
echo "  Ctrl+C para encerrar"

cleanup() {
    echo ""
    echo "Encerrando..."
    [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    echo "Encerrado. 🍪"
}
trap cleanup EXIT INT TERM
wait
