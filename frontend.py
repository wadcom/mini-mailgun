#! /usr/bin/env python3

import collections
from email.message import EmailMessage
import http.server
import json
import socketserver
import uuid

import mailqueue


mq_manager = mailqueue.Manager()
valid_client_ids = set()


def main():
    load_client_info()

    server = ThreadedHTTPServer(('', 5000), Handler)

    mq_manager.start()
    server.serve_forever()


def load_client_info():
    global valid_client_ids
    with open('/conf/clients', 'r') as f:
        valid_client_ids = set(s.strip() for s in f.readlines())


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """This server spawns a new thread for each incoming request"""
    pass


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/send':
            handler = SendHandler(mq_manager)
        elif self.path == '/status':
            handler = StatusHandler(mq_manager)
        else:
            self.send_error(404, 'Not found')

        self._handle_post_with(handler)

    def _handle_post_with(self, handler):
        try:
            body = self._get_json_body()

            if body.get('client_id') not in valid_client_ids:
                self.send_error(401, 'Missing or invalid client_id: {}'.format(body))
                return

            response_data = handler.run(body)
            self._respond_json(response_data)
        except ValueError as e:
            self.send_error(400, e.args[0])

    def _get_json_body(self):
        if self.headers['Content-Type'] != 'application/json':
            raise ValueError('Expected application/json data')

        try:
            content_length = int(self.headers['Content-Length'])
        except (TypeError, ValueError):
            raise ValueError('Invalid or missing content length') from None

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
        envelopes = self._make_envelopes(request_dict['client_id'], submission_id, message,
                                         request_dict['recipients'])

        for e in envelopes:
            self._mail_queue.put(e)

        return {'result': 'queued', 'submission_id': submission_id}

    @staticmethod
    def _make_envelopes(client_id, submission_id, message, recipients):
        domain_to_recipients = collections.defaultdict(list)
        for r in recipients:
            _, domain = r.split('@')
            domain_to_recipients[domain].append(r)

        return (mailqueue.Envelope(recipients=r, destination_domain=d, message=message,
                                   submission_id=submission_id, status=mailqueue.Status.QUEUED,
                                   client_id=client_id)
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

        assert 'client_id' in request_dict, \
            "missing 'client_dict' in request, should've been caught during authentication " \
            "(request: {})".format(request_dict)

        status = self._mail_queue.get_status(request_dict['client_id'], submission_id)
        if status:
            return {'result': 'success', 'status': self._aggregate_status(status)}
        else:
            return {'result': 'error', 'message': 'unknown submission id {}'.format(submission_id)}

    def _aggregate_status(self, status_tuples):
        statuses = collections.Counter(status for _, status in status_tuples)
        if len(statuses) == 1:
            return status_tuples[0][1]
        else:
            return mailqueue.Status.QUEUED


if __name__ == '__main__':
    main()
