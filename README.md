# ![alt text](https://rmon.io/static/images/logo/orange_640.png "Logo")
RMON (remote monitoring) is an easy to understand and use geo-distributed monitoring.

# Get involved
* [Telegram Channel](https://t.me/roxy_wi_channel) about RMON, talks and questions are welcome

![alt text](https://rmon.io/static//images/rmon_history_dashboard.png "RMON check history")

# Features:
1. Checking ping availability
2. Checking DNS records availability
3. Checking the availability of TCP and UDP ports
4. Checking HTTP statuses
5. Checking the BODY of HTTP(s) responses
6. Checking the SSL expiration date
7. Checking SMTP service
8. Checking RabbitMQ service
9. Sending Telegram, Slack, PagerDuty and Email notifications
10. Real-time alerting via RMON web interface
11. Checking network connectivity
12. Providing information upon response time
13. Providing information upon servers uptime and downtime
14. Storing the alarm history
15. Storing the history of events for each host
16. Status pages
17. RMON Agents 
18. Network tools

# Install

For installation on EL and Ubuntu read this [guide](https://rmon.io/installation)

## Security configuration

RMON no longer ships reusable application or credential-encryption secrets. Set these values in the service environment before starting RMON:

- `RMON_SECRET_KEY`: a random value of at least 32 characters for Flask sessions.
- `RMON_SECRET_PHRASE`: a Fernet key for stored SSH passwords, passphrases, and private keys. Generate one with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- `RMON_JWT_PRIVATE_KEY_FILE` and `RMON_JWT_PUBLIC_KEY_FILE`: optional overrides for the default JWT key paths in `/var/lib/rmon/keys`.

The Flask secret may instead be stored in `RMON_SECRET_KEY_FILE`; when neither setting exists, RMON creates `/var/lib/rmon/keys/flask-secret` with mode `0600`. The scheduler itself remains enabled by default, but its unauthenticated REST API is disabled. Set `RMON_SCHEDULER_ENABLED=0` when a separate scheduler process is used.

To rotate an existing credential key, back up the database and run `rotate_credential_secret.py` with both `RMON_OLD_SECRET_PHRASE` and the new `RMON_SECRET_PHRASE` in the environment. The update is transactional and can safely skip values that were already rotated.

![alt text](https://rmon.io/static//images/rmon_checks.png "RMON checks")
