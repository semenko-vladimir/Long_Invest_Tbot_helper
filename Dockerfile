FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /opt/tbot

COPY requirements-base.txt requirements-v1.txt ./
RUN python -m pip install --no-cache-dir -r requirements-v1.txt

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

CMD ["python", "app/run.py"]
