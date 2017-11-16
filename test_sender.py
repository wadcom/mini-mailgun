#! /usr/bin/env python3

import unittest
from unittest.mock import call, MagicMock

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
        self.dns_resolver.get_mxs = MagicMock(return_value=['mail.example.com'])
        self.smtp_client = sender.SMTPClient()
        self.smtp_client.send = MagicMock()

        self.delivery_agent = sender.DeliveryAgent(self.mq, self.dns_resolver, self.smtp_client)

    def test_successful_delivery(self):
        envelope = self._envelope_to_be_processed()
        envelope.destination_domain='example.com'

        self.assertDeliveryResultIs(sender.DeliveryAgent.DONE)

        self.mq.get.assert_called_once()
        self.dns_resolver.get_mxs.assert_called_once_with('example.com')
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

    def test_unavailable_first_mx_should_cause_delivery_attempt_to_next_one(self):
        def fail_mx1(hostname, _envelope):
            if hostname == 'mx1.a.com':
                raise sender.TemporaryFailure('simulated failure on the first MX')

        self.dns_resolver.get_mxs = MagicMock(return_value=['mx1.a.com', 'mx2.a.com'])
        self.smtp_client.send = MagicMock(side_effect=fail_mx1)
        envelope = self._envelope_to_be_processed()

        self.delivery_agent.deliver_single_envelope()

        self.smtp_client.send.assert_has_calls(
            [call('mx1.a.com', envelope), call('mx2.a.com', envelope)])

    def test_multiple_mxs_should_not_cause_multiple_deliveries(self):
        self.dns_resolver.get_mxs = MagicMock(return_value=['mx1.a.com', 'mx2.a.com'])
        self._envelope_to_be_processed()
        self.delivery_agent.deliver_single_envelope()
        self.smtp_client.send.assert_called_once()

    def test_permanent_failure_should_mark_email_undeliverable(self):
        envelope = self._envelope_to_be_processed()
        self.smtp_client.send = MagicMock(
            side_effect=sender.PermanentFailure('Error during SMTP session'))
        self.delivery_agent.deliver_single_envelope()
        self.mq.mark_as_undeliverable.assert_called_once_with(envelope)
        self.mq.schedule_retry_in.assert_not_called()

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
        self.dns_resolver.get_mxs = MagicMock(
            side_effect=sender.TemporaryFailure("Can't resolve MX"))
        return envelope


class TestStaticMXConfigParser(unittest.TestCase):
    def test_sample(self):
        self.assertEqual(
            {
                'a.com': ['mx1', 'mx2'],
                'b.com': ['mx1'],
                'c.com': ['mx2', 'mx3'],
            },
            sender.parse_static_mx_config('a.com:mx1,mx2;b.com:mx1;c.com:mx2,mx3')
        )

if __name__ == '__main__':
    unittest.main()
