# Imagen del microservicio Catalogo. Construir desde la RAIZ del repo:
#   docker build -f docker/catalogo/Dockerfile -t sportmarket-catalogo .
FROM node:lts-alpine
WORKDIR /app
COPY microservicios/catalogo/package*.json ./
RUN npm install --omit=dev
COPY microservicios/catalogo/ ./
EXPOSE 3003
CMD ["node", "src/server.js"]
