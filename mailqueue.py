import unittest

class MailQueue:
    def __init__(self):
        self._queue = []

    def get(self):
        try:
            return self._queue.pop()
        except IndexError:
            return None

    def put(self, message):
        self._queue.append(message)

class TestMailQueue(unittest.TestCase):
    def test_roundtrip(self):
        message = 'something'
        mq = MailQueue()
        mq.put(message)
        self.assertEqual(message, mq.get())

    def test_empty_queue_should_return_none_on_get(self):
        self.assertIsNone(MailQueue().get())
