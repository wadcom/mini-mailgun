#! /usr/bin/env python3

import unittest
from unittest.mock import MagicMock

import mailqueue
import sender


class TestDeliveryAgent(unittest.TestCase):
    class DNSResolverStub:
        pass

    def setUp(self):
        self.mq = mailqueue.MailQueue(fresh=True)
        self.dns_resolver = self.DNSResolverStub()
        self.smtp_client = sender.SMTPClient()

        self.delivery_agent = sender.DeliveryAgent(self.mq, self.dns_resolver, self.smtp_client)

    def test_successful_delivery(self):
        envelope = mailqueue.Envelope(destination_domain='example.com')

        self.mq.get = MagicMock(return_value=envelope)
        self.mq.mark_as_sent = MagicMock()

        self.dns_resolver.get_first_mx = MagicMock(return_value='mail.example.com')

        self.smtp_client.send = MagicMock()

        self.assertDeliveryResultIs(sender.DeliveryAgent.DONE)

        self.mq.get.assert_called_once()
        self.dns_resolver.get_first_mx.assert_called_once_with('example.com')
        self.smtp_client.send.assert_called_once_with('mail.example.com', envelope)
        self.mq.mark_as_sent.assert_called_once()

    def test_no_incoming_messages_should_indicate_being_idle(self):
        self.mq.get = MagicMock(return_value=None)
        self.assertDeliveryResultIs(sender.DeliveryAgent.IDLE)

    def test_mx_resolution_error_should_schedule_delivery_retry(self):
        envelope = mailqueue.Envelope(destination_domain='unresolvable.com')
        self.mq.get = MagicMock(return_value=envelope)
        self.mq.schedule_retry_in = MagicMock()
        self.dns_resolver.get_first_mx = MagicMock(
            side_effect=sender.TemporaryFailure("Can't resolve MX"))

        self.assertDeliveryResultIs(sender.DeliveryAgent.DONE)
        self.mq.schedule_retry_in.assert_called_once_with(envelope,
                                                          self.delivery_agent.RETRY_INTERVAL)

    def assertDeliveryResultIs(self, expected):
        result = self.delivery_agent.deliver_single_envelope()
        self.assertEqual(expected, result)


if __name__ == '__main__':
    unittest.main()
