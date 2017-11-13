#! /usr/bin/env python3

import collections
from email.message import EmailMessage
import http.server
import json
import socketserver
import uuid

import mailqueue


mq_manager = mailqueue.Manager()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """This server spawns a new thread for each incoming request"""
    pass


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/send':
            self._handle_post_with(SendHandler)
        elif self.path == '/status':
            self._handle_post_with(StatusHandler)
        else:
            self.send_error(404, 'Not found')

    def _handle_post_with(self, handler_class):
        try:
            body = self._get_json_body()
            response_data = handler_class(mq_manager).run(body)
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
    def __init__(self, mail_queue):
        self._mail_queue = mail_queue

    def run(self, request_dict):
        message = self._make_message(request_dict)
        submission_id = uuid.uuid4().hex
        envelopes = self._make_envelopes(submission_id, message, request_dict['recipients'])

        for e in envelopes:
            self._mail_queue.put(e)

        return {'result': 'queued', 'submission_id': submission_id}

    @staticmethod
    def _make_envelopes(submission_id, message, recipients):
        domain_to_recipients = collections.defaultdict(list)
        for r in recipients:
            _, domain = r.split('@')
            domain_to_recipients[domain].append(r)

        return (mailqueue.Envelope(sender='XXX', recipients=r, destination_domain=d,
                                   message=message, submission_id=submission_id,
                                   status=mailqueue.Status.QUEUED)
                for d, r in domain_to_recipients.items())

    @staticmethod
    def _make_message(request_dict):
        message = EmailMessage()
        try:
            message['From'] = request_dict['sender']
            message['To'] = request_dict['recipients']
            message['Subject'] = request_dict['subject']
            message.set_content(request_dict['body'])
        except KeyError as e:
            raise ValueError('Missing request field "{}"'.format(e))

        return message


class StatusHandler:
    def __init__(self, mail_queue):
        self._mail_queue = mail_queue

    def run(self, request_dict):
        try:
            submission_id = request_dict['submission_id']
        except KeyError as e:
            raise ValueError('Missing request field "{}"'.format(e)) from None

        status = self._mail_queue.get_status(submission_id)
        if status:
            return {'result': 'success', 'status': status}
        else:
            return {'result': 'error', 'message': 'unknown submission id {}'.format(submission_id)}


def main():
    server = ThreadedHTTPServer(('', 5000), Handler)

    mq_manager.start()
    server.serve_forever()


if __name__ == '__main__':
    main()
