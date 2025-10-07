FROM python:3.10-slim
WORKDIR /app
ENV PYTHONPATH /app
ENV PYTHONUNBUFFERED 1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# O comando para iniciar o worker será definido no docker-compose.yml