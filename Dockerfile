FROM python:3.12-alpine

LABEL maintainer="eunicefelixtine"
LABEL description="Nettoyeur de disque pour développeurs : dossiers de projets + cache Docker"

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser -D -h /home/appuser appuser
COPY --chown=appuser:appuser dev_sweep.py /app/

USER appuser

ENTRYPOINT ["python", "dev_sweep.py"]
