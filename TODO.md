# TODO / Backlog

 * Validate input in `/send`

 * Use retention policy for delivery attempts
   * Remove status data after X hours after last update

 * Authenticate clients
   * Clients should not be able to query other clients' submission status

 * Try delivering to all MX records for a domain, not only to the top priority one

 * Make `sender` multi-threaded
