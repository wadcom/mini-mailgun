import time
import unittest

import mailqueue
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
        self.mq = mailqueue.MailQueue(fresh=True)
        self.valid_envelope = testhelpers.make_valid_envelope()

    def test_roundtrip(self):
        self.mq.clock = self.FakeClock(123)
        assigned_id = self.mq.put(self.valid_envelope)
        e = self.mq.get()
        self.assertEnvelopesEqual(self.valid_envelope, e)
        self.assertEqual(123, e.next_attempt_at)
        self.assertEqual(mailqueue.Status.QUEUED, e.status)
        self.assertEqual(assigned_id, e.id)

    def test_empty_queue_should_return_none_on_get(self):
        self.assertIsNone(self.mq.get())

    def test_mailqueue_with_fresh_should_drop_database(self):
        self.mq.put(self.valid_envelope)
        self.assertIsNone(mailqueue.MailQueue(fresh=True).get())

    def test_messages_should_be_persisted(self):
        self.mq.put(self.valid_envelope)
        self.assertEnvelopesEqual(self.valid_envelope, mailqueue.MailQueue().get())

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

    def test_missing_submission_should_return_none_for_status(self):
        self.assertIsNone(self.mq.get_status('unused', 1))

    def test_envelope_status_should_be_returned(self):
        e = self.valid_envelope
        id1 = self.mq.put(e)
        id2 = self.mq.put(e)
        expected = [(id1, mailqueue.Status.QUEUED), (id2, mailqueue.Status.QUEUED)]
        result = self.mq.get_status(e.client_id, e.submission_id)
        self.assertEqual(sorted(expected), sorted(result))

    def test_new_envelope_should_have_zero_delivery_attempts(self):
        e = self._put_and_get_envelope()
        self.assertEqual(0, e.delivery_attempts)

    def test_scheduled_retry_should_increase_delivery_attempts_count(self):
        e = self._put_and_get_envelope()
        self.mq.schedule_retry_in(e, 0)
        e = self.mq.get()
        self.assertEqual(1, e.delivery_attempts)

    def test_undeliverable_envelopes_should_not_be_retrieved(self):
        e = self._put_and_get_envelope()
        self.mq.mark_as_undeliverable(e)
        self.assertIsNone(self.mq.get())

    def test_envelope_marked_undeliverable_should_have_updated_status(self):
        e = self._put_and_get_envelope()
        self.mq.mark_as_undeliverable(e)
        self.assertEqual([(1, mailqueue.Status.UNDELIVERABLE)],
                         self.mq.get_status(e.client_id, e.submission_id))

    def test_mailqueue_manager_should_be_instantiated_successfully(self):
        mailqueue.Manager()

    def test_message_taken_should_not_be_retrieved_by_another_instance(self):
        mq1 = mailqueue.MailQueue(fresh=True)
        mq2 = mailqueue.MailQueue(fresh=False)
        mq1.put(testhelpers.make_valid_envelope())
        mq1.get()
        self.assertIsNone(mq2.get())

    def test_sharded_envelopes_should_be_retrieved_by_correct_shards(self):
        mq1 = mailqueue.MailQueue(fresh=True, shards=2, shard=0)
        mq2 = mailqueue.MailQueue(fresh=False, shards=2, shard=1)
        mq1.put(testhelpers.make_valid_envelope())
        self.assertIsNone(mq1.get())
        self.assertIsNotNone(mq2.get())

    def test_status_of_another_clients_submission_should_not_be_returned(self):
        e = self.valid_envelope
        e.client_id = 'A'
        self.mq.put(e)
        self.assertIsNone(self.mq.get_status('B', e.submission_id))

    def test_envelopes_before_cutoff_should_be_removed(self):
        self.mq.clock = self.FakeClock(100)
        e = self._put_and_get_envelope()
        self.mq.mark_as_sent(e)
        self.mq.clock.set(200)
        self.assertEqual(1, self.mq.remove_inactive_envelopes(50))

    def test_envelopes_after_cutoff_should_not_be_removed(self):
        self.mq.clock = self.FakeClock(100)
        e = self._put_and_get_envelope()
        self.mq.mark_as_sent(e)
        self.assertEqual(0, self.mq.remove_inactive_envelopes(50))

    def test_undeliverable_envelopes_should_be_considered_inactive(self):
        self.mq.clock = self.FakeClock(100)
        e = self._put_and_get_envelope()
        self.mq.mark_as_undeliverable(e)
        self.mq.clock.set(200)
        self.assertEqual(1, self.mq.remove_inactive_envelopes(50))

    def assertEnvelopesEqual(self, expected, actual):
        if expected:
            self.assertIsNotNone(actual)

        self.assertEqual(expected.recipients, actual.recipients)
        self.assertEqual(expected.destination_domain, actual.destination_domain)
        self.assertEqual(str(expected.message), str(actual.message))
        self.assertEqual(expected.submission_id, actual.submission_id)

    def _put_and_get_envelope(self):
        self.mq.put(self.valid_envelope)
        return self.mq.get()
