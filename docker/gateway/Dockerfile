# Imagen del API Gateway. Construir desde la RAIZ del repo:
#   docker build -f docker/gateway/Dockerfile -t sportmarket-gateway .
FROM node:lts-alpine
WORKDIR /app
COPY api-gateway/package*.json ./
RUN npm install --omit=dev
COPY api-gateway/ ./
EXPOSE 8080
CMD ["node", "src/server.js"]
