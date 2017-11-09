# TODO / Backlog

 * Validate input in `/send`

 * Ensure proper support for multiple recipients in `/send`

 * Implement retries when delivering a message

 * Add an endpoint to query message status
   * Status: Delivered / In Queue / Dropped
   * Last delivery attempt: timestamp, status
   * Next delivery attempt: "not earlier than at <timestamp>"

 * Use retention policy for delivery attempts
   * Remove status data after X hours after last update

 * Use exponential backoff for redeliveries
   * 1 initial attempt + 3 retries
   * Don't keep message in the system for more than 30 minutes

 * Route messages to upstream SMTP servers based on configuration

 * Route messages to upstream SMTP servers per DNS MX records
