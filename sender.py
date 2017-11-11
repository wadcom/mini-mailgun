#! /usr/bin/env python3

import smtplib
import socket
import time

import mailqueue


def main():
    delivery_agent = DeliveryAgent(mailqueue.MailQueue(), DNSResolverStub(), SMTPClient())

    while True:
        if delivery_agent.deliver_single_envelope() == DeliveryAgent.IDLE:
            time.sleep(1)


class DeliveryAgent:
    IDLE = 'IDLE (there was no items in the incoming queue)'
    DONE = 'DONE (there was at least one item to process)'

    RETRY_INTERVAL = 600 # seconds

    def __init__(self, mailqueue, dns_resolver, smtp_client):
        self._dns_resolver = dns_resolver
        self._mailqueue = mailqueue
        self._smtp_client = smtp_client

    def deliver_single_envelope(self):
        envelope = self._mailqueue.get()

        if not envelope:
            return self.IDLE

        try:
            mx = self._dns_resolver.get_first_mx(envelope.destination_domain)
        except TemporaryFailure:
            self._mailqueue.schedule_retry_in(envelope, self.RETRY_INTERVAL)
            return self.DONE

        self._smtp_client.send(mx, envelope)
        self._mailqueue.mark_as_sent(envelope)
        return self.DONE


class DNSResolverStub:
    def __init__(self):
        self._mx = {
            'a.com': 'smtp-a',
            'b.com': 'smtp-b',
        }

    def get_first_mx(self, domain):
        try:
            return self._mx[domain]
        except KeyError:
            raise TemporaryFailure("Can't resolve MX for '{}': unknown hostname".format(domain)) \
                from None


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


class TemporaryFailure(Exception):
    """Temporary failure, delivery should be retried"""


if __name__ == '__main__':
    main()