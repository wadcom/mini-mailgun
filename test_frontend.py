#! /usr/bin/env python3

import unittest
from unittest.mock import MagicMock

import frontend
import mailqueue

import testhelpers


class TestSendHandler(unittest.TestCase):
    def setUp(self):
        self.mq = mailqueue.MailQueue()
        self.mq.put = MagicMock()
        self.handler = frontend.SendHandler(self.mq)
        self.valid_request_dict = {
            'sender': 'someone',
            'recipients': ['alice@here.com', 'bob@there.com'],
            'subject': 'important message',
            'body': 'hello!'
        }

    def test_successful_run_should_return_correct_response(self):
        r = self.handler.run(self.valid_request_dict)
        self.assertEqual('queued', r['result'])
        self.assertIn('submission_id', r)

    def test_valid_request_should_place_envelope_to_incoming_queue(self):
        e = self._run_handler_and_get_result_envelope(self.valid_request_dict)
        self.assertTrue(isinstance(e, mailqueue.Envelope),
                        msg='expected Envelope, got {}'.format(e.__class__.__name__))

    def test_valid_request_should_assign_submission_id(self):
        e = self._run_handler_and_get_result_envelope(self.valid_request_dict)
        self.assertIsNotNone(e.submission_id)

    def test_valid_request_should_be_placed_as_queued(self):
        e = self._run_handler_and_get_result_envelope(self.valid_request_dict)
        self.assertEqual(mailqueue.Status.QUEUED, e.status)

    def test_each_request_should_generate_new_submission_id(self):
        e1 = self._run_handler_and_get_result_envelope(self.valid_request_dict)
        self.mq.put.reset_mock()
        e2 = self._run_handler_and_get_result_envelope(self.valid_request_dict)
        self.assertNotEqual(e1.submission_id, e2.submission_id)

    # TODO: test for invalid values of recipients

    def test_single_recipient_domain_should_become_destination_domain(self):
        e = self._run_handler_and_get_result_envelope(
            self._valid_request_with_field('recipients', ['someone@recipient.com']))
        self.assertEqual('recipient.com', e.destination_domain)

    def test_two_recipients_in_same_domain_should_result_in_single_envelope(self):
        self.handler.run(
            self._valid_request_with_field('recipients',
                                           ['first@recipient.com', 'second@recipient.com']))
        self.mq.put.assert_called_once()

    def test_two_recipients_in_different_domains_should_result_in_two_envelopes(self):
        self.handler.run(
            self._valid_request_with_field('recipients',
                                           ['first@first.com', 'second@second.com']))

        self.assertEqual(2, self.mq.put.call_count)

    def test_missing_request_keys_should_not_affect_queue(self):
        for k in self.valid_request_dict:
            with self.subTest(field=k):
                self.mq.put.reset_mock()

                r = dict(self.valid_request_dict)
                del r[k]

                with self.assertRaises(ValueError) as cm:
                    self.handler.run(r)

                self.assertTrue(k in cm.exception.args[0],
                                msg='expected exception description "{}" to contain "{}"'.format(
                                    cm.exception.args[0], k
                                ))
                self.mq.put.assert_not_called()

    def test_message_body_should_be_taken_from_request(self):
        expected_body = 'this will be a body of the message'

        e = self._run_handler_and_get_result_envelope(
            self._valid_request_with_field('body', expected_body))
        self.assertEqual(expected_body + '\n', e.message.get_content())

    def test_request_recipients_should_become_joined_in_to_header(self):
        e = self._run_handler_and_get_result_envelope(
            self._valid_request_with_field('recipients', ['a@a.com', 'b@b.com']))
        self.assertEqual('a@a.com, b@b.com', e.message['To'])

    def test_request_sender_should_appear_in_message(self):
        e = self._run_handler_and_get_result_envelope(
            self._valid_request_with_field('sender', 'my@own.sender.com'))
        self.assertEqual('my@own.sender.com', e.message['From'])

    def test_request_subject_should_appear_in_message(self):
        e = self._run_handler_and_get_result_envelope(
            self._valid_request_with_field('subject', 'my subject'))
        self.assertEqual('my subject', e.message['Subject'])

    @staticmethod
    def _last_call_first_arg(mock):
        """Convenience method to return the first argument of the last call to the mock."""
        return mock.call_args[0][0]

    def _run_handler_and_get_result_envelope(self, request):
        self.handler.run(request)
        return self._last_call_first_arg(self.mq.put)

    def _valid_request_with_field(self, k, v):
        r = dict(self.valid_request_dict)
        r[k] = v
        return r


class TestStatusHandler(unittest.TestCase):
    # TODO: test for missing and invalid parameters in request_dict

    def setUp(self):
        self.mq = mailqueue.MailQueue(fresh=True)
        self.handler = frontend.StatusHandler(self.mq)

    def test_unknown_status_should_result_in_error(self):
        self.mq.get_status = MagicMock(return_value=None)
        self.assertEqual({'result': 'error', 'message': 'unknown submission id 1'},
                         self._get_submission_status(1))

    def test_request_should_query_mail_queue(self):
        status = 'opaque status value from mail queue'

        submission_id = self.mq.put(testhelpers.make_valid_envelope())
        self.mq.get_status = MagicMock(return_value=status)

        result = self._get_submission_status(submission_id)

        self.mq.get_status.assert_called_once_with(submission_id)
        self.assertEqual({'result': 'success', 'status': status}, result)

    def test_missing_submission_id_should_raise_value_error(self):
        self.mq.get_status = MagicMock()
        with self.assertRaises(ValueError) as cm:
            self.handler.run({})

        self.assertIn('submission_id', cm.exception.args[0])
        self.mq.get_status.assert_not_called()

    def _get_submission_status(self, submission_id):
        return self.handler.run({'submission_id': submission_id})


if __name__ == '__main__':
    unittest.main()
