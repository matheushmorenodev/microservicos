# servico-banco-dados/Dockerfile
FROM python:3.10-slim
RUN apt-get update && apt-get install -y tzdata
ENV TZ=America/Sao_Paulo
WORKDIR /app
ENV PYTHONUNBUFFERED 1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8002
# DEPOIS (versão final):
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && gunicorn db_project.wsgi:application --bind 0.0.0.0:8002"]