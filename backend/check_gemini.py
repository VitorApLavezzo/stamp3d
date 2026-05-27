"""
Diagnóstico Gemini - versão robusta
"""
import sys
import os

# Mostrar qual Python está sendo usado
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
print(f"Path: {sys.path[:3]}")
print()

# Tentar importar
try:
    import google.generativeai as genai
    print(f"✅ google-generativeai importado OK: {genai.__version__}")
except ImportError as e:
    print(f"❌ Erro ao importar: {e}")
    print()
    print("Tentando localizar o pacote...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "google-generativeai"],
        capture_output=True, text=True
    )
    print(result.stdout or result.stderr)
    print()
    print("SOLUÇÃO: Execute estes comandos:")
    print(f"  {sys.executable} -m pip install google-generativeai")
    sys.exit(1)

# Carregar .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

key = os.environ.get("GEMINI_API_KEY", "")
if not key or "sua-chave" in key:
    print("❌ GEMINI_API_KEY não configurada no .env")
    sys.exit(1)

print(f"✅ Chave encontrada: {key[:15]}...")
genai.configure(api_key=key)

print("\nModelos disponíveis com generateContent:\n")
for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(f"  {m.name}")