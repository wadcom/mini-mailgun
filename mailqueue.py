import email
import os
import queue
import sqlite3
import threading
import time


class Envelope:
    def __init__(self, **kwargs):
        self.id = None
        self.__dict__.update(kwargs)

    def __str__(self):
        return 'Envelope({})'.format(
            ', '.join([k + '=' + repr(v) for k, v in sorted(self.__dict__.items())]))


class MailQueue:

    DB_FILE = '/mailq/messages.db'

    def __init__(self, fresh=False):
        if fresh:
            try:
                os.remove(self.DB_FILE)
            except FileNotFoundError:
                pass

        self.clock = time

        self._db_conn = sqlite3.connect(self.DB_FILE)
        self._db_conn.row_factory = sqlite3.Row
        self._db_cursor = self._db_conn.cursor()

        self._execute_committing(
            "CREATE TABLE IF NOT EXISTS envelopes ("
            "sender TEXT, "
            "recipients TEXT, "
            "destination_domain TEXT, "
            "message TEXT, "
            "next_attempt_at INTEGER DEFAULT (strftime('%s', CURRENT_TIMESTAMP))"
            ")"
        )

    def get(self):
        self._db_cursor.execute(
            "SELECT rowid, * FROM envelopes "
            "WHERE next_attempt_at <= ? LIMIT 1",
            (self.clock.time(),)
        )
        row = self._db_cursor.fetchone()

        if not row:
            return None

        # TODO: test parsing recipients
        return Envelope(sender=row['sender'], recipients=row['recipients'].split(','),
                        destination_domain=row['destination_domain'],
                        message=email.message_from_string(row['message']), id=row['rowid'],
                        next_attempt_at=int(row['next_attempt_at']))

    def mark_as_sent(self, envelope):
        self._assert_envelope_has_id(envelope)
        self._execute_committing('DELETE FROM envelopes WHERE rowid=?', (envelope.id, ))

    def put(self, envelope):
        self._execute_committing(
            'INSERT INTO envelopes '
            '(sender, recipients, destination_domain, message, next_attempt_at) '
            'VALUES (?, ?, ?, ?, ?)',
            (envelope.sender, ','.join(envelope.recipients), envelope.destination_domain,
             str(envelope.message), self.clock.time())
        )

    def schedule_retry_in(self, envelope, retry_after):
        self._assert_envelope_has_id(envelope)
        self._execute_committing(
            "UPDATE envelopes SET next_attempt_at=? WHERE rowid=?",
            (self.clock.time() + retry_after, envelope.id)
        )

    @staticmethod
    def _assert_envelope_has_id(envelope):
        assert envelope.id, '{}: invalid envelope id "{}"'.format(envelope, envelope.id)

    def _execute_committing(self, statement, *extra_args):
        self._db_cursor.execute(statement, *extra_args)
        self._db_conn.commit()


class Manager:
    """A proxy synchronizing access to MailQueue from multiple threads.

    SQLite requires that the thread creating the database object is
    the only one using it. This manager synchronizes access to methods
    of MailQueue via blocking queues.
    """

    def __init__(self, **kwargs):
        self._mail_queue_args = kwargs
        self._manager_thread = threading.Thread(target=self._main_loop)
        self._requests = queue.Queue(1)
        self._responses = queue.Queue(1)

    def put(self, *args):
        self._requests.put(('put', args))
        return self._responses.get()

    def start(self):
        self._manager_thread.start()

    def _main_loop(self):
        mq = MailQueue(**self._mail_queue_args)
        while True:
            method, args = self._requests.get()
            self._responses.put(getattr(mq, method)(*args))
