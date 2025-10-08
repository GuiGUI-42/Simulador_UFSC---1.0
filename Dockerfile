# Usar imagem leve do Python
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=simulador_flask.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "simulador_flask:app"]
