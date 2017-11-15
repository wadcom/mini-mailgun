import email
import inspect
import os
import queue
import sqlite3
import threading
import time


class Status:
    QUEUED = 'queued'
    SENT = 'sent'
    UNDELIVERABLE = 'undeliverable'


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

        status_column = "status TEXT CHECK({}) NOT NULL, ".format(' or '.join(
            'status="{}"'.format(v) for k, v in Status.__dict__.items() if not k.startswith('_'))
        )

        self._execute_committing(
            "CREATE TABLE IF NOT EXISTS envelopes ("
            "sender TEXT NOT NULL, "
            "recipients TEXT NOT NULL, "
            "destination_domain TEXT NOT NULL, "
            "message TEXT NOT NULL, "
            "next_attempt_at INTEGER NOT NULL, "
            + status_column +
            "submission_id TEXT NOT NULL, "
            "delivery_attempts INTEGER NOT NULL DEFAULT 0, "
            "being_processed BOOLEAN NOT NULL DEFAULT 0"
            ")"
        )

    def get(self):
        row = self._select_row_for_processing()
        return self._convert_row_to_envelope(row) if row else None

    def get_status(self, submission_id):
        self._db_cursor.execute(
            "SELECT rowid, * FROM envelopes WHERE submission_id=?", (submission_id,)
        )

        rows = self._db_cursor.fetchall()
        if not rows:
            return None

        return [(r['rowid'], r['status']) for r in rows]

    def mark_as_sent(self, envelope):
        self._set_envelope_status(envelope, Status.SENT)

    def mark_as_undeliverable(self, envelope):
        self._set_envelope_status(envelope, Status.UNDELIVERABLE)

    # TODO: split it into domain-specific methods, e.g. put_new_envelope() etc
    def put(self, envelope):
        self._execute_committing(
            'INSERT INTO envelopes '
            '(sender, recipients, destination_domain, message, next_attempt_at, submission_id, '
            'status) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (envelope.sender, ','.join(envelope.recipients), envelope.destination_domain,
             str(envelope.message), self.clock.time(), envelope.submission_id, envelope.status)
        )

        return self._db_cursor.lastrowid

    def schedule_retry_in(self, envelope, retry_after):
        self._assert_envelope_has_id(envelope)
        self._execute_committing(
            "UPDATE envelopes SET next_attempt_at=?, delivery_attempts=?, being_processed=0 "
            "WHERE rowid=?",
            (self.clock.time() + retry_after, envelope.delivery_attempts + 1, envelope.id)
        )

    @staticmethod
    def _assert_envelope_has_id(envelope):
        assert envelope.id, '{}: invalid envelope id "{}"'.format(envelope, envelope.id)

    @staticmethod
    def _convert_row_to_envelope(row):
        # TODO: test parsing recipients
        as_is = lambda x: x
        column_transformations = {
            'delivery_attempts': int,
            'destination_domain': as_is,
            'message': email.message_from_string,
            'next_attempt_at': int,
            'recipients': lambda x: x.split(','),
            'sender': as_is,
            'status': as_is,
            'submission_id': as_is
        }
        return Envelope(id=row['rowid'],
                        **{k: f(row[k]) for k, f in column_transformations.items()})

    def _execute_committing(self, statement, *extra_args):
        self._db_cursor.execute(statement, *extra_args)
        self._db_conn.commit()

    def _select_row_for_processing(self):
        self._db_cursor.execute(
            "SELECT rowid, * FROM envelopes "
            "WHERE next_attempt_at <= ? AND status='{}' AND being_processed=0 "
            "LIMIT 1".format(Status.QUEUED), (self.clock.time(),)
        )
        row = self._db_cursor.fetchone()

        if row:
            self._execute_committing("UPDATE envelopes SET being_processed=1 WHERE rowid=?",
                                     (row['rowid'],))
        return row

    def _set_envelope_status(self, envelope, status):
        self._assert_envelope_has_id(envelope)
        self._execute_committing(
            'UPDATE envelopes SET status="{}" WHERE rowid=?'.format(status), (envelope.id, ))


# TODO: rename it to SynchronizedMailQueue
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

        # XXX: factor out
        methods = [name for name, _ in inspect.getmembers(MailQueue, inspect.isfunction)
                   if not name.startswith('_')]

        for method in methods:
            assert method not in self.__class__.__dict__, \
                "name clash: method '{}' already exists in {}".format(method,
                                                                      self.__class__.__name__)
            self.__dict__[method] = self.ProxiedMethod(method, self._requests, self._responses)

    def start(self):
        self._manager_thread.start()

    def _main_loop(self):
        mq = MailQueue(**self._mail_queue_args)
        while True:
            method, args = self._requests.get()
            self._responses.put(getattr(mq, method)(*args))

    class ProxiedMethod:
        def __init__(self, method_name, request_queue, response_queue):
            self._method_name = method_name
            self._request_queue = request_queue
            self._response_queue = response_queue

        def __call__(self, *args, **kwargs):
            self._request_queue.put((self._method_name, args))
            return self._response_queue.get()
