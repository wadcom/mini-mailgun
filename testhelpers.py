import email

import mailqueue

def make_valid_envelope():
    return mailqueue.Envelope(recipients=['alice@target.domain', 'bob@target.domain'],
                              destination_domain='target.domain',
                              message=make_valid_email(),
                              submission_id='a-submission-id',
                              status=mailqueue.Status.QUEUED,
                              delivery_attempts=1,
                              client_id='testhelpers_client_id'
                              )


def make_valid_email():
    message = email.message.EmailMessage()
    message['From'] = 'me@example.com'
    message['To'] = 'you@example.com'
    message['Subject'] = 'valid email'
    message.set_content('indeed!')
    return message
