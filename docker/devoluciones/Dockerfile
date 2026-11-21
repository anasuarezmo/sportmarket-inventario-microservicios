FROM python:3.12-slim
WORKDIR /app
COPY microservicios/devoluciones/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY microservicios/devoluciones/ ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 5006
CMD ["python", "app.py"]
