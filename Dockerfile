FROM  python:3.14-rc-alpine3.21
ENV PYTHONPATH='.'

RUN pip install pytest

WORKDIR '/data/'
COPY . .
CMD ["pytest"]