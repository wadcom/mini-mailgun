#! /usr/bin/env python3

import logging
import smtplib
import socket
import time

import mailqueue

def main():
    setup_logging()

    delivery_agent = DeliveryAgent(mailqueue.MailQueue(), DNSResolverStub(), SMTPClient())

    while True:
        # TODO: retrieve a batch of messages and group by destination domain to reuse SMTP sessions
        # to the same MX
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

        logging.info('Took envelope {} for delivery (domain={})'.format(
            envelope.id, envelope.destination_domain))

        try:
            mx = self._dns_resolver.get_first_mx(envelope.destination_domain)
            logging.debug('Envelope {}: MX for {} is {}'.format(envelope.id,
                                                                envelope.destination_domain,
                                                                mx))
        except TemporaryFailure as e:
            logging.warning(
                'Envelope {}: temporary failure ({}), scheduling to retry in {} seconds'.format(
                    envelope.id, e, self.RETRY_INTERVAL
            ))

            self._mailqueue.schedule_retry_in(envelope, self.RETRY_INTERVAL)
            return self.DONE

        self._smtp_client.send(mx, envelope)
        logging.info('Envelope {}: successfully delivered to {}'.format(envelope.id, mx))

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


def setup_logging():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s %(message)s',
                        datefmt='%x %X',
                        level=logging.DEBUG)
    logging.info('Starting up...')


if __name__ == '__main__':
    main()