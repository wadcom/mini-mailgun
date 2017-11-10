import collections
import email
import os
import sqlite3


Envelope = collections.namedtuple('Envelope', 'sender recipients destination_domain message')


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


class MailQueue:

    DB_FILE = '/mailq/messages.db'

    def __init__(self, fresh=False):
        if fresh:
            try:
                os.remove(self.DB_FILE)
            except FileNotFoundError:
                pass

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

    def put(self, envelope):
        self._execute_committing('INSERT INTO messages VALUES (?)', (str(envelope.message),))

    def _execute_committing(self, statement, *extra_args):
        self._db_cursor.execute(statement, *extra_args)
        self._db_conn.commit()

