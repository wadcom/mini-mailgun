import os
import sqlite3
import unittest

class MailQueue:

    DB_FILE = '/mailq/messages.db'

    def __init__(self, fresh=False):
        if fresh:
            os.remove(self.DB_FILE)

        self._db_conn = sqlite3.connect(self.DB_FILE)
        self._db_conn.row_factory = sqlite3.Row
        self._db_cursor = self._db_conn.cursor()

        self._db_cursor.execute(
            'CREATE TABLE IF NOT EXISTS messages (sender text, recipients text, body text)')
        self._db_conn.commit()

    def get(self):
        self._db_cursor.execute('SELECT * FROM messages LIMIT 1')
        row = self._db_cursor.fetchone()
        return row['body'] if row else None

    def put(self, message):
        self._db_cursor.execute('INSERT INTO messages VALUES (?, ?, ?)',
                                ('XXX-sender', 'XXX-recipients', message))
        self._db_conn.commit()


class TestMailQueue(unittest.TestCase):
    def test_roundtrip(self):
        message = 'something'
        mq = MailQueue()
        mq.put(message)
        self.assertEqual(message, mq.get())

    def test_empty_queue_should_return_none_on_get(self):
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_mailqueue_with_fresh_should_drop_database(self):
        mq = MailQueue(fresh=True)
        mq.put('unused')
        self.assertIsNone(MailQueue(fresh=True).get())

    def test_messages_should_be_persisted(self):
        message = 'something'
        mq = MailQueue(fresh=True)
        mq.put(message)

        self.assertEqual(message, MailQueue().get())
