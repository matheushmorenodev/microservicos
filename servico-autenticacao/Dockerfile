# servico-autenticacao/Dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y tzdata
ENV TZ=America/Sao_Paulo

WORKDIR /app

ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

# Comando para iniciar o servidor de desenvolvimento do Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]