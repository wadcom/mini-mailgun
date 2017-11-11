from email.message import EmailMessage
import unittest

from mailqueue import Envelope, MailQueue


class TestMailQueue(unittest.TestCase):
    def setUp(self):
        self.valid_envelope = Envelope(sender='sender@address.com',
                                       recipients=['alice@target.domain', 'bob@target.domain'],
                                       destination_domain='target.domain',
                                       message=self._create_valid_email()
                                       )

    def test_roundtrip(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)
        self.assertEnvelopesEqual(self.valid_envelope, mq.get())

    def test_empty_queue_should_return_none_on_get(self):
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_mailqueue_with_fresh_should_drop_database(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_messages_should_be_persisted(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)
        self.assertEnvelopesEqual(self.valid_envelope, MailQueue().get())

    def test_message_marked_as_sent_should_not_be_retrieved(self):
        mq = MailQueue(fresh=True)
        mq.put(self.valid_envelope)
        item = mq.get()
        mq.mark_as_sent(item)

        self.assertIsNone(mq.get())

    def assertEnvelopesEqual(self, expected, actual):
        self.assertEqual(expected.sender, actual.sender)
        self.assertEqual(expected.recipients, actual.recipients)
        self.assertEqual(expected.destination_domain, actual.destination_domain)
        self.assertEqual(str(expected.message), str(actual.message))

    @staticmethod
    def _create_valid_email():
        message = EmailMessage()
        message['From'] = 'me@example.com'
        message['To'] = 'you@example.com'
        message['Subject'] = 'valid email'
        message.set_content('indeed!')
        return message
