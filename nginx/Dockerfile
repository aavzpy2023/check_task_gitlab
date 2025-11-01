# /nginx/Dockerfile
# SSS v4.2.0 - Dockerfile para el servicio de Reverse Proxy Nginx

FROM nginx:1.25-alpine

# Eliminar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Copiar nuestra configuración personalizada
COPY nginx.conf /etc/nginx/conf.d/default.conf