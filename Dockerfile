FROM python:3.12

ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

COPY ./requirements-base.txt /requirements-base.txt

RUN pip install -r /requirements-base.txt

WORKDIR /app 

COPY ./app /app/

CMD ["python", "/app/run.py"]
