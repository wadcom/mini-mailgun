#! /usr/bin/env python3

import json
import random
import time
import unittest
import urllib.request


class Client:
    def __init__(self, minimailgun_url):
        self.minimailgun_url = minimailgun_url

    def sends_email_from(self, sender):
        data = {
            'sender': sender,
            'recipients': 'unused@for.now',
            'subject': 'end-to-end test',
            'body': 'the body of\n the message\n'
        }

        request = urllib.request.Request(self.minimailgun_url, data=json.dumps(data).encode(),
                                         headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(request)
        assert response.getcode() == 200, \
            'Request to MiniMailGun returned status code {}, not 200'.format(response.getcode())


class SMTPServer:
    TIMEOUT = 5

    def receives_email_from(self, sender):
        started_at = time.time()
        while True:
            with open('smtpstub.log') as logfile:
                if (sender + '\n') in logfile.readlines():
                    return

            assert (time.time() - started_at) <= self.TIMEOUT, \
                "Message from '{}' wasn't received within {} seconds".format(sender, self.TIMEOUT)

            time.sleep(0.1)


class TestEndToEnd(unittest.TestCase):
    def test_sending_to_single_recipient(self):
        # TODO: take it from an environment variable
        client = Client('http://127.0.0.1:5080/send')
        smtp_server = SMTPServer()

        sender = self._make_unique_address()
        client.sends_email_from(sender)
        smtp_server.receives_email_from(sender)

    @staticmethod
    def _make_unique_address():
        return str(random.randint(0, 10**10)) + '@e2e-test.com'


if __name__ == '__main__':
    unittest.main()