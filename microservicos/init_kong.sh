#!/bin/sh

KONG_ADMIN_URL="http://kong:8001"

echo "Aguardando Kong iniciar em $KONG_ADMIN_URL..."
until curl --output /dev/null --silent --head --fail "$KONG_ADMIN_URL"; do
    printf '.'
    sleep 2
done
echo ""
echo "Kong detectado! Iniciando configuração..."

# --- 1. AUTH SERVICE (O CRÍTICO) ---
# O truque: A URL upstream JÁ CONTÉM /api
# Quando o usuário chamar /api/auth/login/ -> Kong remove /api/auth -> sobra /login/
# Kong junta: http://servico-autenticacao:8001/api + /login/
echo "Configurando Auth Service..."

# Usamos PUT em vez de POST para garantir que se o serviço já existe, ele seja ATUALIZADO
curl -s -X PUT "$KONG_ADMIN_URL/services/auth-service" \
  -d url='http://servico-autenticacao:8001/api' > /dev/null

# Configura a rota
curl -s -X PUT "$KONG_ADMIN_URL/services/auth-service/routes/auth-route" \
  -d 'paths[]=/api/auth' \
  -d strip_path=true > /dev/null


# --- 2. MIDDLEWARE ---
echo "Configurando Middleware..."
curl -s -X PUT "$KONG_ADMIN_URL/services/middleware-service" \
  -d url='http://middleware:8000' > /dev/null

curl -s -X PUT "$KONG_ADMIN_URL/services/middleware-service/routes/middleware-route" \
  -d 'paths[]=/api/departments' \
  -d 'paths[]=/api/rooms' \
  -d 'paths[]=/api/iots' \
  -d strip_path=false > /dev/null


# --- 3. BANCO DE DADOS (ADMIN + STATIC) ---
echo "Configurando DB Service..."
curl -s -X PUT "$KONG_ADMIN_URL/services/db-service" \
  -d url='http://servico-banco-dados:8002' > /dev/null

# Rota Admin
curl -s -X PUT "$KONG_ADMIN_URL/services/db-service/routes/db-admin-route" \
  -d 'paths[]=/admin' \
  -d strip_path=false > /dev/null

# Rota Static (Para o CSS do admin funcionar)
curl -s -X PUT "$KONG_ADMIN_URL/services/db-service/routes/db-static-route" \
  -d 'paths[]=/static' \
  -d strip_path=false > /dev/null

curl -s -X PUT "$KONG_ADMIN_URL/services/db-service/routes/db-permissions-route" \
  -d 'paths[]=/api/user-permissions' \
  -d strip_path=false > /dev/null

echo "Kong Configurado com Sucesso!"