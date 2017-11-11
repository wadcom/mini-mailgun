FROM alpine:3.6

RUN \
    apk add --no-cache python3 && \
    pip3 install aiosmtpd

RUN mkdir /mailq /logs
VOLUME /logs /mailq

ENV PYTHONUNBUFFERED=TRUE

WORKDIR /app

COPY \
    frontend.py \
    mailqueue.py \
    sender.py \
    smtpstub.py \
    test_*.py \
    unittests.sh \
    \
    ./


EXPOSE 5000

ENTRYPOINT /app/unittests.sh