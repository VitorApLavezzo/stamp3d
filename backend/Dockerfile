FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema (potrace, libcairo para cairosvg)
RUN apt-get update && apt-get install -y \
    potrace \
    libcairo2-dev \
    libffi-dev \
    libglib2.0-dev \
    pkg-config \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Criar diretórios de storage
RUN mkdir -p storage/uploads storage/exports storage/temp

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
