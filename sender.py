#! /usr/bin/env python3

import logging
import os
import smtplib
import socket
import threading
import time

import dns.resolver

import mailqueue


DELIVERY_THREADS = 5


def main():
    setup_logging()

    retry_interval = int(os.environ.get('RETRY_INTERVAL', 600))
    shard, shards = get_sharding_configuration()

    mq_manager = mailqueue.Manager(shard=shard, shards=shards)
    mq_manager.start()

    for _ in range(DELIVERY_THREADS):
        d = DeliveryThread(mq_manager, retry_interval)
        d.start()

    while True:
        time.sleep(1)


class DeliveryThread(threading.Thread):
    def __init__(self, mq_manager, retry_interval):
        super().__init__()
        self.daemon = True
        self._delivery_agent = DeliveryAgent(mq_manager, get_dns_resolver(), SMTPClient())
        self._delivery_agent.retry_interval = retry_interval

    def run(self):
        while True:
            self._delivery_agent.deliver_single_envelope()


class DeliveryAgent:
    IDLE = 'IDLE (there was no items in the incoming queue)'
    DONE = 'DONE (there was at least one item to process)'

    def __init__(self, mailqueue, dns_resolver, smtp_client):
        self.max_delivery_attempts = 4 # 1 initial, 3 retries
        self.retry_interval = 600 # seconds

        self._dns_resolver = dns_resolver
        self._mailqueue = mailqueue
        self._smtp_client = smtp_client

    def deliver_single_envelope(self):
        envelope = self._mailqueue.get()

        if not envelope:
            return self.IDLE

        logging.info('Took envelope {} for delivery (domain={}, recipients={})'.format(
            envelope.id, envelope.destination_domain, envelope.recipients))

        mxs = self._get_mxs(envelope)
        if not mxs:
            return self.DONE

        delivered_to = self._try_delivering_to_all_mxs(envelope, mxs)
        self._handle_attempt_outcome(delivered_to, envelope)

        return self.DONE

    def _get_mxs(self, envelope):
        try:
            mxs = self._dns_resolver.get_mxs(envelope.destination_domain)
            logging.debug('Envelope {}: MXs for {} are {}'.format(envelope.id,
                                                                  envelope.destination_domain,
                                                                  mxs))
            return mxs
        except TemporaryFailure as e:
            logging.warning(
                "Envelope {}: can't resolve MXs for {}: {}".format(envelope.id,
                                                                   envelope.destination_domain,
                                                                   e))
            self._handle_temporary_failure(envelope)

    def _handle_attempt_outcome(self, delivered_to, envelope):
        if delivered_to:
            logging.info('Envelope {}: successfully delivered to {}'.format(envelope.id,
                                                                            delivered_to))
            self._mailqueue.mark_as_sent(envelope)
        else:
            self._handle_temporary_failure(envelope)

    def _handle_temporary_failure(self, envelope):
        attempts_performed = envelope.delivery_attempts + 1
        if attempts_performed < self.max_delivery_attempts:
            logging.warning(
                'Envelope {}: temporary failures delivering to all MXs for {}, '
                'scheduling to retry in {} seconds'.format(envelope.id,
                                                           envelope.destination_domain,
                                                           self.retry_interval))
            self._mailqueue.schedule_retry_in(envelope, self.retry_interval)
        else:
            logging.warning(
                "Envelope {}: can't deliver after {} attempts, "
                "marking as undeliverable".format(envelope.id, attempts_performed))
            self._mailqueue.mark_as_undeliverable(envelope)

    def _try_delivering_to_all_mxs(self, envelope, mxs):
        for mx in mxs:
            try:
                self._smtp_client.send(mx, envelope)
                return mx
            except TemporaryFailure as e:
                logging.warning(
                    'Envelope {}: temporary failure delivering to {}: {}'.format(envelope.id,
                                                                                 mx,
                                                                                 e))


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
        except socket.gaierror as e:
            raise TemporaryFailure("Can't resolve {}: {}".format(smtp_hostname, e)) from None
        except (smtplib.SMTPException, OSError) as e:
            raise TemporaryFailure('Error establishing SMTP connection to {}:{}: {}'.format(
                smtp_hostname, self._smtp_port, e)) from None

        # TODO: use correct recipients
        try:
            server.send_message(envelope.message)
            server.quit()
        except smtplib.SMTPException as e:
            raise TemporaryFailure('{} {}'.format(e.args[0], e.args[1].decode())) from None



class TemporaryFailure(Exception):
    """Temporary failure, delivery should be retried"""


def get_dns_resolver():
    # TODO: each DeliveryThread will do this (thus repeating the work and littering the log),
    # need to restructure it.
    static_mx_config = os.environ.get('STATIC_MX_CONFIG')
    if static_mx_config:
        logging.info('Using static MX configuration: {}'.format(static_mx_config))
        return DNSResolverStub(parse_static_mx_config(static_mx_config))
    else:
        return DNSResolver()

def parse_static_mx_config(s):
    static_mx_config = {}
    for domain_mxs in s.split(';'):
        domain, mxs = domain_mxs.split(':')
        static_mx_config[domain] = mxs.split(',')

    return static_mx_config


class DNSResolverStub:
    def __init__(self, domain_to_mxs_dict):
        self._mxs = domain_to_mxs_dict

    def get_mxs(self, domain):
        try:
            return self._mxs[domain]
        except KeyError:
            raise TemporaryFailure("Can't resolve MX for '{}': unknown hostname".format(domain)) \
                from None


class DNSResolver:
    def get_mxs(self, domain):
        mx_records = sorted((r.preference, r.exchange.to_text(omit_final_dot=True))
                            for r in dns.resolver.query(domain, 'MX'))
        return [mx for _preference, mx in mx_records]


def get_sharding_configuration():
    shard, shards = os.environ.get('SHARD', '1/1').split('/')
    logging.info('Running as shard {} of {}'.format(shard, shards))
    return int(shard) - 1, int(shards)


def setup_logging():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s %(message)s',
                        datefmt='%x %X',
                        level=logging.DEBUG)
    logging.info('Starting up...')


if __name__ == '__main__':
    main()