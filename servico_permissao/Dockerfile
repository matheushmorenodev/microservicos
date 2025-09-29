FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED 1

# Instala dependências do sistema, se necessário (ex: para psycopg2)
# RUN apt-get update && apt-get install -y ...

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# O comando para iniciar o worker do Celery
CMD ["celery", "-A", "servico_permissao.celery", "worker", "--loglevel=info"]