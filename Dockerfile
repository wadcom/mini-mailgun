FROM alpine:3.6

RUN \
    apk add --no-cache python3 && \
    pip3 install aiosmtpd

RUN mkdir /mailq /logs
VOLUME /logs /mailq


COPY \
    frontend.py \
    mailqueue.py \
    sender.py \
    smtpstub.py \
    test_*.py \
    unittests.sh \
    \
    /app/

WORKDIR /app

EXPOSE 5000

ENTRYPOINT /app/unittests.sh