#! /usr/bin/env python3

from email.message import EmailMessage
import http.server
import json
import queue
import socketserver
import threading
import unittest
from unittest.mock import MagicMock

import mailqueue


incoming_queue = queue.Queue(10)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/send':
            try:
                body = self._get_json_body()
            except ValueError as e:
                self.send_error(400, e.args[0])
                return

            SendHandler(incoming_queue).run(body)
            self._respond_json({'result': 'queued'})
        else:
            self.send_error(404, 'Not found')

    def _get_json_body(self):
        if self.headers['Content-Type'] != 'application/json':
            raise ValueError('Expected application/json data')

        try:
            content_length = int(self.headers['Content-Length'])
        except ValueError:
            raise ValueError('Invalid content length')

        return json.loads(self.rfile.read(content_length).decode())

    def _respond_json(self, body, status=200):
        self.send_response(status)
        self.end_headers()
        self.wfile.write('{}\n'.format(json.dumps(body)).encode())

###################################################################################################

class SendHandler():
    def __init__(self, incoming_queue):
        self._incoming_queue = incoming_queue

    def run(self, request_dict):
        message = EmailMessage()
        try:
            message['From'] = request_dict['sender']
            message['To'] = request_dict['recipients']
            message['Subject'] = request_dict['subject']
            message.set_content(request_dict['body'])
        except KeyError as e:
            raise ValueError('Missing request field "{}"'.format(e))

        self._incoming_queue.put(message)


class TestSendHandler(unittest.TestCase):
    def setUp(self):
        self.q = queue.Queue(1)
        self.handler = SendHandler(self.q)
        self.valid_request_dict = {
            'sender': 'someone',
            'recipients': 'alice, bob',
            'subject': 'important message',
            'body': 'hello!'
        }

    def test_valid_request_should_place_message_to_incoming_queue(self):
        self.q.put = MagicMock()
        self.handler.run(self.valid_request_dict)
        self.q.put.assert_called_once()

    def test_missing_request_keys_should_not_affect_queue(self):
        for k in self.valid_request_dict:
            with self.subTest(field=k):
                q = queue.Queue(1)
                q.put = MagicMock()
                handler = SendHandler(q)

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

        message = self._queue_pop()
        self.assertEqual(expected_body + '\n', message.get_content())

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

                message = self._queue_pop()
                self.assertEqual(test_value, message[message_field])

    def _queue_pop(self):
        self.assertFalse(self.q.empty(),
                         msg='the queue is empty, expected it to contain at least one message')
        return self.q.get()


###################################################################################################

class MailQueueAppender(threading.Thread):
    def __init__(self, input_queue, outq_factory):
        super(MailQueueAppender, self).__init__()
        self.daemon = True

        self._input_queue = input_queue

        self._mailqueue = None
        self._outq_factory = outq_factory

    def run(self):
        while True:
            self._relay_one_message()

    def _relay_one_message(self):
        if not self._mailqueue:
            self._mailqueue = self._outq_factory()

        message = self._input_queue.get()
        self._mailqueue.put(message)


class TestMailQueueAppender(unittest.TestCase):
    def test_happy_path(self):
        input_queue = queue.Queue(1)
        input_queue.put('something')

        def outq_factory():
            q = mailqueue.MailQueue()
            q.put = MagicMock()
            return q

        appender = MailQueueAppender(input_queue, outq_factory)
        appender._relay_one_message()

        appender._mailqueue.put.assert_called_once()

###################################################################################################

def main():
    mailq_appender = MailQueueAppender(incoming_queue, mailqueue.MailQueue)
    server = ThreadedHTTPServer(('', 5000), Handler)

    mailq_appender.start()
    server.serve_forever()


if __name__ == '__main__':
    main()


