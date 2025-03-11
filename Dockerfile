FROM python:3.12

ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

COPY ./requirements.txt /requirements.txt

RUN echo "tensorflow==2.17.0" > docker-requirements.txt \
    && grep -ivE "tensorflow|tensorflow-intel|tensorboard" /requirements.txt >> docker-requirements.txt \
    && pip install -r docker-requirements.txt

WORKDIR /app 

COPY ./app /app/

CMD ["python", "/app/run.py"]
