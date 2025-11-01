#!/bin/sh
# SSS v4.2.0 - Entrypoint para el Contenedor de Desarrollo Frontend

# Salir inmediatamente si un comando falla
set -e

echo "--- SSS: Iniciando contenedor de desarrollo frontend ---"

# 1. Ejecutar el build inicial de Vite para crear la carpeta /dist
echo "--- SSS: Ejecutando build inicial de Vite... ---"
npm run build

# 2. Iniciar el proceso de 'watch' de Vite en segundo plano
echo "--- SSS: Iniciando Vite en modo 'watch' en segundo plano... ---"
npm run dev &

# 3. Iniciar Nginx en primer plano (este será el proceso principal del contenedor)
echo "--- SSS: Iniciando Nginx en primer plano... ---"
nginx -g "daemon off;"