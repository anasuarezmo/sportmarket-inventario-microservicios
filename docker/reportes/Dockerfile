# Imagen del microservicio Reportes y Alertas. Construir desde la RAIZ del repo:
#   docker build -f docker/reportes/Dockerfile -t sportmarket-reportes .
FROM python:3.12-slim
WORKDIR /app
COPY microservicios/reportes-alertas/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY microservicios/reportes-alertas/ ./
EXPOSE 5007
CMD ["python", "-m", "app.server"]
