#! /usr/bin/env python3

import smtplib
import socket
import time

import mailqueue

def main():
    # TODO: this is a prototype and should be reworked

    mq = mailqueue.MailQueue()
    while True:
        envelope = mq.get()
        if envelope:
            smtp_hostname = get_mx_for_domain(envelope.destination_domain)

            try:
                # TODO: take port from configuration
                server = smtplib.SMTP(host=smtp_hostname, port=5000)
            except socket.gaierror:
                import sys
                # TODO: log it properly
                sys.stderr.write('error resolving {}\n'.format(smtp_hostname))
                # TODO: mark delivery failure
                sys.exit(1)

            server.send_message(envelope.message)
            server.quit()

            # TODO: handle errors
            mq.mark_as_sent(envelope)
        else:
            time.sleep(1)


def get_mx_for_domain(domain):
    return {
        'a.com': 'smtp-a',
        'b.com': 'smtp-b',
    }[domain]


if __name__ == '__main__':
    main()