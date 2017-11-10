#! /usr/bin/env python3

import os
import threading
import time
import queue

import aiosmtpd.controller

class SMTPHandler:
    def __init__(self, log_queue):
        self._log_queue = log_queue

    async def handle_DATA(self, server, session, envelope):
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
