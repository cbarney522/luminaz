FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV LUMINAZ_HTTPS=1 PORT=8000
# The instance folder holds the database, uploaded documents, backups and the outbox. Mount it as a volume.
VOLUME ["/app/instance"]
EXPOSE 8000
CMD gunicorn "luminaz:create_app()" --bind 0.0.0.0:$PORT --workers 2 --timeout 60
