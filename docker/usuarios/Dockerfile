FROM python:3.12-slim
WORKDIR /app
COPY microservicios/usuarios-autenticacion/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY microservicios/usuarios-autenticacion/ ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 5001
CMD ["python", "-m", "app.server"]
