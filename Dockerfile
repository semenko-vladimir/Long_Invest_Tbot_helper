FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /opt/tbot

COPY requirements-base.txt requirements-v1.txt ./
COPY deploy/certs/RussianTrustedRootCA.pem deploy/certs/RussianTrustedSubCA.pem /tmp/build-certs/
RUN cat /etc/ssl/certs/ca-certificates.crt /tmp/build-certs/*.pem > /tmp/build-ca.pem \
    && PIP_CERT=/tmp/build-ca.pem python -m pip install --no-cache-dir -r requirements-v1.txt \
    && rm -rf /tmp/build-certs /tmp/build-ca.pem

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

CMD ["python", "app/run.py"]
