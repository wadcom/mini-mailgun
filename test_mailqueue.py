import time
import unittest

from mailqueue import MailQueue
import testhelpers


class TestMailQueue(unittest.TestCase):
    class FakeClock:
        def __init__(self, initial_time=None):
            self._now = initial_time or time.time()

        def set(self, timestamp):
            self._now = timestamp

        def time(self):
            return self._now

    def setUp(self):
        self.mq = MailQueue(fresh=True)
        self.valid_envelope = testhelpers.make_valid_envelope()

    def test_roundtrip(self):
        self.mq.clock = self.FakeClock(123)
        self.mq.put(self.valid_envelope)
        e = self.mq.get()
        self.assertEnvelopesEqual(self.valid_envelope, e)
        self.assertEqual(123, e.next_attempt_at)

    def test_empty_queue_should_return_none_on_get(self):
        self.assertIsNone(self.mq.get())

    def test_mailqueue_with_fresh_should_drop_database(self):
        self.mq.put(self.valid_envelope)
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_messages_should_be_persisted(self):
        self.mq.put(self.valid_envelope)
        self.assertEnvelopesEqual(self.valid_envelope, MailQueue().get())

    def test_message_marked_as_sent_should_not_be_retrieved(self):
        item = self._put_and_get_envelope()
        self.mq.mark_as_sent(item)

        self.assertIsNone(self.mq.get())

    def test_message_to_retry_should_not_be_retrieved(self):
        e = self._put_and_get_envelope()
        self.mq.schedule_retry_in(e, 1000)
        self.assertIsNone(self.mq.get())

    def test_message_to_retry_should_be_retrieved_once_its_time_comes(self):
        self.mq.clock = self.FakeClock()
        e = self._put_and_get_envelope()
        self.mq.schedule_retry_in(e, 300)
        self.mq.clock.set(e.next_attempt_at + 600)
        self.assertEqual(e.id, self.mq.get().id)

    def test_mixed_messages_should_result_in_getting_correct_later_message(self):
        self.mq.put(self.valid_envelope)
        e = self._put_and_get_envelope()
        self.mq.schedule_retry_in(e, 1000)
        self.assertNotEqual(e.id, self.mq.get())

    def test_retry_interval_should_start_with_current_time(self):
        self.mq.clock = self.FakeClock(100)
        self.mq.put(self.valid_envelope)
        self.mq.clock.set(200)
        e = self.mq.get()
        self.mq.schedule_retry_in(e, 10)
        self.mq.clock.set(205)
        self.assertIsNone(self.mq.get())

    # TODO increment number of retries

    def assertEnvelopesEqual(self, expected, actual):
        if expected:
            self.assertIsNotNone(actual)

        self.assertEqual(expected.sender, actual.sender)
        self.assertEqual(expected.recipients, actual.recipients)
        self.assertEqual(expected.destination_domain, actual.destination_domain)
        self.assertEqual(str(expected.message), str(actual.message))

    def _put_and_get_envelope(self):
        self.mq.put(self.valid_envelope)
        return self.mq.get()
