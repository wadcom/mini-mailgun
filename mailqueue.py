import email
import os
import sqlite3
import unittest

class Item:
    def __init__(self, id, message_text):
        self._id = id
        self._message_text = message_text

    def as_email(self):
        return email.message_from_string(self._message_text)

    @property
    def id(self):
        return self._id

    @property
    def message_text(self):
        return self._message_text


class TestItem(unittest.TestCase):
    def test_deserializing_should_produce_email_message(self):
        item = Item(id=1, message_text='From: a\n\n')
        message = item.as_email()
        self.assertEqual('a', message['From'])

###################################################################################################

class MailQueue:

    DB_FILE = '/mailq/messages.db'

    def __init__(self, fresh=False):
        if fresh:
            os.remove(self.DB_FILE)

        self._db_conn = sqlite3.connect(self.DB_FILE)
        self._db_conn.row_factory = sqlite3.Row
        self._db_cursor = self._db_conn.cursor()

        self._execute_committing('CREATE TABLE IF NOT EXISTS messages (message text)')

    def get(self):
        self._db_cursor.execute('SELECT rowid, * FROM messages LIMIT 1')
        row = self._db_cursor.fetchone()
        return Item(id=row['rowid'], message_text=row['message']) if row else None

    def mark_as_sent(self, item):
        self._execute_committing('DELETE FROM messages WHERE rowid=?', (item.id, ))

    def put(self, message):
        self._execute_committing('INSERT INTO messages VALUES (?)', (str(message),))

    def _execute_committing(self, statement, *extra_args):
        self._db_cursor.execute(statement, *extra_args)
        self._db_conn.commit()


class TestMailQueue(unittest.TestCase):
    def test_roundtrip(self):
        message = 'something'
        mq = MailQueue(fresh=True)
        mq.put(message)

        expected = Item(id=1, message_text=message)
        self.assertItemsEqual(expected, mq.get())

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

        self.assertEqual(message, MailQueue().get().message_text)

    def test_message_marked_as_sent_should_not_be_retrieved(self):
        mq = MailQueue(fresh=True)
        mq.put('something')
        item = mq.get()
        mq.mark_as_sent(item)

        self.assertIsNone(mq.get())

    def assertItemsEqual(self, expected_item, actual_item):
        self.assertEqual(expected_item.id, actual_item.id)
        self.assertEqual(expected_item.message_text, actual_item.message_text)
