#! /usr/bin/env python3

import queue
import unittest
from unittest.mock import MagicMock

import frontend
import mailqueue


class TestSendHandler(unittest.TestCase):
    def setUp(self):
        self._reset_queue()
        self.valid_request_dict = {
            'sender': 'someone',
            'recipients': ['alice@here.com', 'bob@there.com'],
            'subject': 'important message',
            'body': 'hello!'
        }

    def test_valid_request_should_place_envelope_to_incoming_queue(self):
        self.q.put = MagicMock()
        self.handler.run(self.valid_request_dict)

        self.assertTrue(isinstance(self._last_call_first_arg(self.q.put), mailqueue.Envelope),
                        msg='expected Envelope, got {}'.format(
                            self._last_call_first_arg(self.q.put).__class__.__name__))

    # TODO: test for invalid values of recipients

    def test_single_recipient_domain_should_become_destination_domain(self):
        self.q.put = MagicMock()
        self.handler.run(self._valid_request_with_field('recipients', ['someone@recipient.com']))

        self.assertEqual('recipient.com', self._last_call_first_arg(self.q.put).destination_domain)

    def test_two_recipients_in_same_domain_should_result_in_single_envelope(self):
        self.q.put = MagicMock()
        self.handler.run(
            self._valid_request_with_field('recipients',
                                           ['first@recipient.com', 'second@recipient.com']))

        self.q.put.assert_called_once()

    def test_two_recipients_in_different_domains_should_result_in_two_envelopes(self):
        self.handler.run(
            self._valid_request_with_field('recipients',
                                           ['first@first.com', 'second@second.com']))

        result = [self._queue_pop(), self._queue_pop()]
        self.assertTrue(self.q.empty())
        self.assertEqual(['first.com', 'second.com'], list(e.destination_domain for e in result))

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
        self.handler.run(self._valid_request_with_field('body', expected_body))

        envelope = self._queue_pop()
        self.assertEqual(expected_body + '\n', envelope.message.get_content())

    def test_request_recipients_should_become_joined_in_to_header(self):
        self.handler.run(self._valid_request_with_field('recipients', ['a@a.com', 'b@b.com']))
        self.assertEqual('a@a.com, b@b.com', self._queue_pop().message['To'])

    def test_message_header_should_contain_values_from_request(self):
        input_fields = {
            'sender': 'From',
            'subject': 'Subject'
        }

        test_value = 'value_used_by_test@x.com'

        # TODO: simplify, make two separate testcases out of it
        for input_field, message_field in input_fields.items():
            with self.subTest(input_field=input_field, message_field=message_field):
                self._reset_queue()
                self.handler.run(self._valid_request_with_field(input_field, test_value))

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

    def _reset_queue(self):
        self.q = queue.Queue(10)
        self.handler = frontend.SendHandler(self.q)

    def _valid_request_with_field(self, k, v):
        r = dict(self.valid_request_dict)
        r[k] = v
        return r


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
