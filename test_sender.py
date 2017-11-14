#! /usr/bin/env python3

import unittest
from unittest.mock import MagicMock

import mailqueue
import sender
import testhelpers


class TestDeliveryAgent(unittest.TestCase):
    class DNSResolverStub:
        pass

    def setUp(self):
        self.mq = mailqueue.MailQueue(fresh=True)
        self.mq.mark_as_sent = MagicMock()
        self.mq.mark_as_undeliverable = MagicMock()
        self.mq.schedule_retry_in = MagicMock()
        self.dns_resolver = self.DNSResolverStub()
        self.dns_resolver.get_first_mx = MagicMock(return_value='mail.example.com')
        self.smtp_client = sender.SMTPClient()
        self.smtp_client.send = MagicMock()

        self.delivery_agent = sender.DeliveryAgent(self.mq, self.dns_resolver, self.smtp_client)

    def test_successful_delivery(self):
        envelope = mailqueue.Envelope(destination_domain='example.com')

        self.mq.get = MagicMock(return_value=envelope)

        self.assertDeliveryResultIs(sender.DeliveryAgent.DONE)

        self.mq.get.assert_called_once()
        self.dns_resolver.get_first_mx.assert_called_once_with('example.com')
        self.smtp_client.send.assert_called_once_with('mail.example.com', envelope)
        self.mq.mark_as_sent.assert_called_once()

    def test_no_incoming_messages_should_indicate_being_idle(self):
        self.mq.get = MagicMock(return_value=None)
        self.assertDeliveryResultIs(sender.DeliveryAgent.IDLE)

    def test_mx_resolution_error_should_schedule_delivery_retry(self):
        envelope = self._envelope_with_unresolvable_mx()
        self.delivery_agent.deliver_single_envelope()
        self.assertRetryScheduled(envelope)

    def test_smtp_error_should_schedule_delivery_retry(self):
        envelope = self._envelope_to_be_processed()
        self.smtp_client.send = MagicMock(
            side_effect=sender.TemporaryFailure('Error during SMTP session'))
        self.delivery_agent.deliver_single_envelope()
        self.assertRetryScheduled(envelope)

    def test_retry_interval_should_be_settable(self):
        self.delivery_agent.retry_interval = 123
        envelope = self._envelope_with_unresolvable_mx()
        self.delivery_agent.deliver_single_envelope()
        self.mq.schedule_retry_in.assert_called_once_with(envelope, 123)

    def test_too_many_delivery_attempts_should_mark_envelope_undeliverable(self):
        envelope = self._envelope_with_unresolvable_mx()
        envelope.delivery_attempts = self.delivery_agent.max_delivery_attempts - 1
        self.delivery_agent.deliver_single_envelope()
        self.mq.mark_as_undeliverable.assert_called_once_with(envelope)

    def assertDeliveryResultIs(self, expected):
        result = self.delivery_agent.deliver_single_envelope()
        self.assertEqual(expected, result)

    def assertRetryScheduled(self, envelope):
        self.mq.mark_as_sent.assert_not_called()
        self.mq.schedule_retry_in.assert_called_once_with(envelope,
                                                          self.delivery_agent.retry_interval)

    def _envelope_to_be_processed(self):
        envelope = testhelpers.make_valid_envelope()
        self.mq.get = MagicMock(return_value=envelope)
        return envelope

    def _envelope_with_unresolvable_mx(self):
        envelope = self._envelope_to_be_processed()
        envelope.destination_domain = 'unresolvable.com'
        self.dns_resolver.get_first_mx = MagicMock(
            side_effect=sender.TemporaryFailure("Can't resolve MX"))
        return envelope


if __name__ == '__main__':
    unittest.main()
