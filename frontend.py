#! /usr/bin/env python3

import collections
from email.message import EmailMessage
import http.server
import json
import queue
import socketserver
import threading

import mailqueue


incoming_queue = queue.Queue(10)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """This server spawns a new thread for each incoming request"""
    pass


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/send':
            self._handle_post_with(SendHandler)
        else:
            self.send_error(404, 'Not found')

    def _handle_post_with(self, handler_class):
        try:
            body = self._get_json_body()
            response_data = handler_class(incoming_queue).run(body)
            self._respond_json(response_data)
        except ValueError as e:
            self.send_error(400, e.args[0])

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


class SendHandler:
    def __init__(self, incoming_queue):
        self._incoming_queue = incoming_queue

    def run(self, request_dict):
        message = self._make_message(request_dict)
        envelopes = self._make_envelopes(message, request_dict['recipients'])

        for e in envelopes:
            self._incoming_queue.put(e)

        return {'result': 'queued'}

    def _make_envelopes(self, message, recipients):
        domain_to_recipients = collections.defaultdict(list)
        for r in recipients:
            _, domain = r.split('@')
            domain_to_recipients[domain].append(r)

        return (mailqueue.Envelope(sender='XXX', recipients=r, destination_domain=d,
                                   message=message)
                for d, r in domain_to_recipients.items())

    def _make_message(self, request_dict):
        message = EmailMessage()
        try:
            message['From'] = request_dict['sender']
            message['To'] = request_dict['recipients']
            message['Subject'] = request_dict['subject']
            message.set_content(request_dict['body'])
        except KeyError as e:
            raise ValueError('Missing request field "{}"'.format(e))

        return message


class MailQueueAppender(threading.Thread):
    def __init__(self, input_queue, outq_factory):
        super(MailQueueAppender, self).__init__()
        self.daemon = True

        self._input_queue = input_queue

        self._mailqueue = None

        # The queue object should be created in the same thread it's going to be used, so we
        # remember the factory and instantiate the queue when the new thread is spawned.
        self._outq_factory = outq_factory

    def run(self):
        while True:
            self._relay_one_message()

    def _relay_one_message(self):
        if not self._mailqueue:
            self._mailqueue = self._outq_factory()

        message = self._input_queue.get()
        self._mailqueue.put(message)


def main():
    mailq_appender = MailQueueAppender(incoming_queue, mailqueue.MailQueue)
    server = ThreadedHTTPServer(('', 5000), Handler)

    mailq_appender.start()
    server.serve_forever()


if __name__ == '__main__':
    main()
