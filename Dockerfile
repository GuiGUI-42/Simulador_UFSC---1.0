# Usar imagem leve do Python
FROM python:3.10-slim

# Instalar dependências do sistema necessárias para matplotlib, numpy, scipy, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    libatlas-base-dev \
    libffi-dev \
    libssl-dev \
    libpng-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o código do projeto
COPY . .

# Variáveis de ambiente para Flask
ENV FLASK_APP=simulador_flask.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Comando padrão para produção
CMD ["gunicorn", "-b", "0.0.0.0:8080", "simulador_flask:app"]
