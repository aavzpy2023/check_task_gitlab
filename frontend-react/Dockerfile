# /frontend-react/Dockerfile

# --- Etapa 1: Build ---
    FROM node:18-alpine AS build
    WORKDIR /app
    COPY package.json .
    RUN npm install
    COPY . .
    RUN npm run build
    
    # --- Etapa 2: Production ---
    FROM nginx:1.25-alpine
    # Copiar los archivos estáticos construidos desde la etapa anterior
    COPY --from=build /app/dist /usr/share/nginx/html
    # Copiar configuración de Nginx si es necesaria (opcional)
    # COPY nginx.conf /etc/nginx/conf.d/default.conf
    EXPOSE 80
    CMD ["nginx", "-g", "daemon off;"]