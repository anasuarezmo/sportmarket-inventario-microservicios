FROM python:3.12-slim
WORKDIR /app
COPY microservicios/bodegas/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY microservicios/bodegas/ ./
EXPOSE 5002
CMD ["python", "app.py"]
