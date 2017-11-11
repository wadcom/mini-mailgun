#! /usr/bin/env python3

import json
import random
import time
import unittest
import urllib.request


class Client:
    # TODO: take it from an environment variable
    MINIMAILGUN_URL = 'http://127.0.0.1:5080/send'

    def sends_email(self, sender, recipients):
        data = {
            'sender': sender,
            'recipients': recipients,
            'subject': 'end-to-end test',
            'body': 'the body of\n the message\n'
        }

        request = urllib.request.Request(self.MINIMAILGUN_URL, data=json.dumps(data).encode(),
                                         headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(request)
        assert response.getcode() == 200, \
            'Request to MiniMailGun returned status code {}, not 200'.format(response.getcode())


class SMTPServer:
    TIMEOUT = 5

    def __init__(self, domain):
        self.domain = domain

    def receives_email_from(self, sender):
        started_at = time.time()
        while True:
            with open(self.domain + '-smtp.log') as logfile:
                if (sender + '\n') in logfile.readlines():
                    return

            assert (time.time() - started_at) <= self.TIMEOUT, \
                "Message from '{}' wasn't received within {} seconds by '{}'".format(sender,
                                                                                     self.TIMEOUT,
                                                                                     self.domain
                                                                                     )

            time.sleep(0.1)


class TestEndToEnd(unittest.TestCase):
    def test_sending_to_single_recipient(self):
        client = Client()
        smtp_server = SMTPServer('a.com')

        sender = self._make_unique_address()
        client.sends_email(sender, ['unused@a.com'])
        smtp_server.receives_email_from(sender)

    def test_delivering_to_different_smtp_servers(self):
        client = Client()
        smtp_a = SMTPServer('a.com')
        smtp_b = SMTPServer('b.com')

        sender = self._make_unique_address()
        client.sends_email(sender, ['a@a.com', 'b@b.com'])
        smtp_a.receives_email_from(sender)
        smtp_b.receives_email_from(sender)

    @staticmethod
    def _make_unique_address():
        return str(random.randint(0, 10**10)) + '@e2e-test.com'


if __name__ == '__main__':
    unittest.main()