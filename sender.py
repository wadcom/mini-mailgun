#! /usr/bin/env python3

import logging
import os
import smtplib
import socket
import time

import dns.resolver

import mailqueue

def main():
    setup_logging()

    delivery_agent = DeliveryAgent(mailqueue.MailQueue(), get_dns_resolver(), SMTPClient())

    if 'RETRY_INTERVAL' in os.environ:
        delivery_agent.retry_interval = int(os.environ['RETRY_INTERVAL'])

    while True:
        # TODO: retrieve a batch of messages and group by destination domain to reuse SMTP sessions
        # to the same MX
        if delivery_agent.deliver_single_envelope() == DeliveryAgent.IDLE:
            time.sleep(1)


class DeliveryAgent:
    IDLE = 'IDLE (there was no items in the incoming queue)'
    DONE = 'DONE (there was at least one item to process)'

    def __init__(self, mailqueue, dns_resolver, smtp_client):
        self.retry_interval = 600 # seconds

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
            # TODO: loop through MXs
            mx = self._dns_resolver.get_first_mx(envelope.destination_domain)
            logging.debug('Envelope {}: MX for {} is {}'.format(envelope.id,
                                                                envelope.destination_domain,
                                                                mx))
            self._smtp_client.send(mx, envelope)
        except TemporaryFailure as e:
            logging.warning(
                'Envelope {}: temporary failure ({}), scheduling to retry in {} seconds'.format(
                    envelope.id, e, self.retry_interval
            ))

            self._mailqueue.schedule_retry_in(envelope, self.retry_interval)
            return self.DONE

        logging.info('Envelope {}: successfully delivered to {}'.format(envelope.id, mx))

        self._mailqueue.mark_as_sent(envelope)
        return self.DONE

class SMTPClient:
    # XXX: test for network issues (e.g. connection timeout etc)
    def __init__(self):
        self._smtp_port = int(os.environ.get('SMTP_PORT', '25'))

    def send(self, smtp_hostname, envelope):
        logging.debug('Envelope {}: establishing SMTP connection to {}:{}'.format(envelope.id,
                                                                                  smtp_hostname,
                                                                                  self._smtp_port))
        try:
            server = smtplib.SMTP(host=smtp_hostname, port=self._smtp_port)
        except socket.gaierror:
            import sys
            # TODO: log it properly
            sys.stderr.write('error resolving {}\n'.format(smtp_hostname))
            # TODO: mark delivery failure
            sys.exit(1)

        # TODO: use correct recipients
        try:
            server.send_message(envelope.message)
            server.quit()
        except smtplib.SMTPException as e:
            raise TemporaryFailure('{} {}'.format(e.args[0], e.args[1].decode())) from None



class TemporaryFailure(Exception):
    """Temporary failure, delivery should be retried"""


def get_dns_resolver():
    static_mx_config = os.environ.get('STATIC_MX_CONFIG')
    if static_mx_config:
        logging.info('Using static MX configuration: {}'.format(static_mx_config))
        return DNSResolverStub({
            k: v for k, v in [entry.split(':') for entry in static_mx_config.split(',')]
        })
    else:
        return DNSResolver()

class DNSResolverStub:
    def __init__(self, domain_to_mx_dict):
        self._mx = domain_to_mx_dict

    def get_first_mx(self, domain):
        try:
            return self._mx[domain]
        except KeyError:
            raise TemporaryFailure("Can't resolve MX for '{}': unknown hostname".format(domain)) \
                from None


class DNSResolver:
    def get_first_mx(self, domain):
        mx_records = sorted((r.preference, r.exchange.to_text(omit_final_dot=True))
                            for r in dns.resolver.query(domain, 'MX'))
        # TODO: handle no MX records
        return mx_records[0][1]


def setup_logging():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s %(message)s',
                        datefmt='%x %X',
                        level=logging.DEBUG)
    logging.info('Starting up...')


if __name__ == '__main__':
    main()