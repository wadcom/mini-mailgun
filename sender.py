#! /usr/bin/env python3

import smtplib
import socket
import time

import mailqueue

def main():
    # TODO: this is a prototype and should be reworked

    mq = mailqueue.MailQueue()
    client = SMTPClient()

    while True:
        envelope = mq.get()
        if not envelope:
            time.sleep(1)
            continue

        smtp_hostname = get_mx_for_domain(envelope.destination_domain)

        client.send(smtp_hostname, envelope)

        # TODO: handle errors
        mq.mark_as_sent(envelope)


class SMTPClient:
    def send(self, smtp_hostname, envelope):
        try:
            # TODO: take port from configuration
            server = smtplib.SMTP(host=smtp_hostname, port=5000)
        except socket.gaierror:
            import sys
            # TODO: log it properly
            sys.stderr.write('error resolving {}\n'.format(smtp_hostname))
            # TODO: mark delivery failure
            sys.exit(1)

        # TODO: use correct recipients
        server.send_message(envelope.message)
        server.quit()


def get_mx_for_domain(domain):
    return {
        'a.com': 'smtp-a',
        'b.com': 'smtp-b',
    }[domain]


if __name__ == '__main__':
    main()