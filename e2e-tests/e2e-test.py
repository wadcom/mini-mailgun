#! /usr/bin/env python3

import collections
import json
import random
import time
import unittest
import urllib.request

Submission = collections.namedtuple('Submission', 'id')


MAX_DELIVERY_ATTEMPTS = 4 # 1 initial, 3 retries
SMTPSTUB_RETRY_INTERVAL = 5


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.smtp_a = SMTPServer('a.com')
        self.smtp_b = SMTPServer('b.com')

    def test_sending_to_single_recipient(self):
        email = Email(recipients=['unused@a.com'])
        self.client.sends_email(email)
        self.smtp_a.receives_email(email)
        # TODO: test status after email is sent

    def test_delivering_to_different_smtp_servers(self):
        email = Email(recipients=['a@a.com', 'b@b.com'])
        self.client.sends_email(email)
        self.smtp_a.receives_email(email)
        self.smtp_b.receives_email(email)
        # TODO: test status after email is sent

    def test_partial_delivery(self):
        email = Email(recipients=['a@a.com', 'undeliverable@aaa.com', 'b@b.com'])
        self.client.sends_email(email)
        self.smtp_a.receives_email(email)
        self.smtp_b.receives_email(email)

    def test_delivery_retry(self):
        email = Email.causing_server_to_tempfail_once(recipients=['a@a.com'])
        submission = self.client.sends_email(email)
        self.client.observes_submission_status(submission, 'queued')
        time.sleep(2 * SMTPSTUB_RETRY_INTERVAL)
        self.smtp_a.receives_email(email)
        self.client.observes_submission_status(submission, 'sent')

    def test_delivery_attempts_should_be_limited(self):
        email = Email(recipients=['undeliverable@aaa.com'])
        submission = self.client.sends_email(email)
        attempts_before_first_check = (MAX_DELIVERY_ATTEMPTS - 2)
        time.sleep(attempts_before_first_check * SMTPSTUB_RETRY_INTERVAL)
        self.client.observes_submission_status(submission, 'queued')
        attempts_before_second_check = (MAX_DELIVERY_ATTEMPTS + 1 - attempts_before_first_check)
        time.sleep(attempts_before_second_check * SMTPSTUB_RETRY_INTERVAL)
        self.client.observes_submission_status(submission, 'undeliverable')

class Client:
    # TODO: take it from an environment variable
    MINIMAILGUN_URL = 'http://127.0.0.1:5080'

    def observes_submission_status(self, submission, expected_status):
        r = self._access_minimailgun('/status', {'submission_id': submission.id})
        assert r == {'result': 'success', 'status': expected_status}, \
            "expected status '{}', actual response: {}".format(expected_status, r)

    def sends_email(self, email):
        r = self._access_minimailgun('/send', {
            'sender': email.sender,
            'recipients': email.recipients,
            'subject': 'end-to-end test',
            'body': 'the body of\n the message\n'
        })

        assert r['result'] == 'queued'
        return Submission(id=r['submission_id'])

    def _access_minimailgun(self, endpoint, request_data):
        request = urllib.request.Request(self.MINIMAILGUN_URL + endpoint,
                                         data=json.dumps(request_data).encode(),
                                         headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(request)
        assert response.getcode() == 200, \
            'Request to MiniMailGun returned status code {}, not 200'.format(response.getcode())

        data = response.read()
        return json.loads(data)


class SMTPServer:
    TIMEOUT = 5

    def __init__(self, domain):
        self.domain = domain

    def receives_email(self, expected_email):
        # TODO: enforce strict checks for mail from, recipients etc
        started_at = time.time()
        while True:
            with open(self.domain + '-smtp.log') as logfile:
                if (expected_email.sender + '\n') in logfile.readlines():
                    return

            assert (time.time() - started_at) <= self.TIMEOUT, \
                "Message from '{}' wasn't received within {} seconds by '{}'".format(
                    expected_email.sender, self.TIMEOUT, self.domain)

            time.sleep(0.1)


class Email:
    def __init__(self, recipients, sender=None):
        self._sender = sender or self._make_unique_address()
        self._recipients = recipients

    @classmethod
    def causing_server_to_tempfail_once(cls, recipients):
        return cls(recipients=recipients,
                   sender='tempfail-once-' + cls._make_unique_string() + '@e2e-test.com')

    @property
    def recipients(self):
        return self._recipients

    @property
    def sender(self):
        return self._sender

    @classmethod
    def _make_unique_address(cls):
        return cls._make_unique_string() + '@e2e-test.com'

    @staticmethod
    def _make_unique_string():
        return str(random.randint(0, 10**10))


if __name__ == '__main__':
    unittest.main()