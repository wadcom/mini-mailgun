import unittest

class MailQueue:
    def put(self, message):
        pass

class TestMailQueue(unittest.TestCase):
    def test_put(self):
        mq = MailQueue()
        mq.put('something')
        # TODO: make it a round-trip test
