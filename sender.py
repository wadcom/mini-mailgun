#! /usr/bin/env python3

import smtplib
import time

import mailqueue


def main():
    # TODO: this is a prototype and should be reworked

    mq = mailqueue.MailQueue()
    while True:
        q_item = mq.get()
        if q_item:
            # TODO: take hostname and port from configuration
            server = smtplib.SMTP(host='smtpstub', port=5000)
            server.send_message(q_item.as_email())
            server.quit()

            # TODO: handle errors
            mq.mark_as_sent(q_item)
        else:
            time.sleep(1)


if __name__ == '__main__':
    main()