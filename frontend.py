#! /usr/bin/env python3

import http.server
import json
import queue
import socketserver
import threading

import mmglib

incoming_queue = queue.Queue(10)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/logs':
            try:
                body = self._get_json_body()
            except ValueError as e:
                self.send_error(400, e.args[0])
                return

            incoming_queue.put(body)

            self.send_response(200)
            self.end_headers()
            self.wfile.write('{}\n'.format(json.dumps({'status': 'success'})).encode())
        elif self.path == '/send':
            incoming_queue.put(mmglib.Message())
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


class MailQueueAppender(threading.Thread):
    def __init__(self):
        super(MailQueueAppender, self).__init__()
        self.daemon = True

    def run(self):
        while True:
            message = incoming_queue.get()


def main():
    mailq_appender = MailQueueAppender()
    server = ThreadedHTTPServer(('', 5000), Handler)

    mailq_appender.start()
    server.serve_forever()



if __name__ == '__main__':
    main()


