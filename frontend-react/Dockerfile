FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Exponer el puerto de Vite a la red interna de Docker
EXPOSE 3000

# SSS: Corrección Definitiva - Usamos 'npm run dev' que sabe cómo encontrar
# y ejecutar el binario de Vite desde node_modules.
CMD ["npm", "run", "dev"]