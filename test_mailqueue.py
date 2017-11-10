from email.message import EmailMessage
import unittest

from mailqueue import Envelope, Item, MailQueue


class TestItem(unittest.TestCase):
    def test_deserializing_should_produce_email_message(self):
        item = Item(id=1, message_text='From: a\n\n')
        message = item.as_email()
        self.assertEqual('a', message['From'])


class TestMailQueue(unittest.TestCase):
    def setUp(self):
        self.valid_envelope = Envelope('sender@address.com',
                                       ['alice@target.domain', 'bob@target.domain'],
                                       'target.domain',
                                        self._create_valid_email()
                                       )

    def test_roundtrip(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)

        expected = Item(id=1, message_text=self.valid_envelope.message.as_string())
        self.assertItemsEqual(expected, mq.get())

    def test_empty_queue_should_return_none_on_get(self):
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_mailqueue_with_fresh_should_drop_database(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_messages_should_be_persisted(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)

        self.assertEqual(self.valid_envelope.message.as_string(), MailQueue().get().message_text)

    def test_message_marked_as_sent_should_not_be_retrieved(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)
        item = mq.get()
        mq.mark_as_sent(item)

        self.assertIsNone(mq.get())

    def assertItemsEqual(self, expected_item, actual_item):
        self.assertEqual(expected_item.id, actual_item.id)
        self.assertEqual(expected_item.message_text, actual_item.message_text)

    @staticmethod
    def _create_valid_email():
        message = EmailMessage()
        message['From'] = 'me@example.com'
        message['To'] = 'you@example.com'
        message['Subject'] = 'valid email'
        message.set_content('indeed!')
        return message
