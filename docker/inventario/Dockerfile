# Imagen del microservicio Inventario. Construir desde la RAIZ del repo:
#   docker build -f docker/inventario/Dockerfile -t sportmarket-inventario .
FROM node:lts-alpine
WORKDIR /app
COPY microservicios/inventario/package*.json ./
RUN npm install --omit=dev
COPY microservicios/inventario/ ./
EXPOSE 3004
CMD ["node", "src/server.js"]
