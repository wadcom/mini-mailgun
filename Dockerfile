FROM alpine:3.6

RUN \
    apk add --no-cache python3

RUN mkdir /mailq
VOLUME /mailq

COPY \
    entrypoint.py \
    frontend.py \
    mailqueue.py \
    mmglib.py \
    \
    /app/

WORKDIR /app

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.py"]