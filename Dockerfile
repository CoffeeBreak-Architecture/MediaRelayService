  
FROM python:3

RUN apt-get update

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY ./src /app

WORKDIR /app/

ENV PYTHONPATH=/app

CMD [ "python", "server2.py" ]