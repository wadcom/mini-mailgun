#! /usr/bin/env python3

import asyncio
import os
import threading
import time
import queue

import aiosmtpd.controller

class SMTPHandler:
    def __init__(self, log_queue):
        self._log_queue = log_queue
        self._simulate_failure_for = {}

    async def handle_MAIL(self, server, session, envelope, sender, *args):
        if sender.startswith('tempfail-once-'):
            if sender not in self._simulate_failure_for:
                self._simulate_failure_for[sender] = True
        elif sender.startswith('stall-'):
            await asyncio.sleep(15)

        envelope.mail_from = sender
        return '250 ok'

    async def handle_DATA(self, server, session, envelope):
        if self._simulate_failure_for.get(envelope.mail_from, False):
            self._simulate_failure_for[envelope.mail_from] = False
            return '451 Aborted as directed by the special sender address; try again later'

        self._log_queue.put(envelope)
        return '250 Ok, accepted'


class SMTPServer(threading.Thread):
    def __init__(self, log_queue):
        super(SMTPServer, self).__init__()
        self.daemon = True

        self._controller = aiosmtpd.controller.Controller(SMTPHandler(log_queue),
                                                          hostname='0.0.0.0', port=5000)

    def run(self):
        self._controller.start()

        while True:
            time.sleep(1)


def main():
    domain = os.environ.get('DOMAIN', 'unspecified.domain')
    log_queue = queue.Queue(10)

    server = SMTPServer(log_queue)
    server.start()

    logfile = open('/logs/{}-smtp.log'.format(domain), 'w')
    while True:
        log_item = log_queue.get()
        logfile.write(log_item.mail_from + '\n')
        logfile.flush()


if __name__ == '__main__':
    main()
