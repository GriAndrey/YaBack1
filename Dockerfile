FROM  ubuntu:latest
MAINTAINER Andrey Gribunin 'andrey@gribunin.ru'
RUN apt-get update -y
RUN apt-get install -y python-pip python-dev build-essential
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT ['python']
CMD ['app.py']