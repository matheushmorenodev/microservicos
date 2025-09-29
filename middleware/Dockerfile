# 1. Use uma imagem base oficial do Python. A versão 'slim' é menor.
FROM python:3.10-slim

# 2. Define o diretório de trabalho dentro do contêiner.
WORKDIR /app

# 3. Define uma variável de ambiente para garantir que o output do Python não seja bufferizado.
ENV PYTHONUNBUFFERED 1

# 4. Copia o arquivo de dependências PRIMEIRO para aproveitar o cache do Docker.
COPY requirements.txt .

# 5. Instala as dependências.
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia o código da sua aplicação para o diretório de trabalho.
COPY ./app /app/app

# 7. Expõe a porta que o Uvicorn vai usar.
EXPOSE 8000

# 8. Define o comando para iniciar a aplicação quando o contêiner for executado.
#    --host 0.0.0.0 é crucial para que a aplicação seja acessível de fora do contêiner.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]