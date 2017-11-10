#! /usr/bin/env python3

import queue
import unittest
from unittest.mock import MagicMock

import frontend
import mailqueue


class TestSendHandler(unittest.TestCase):
    def setUp(self):
        self.q = queue.Queue(1)
        self.handler = frontend.SendHandler(self.q)
        self.valid_request_dict = {
            'sender': 'someone',
            'recipients': 'alice, bob',
            'subject': 'important message',
            'body': 'hello!'
        }

    def test_valid_request_should_place_envelope_to_incoming_queue(self):
        self.q.put = MagicMock()
        self.handler.run(self.valid_request_dict)

        self.assertTrue(isinstance(self._last_call_first_arg(self.q.put), mailqueue.Envelope),
                        msg='expected Envelope, got {}'.format(
                            self._last_call_first_arg(self.q.put).__class__.__name__))

    def test_missing_request_keys_should_not_affect_queue(self):
        for k in self.valid_request_dict:
            with self.subTest(field=k):
                q = queue.Queue(1)
                q.put = MagicMock()
                handler = frontend.SendHandler(q)

                r = dict(self.valid_request_dict)
                del r[k]

                with self.assertRaises(ValueError) as cm:
                    handler.run(r)

                self.assertTrue(k in cm.exception.args[0],
                                msg='expected exception description "{}" to contain "{}"'.format(
                                    cm.exception.args[0], k
                                ))
                q.put.assert_not_called()

    def test_message_body_should_be_taken_from_request(self):
        expected_body = 'this will be a body of the message'
        r = dict(self.valid_request_dict)
        r['body'] = expected_body

        self.handler.run(r)

        envelope = self._queue_pop()
        self.assertEqual(expected_body + '\n', envelope.message.get_content())

    def test_message_header_should_contain_values_from_request(self):
        input_fields = {
            'sender': 'From',
            'recipients': 'To',
            'subject': 'Subject'
        }

        test_value = 'value_used_by_test'

        for input_field, message_field in input_fields.items():
            with self.subTest(input_field=input_field, message_field=message_field):
                r = dict(self.valid_request_dict)
                r[input_field] = test_value

                self.handler.run(r)

                envelope = self._queue_pop()
                self.assertEqual(test_value, envelope.message[message_field])

    @staticmethod
    def _last_call_first_arg(mock):
        """Convenience method to return the first argument of the last call to the mock."""
        return mock.call_args[0][0]

    def _queue_pop(self):
        self.assertFalse(self.q.empty(),
                         msg='the queue is empty, expected it to contain at least one message')
        return self.q.get()


class TestMailQueueAppender(unittest.TestCase):
    def test_happy_path(self):
        # Using the "Humble Object" pattern to test the logic which is executed in a separate
        # thread in production code: http://xunitpatterns.com/Humble%20Object.html
        #
        # Therefore we have to be a little more invasive than usually (e.g. we are accessing a
        # private method).
        input_queue = queue.Queue(1)
        input_queue.put('something')

        def outq_factory():
            q = mailqueue.MailQueue()
            q.put = MagicMock()
            return q

        appender = frontend.MailQueueAppender(input_queue, outq_factory)
        appender._relay_one_message()

        appender._mailqueue.put.assert_called_once()


if __name__ == '__main__':
    unittest.main()
