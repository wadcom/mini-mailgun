#! /usr/bin/env python3

import logging
import os
import time

import mailqueue


def main():
    cleanup_interval = int(os.environ.get('CLEANUP_INTERVAL', '300'))

    # Cleanup implemented here is per-envelope, not per-submission. So it is possible that
    # after the retention period the status of a submission might become invalid (e.g. if we've
    # cleaned up one of the envelopes belonging to the submission, but there is another one still
    # there).
    #
    # Making it always correct is slightly more complicated, so I consider this to be good enough
    # for now.
    #
    # Because of the above we should set the retention period here to a higher value than what is
    # communicated to customers (thus the factor of '2' below).
    retention_period = int(os.environ.get('RETENTION_PERIOD', str(2 * 3 * 3600)))

    setup_logging()

    mq = mailqueue.MailQueue()
    while True:
        removed = mq.remove_inactive_envelopes(retention_period)
        logging.info('Removed {} inactive envelopes'.format(removed))
        time.sleep(cleanup_interval)


def setup_logging():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s %(message)s',
                        datefmt='%x %X',
                        level=logging.DEBUG)
    logging.info('Starting up...')


if __name__ == '__main__':
    main()
