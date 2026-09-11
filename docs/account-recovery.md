# Account recovery

The public login page links to password recovery. A user supplies their email, receives a reset link, chooses a new password and signs in again. The request returns a neutral accepted response to avoid revealing whether an account exists. Reset tokens are hashed in PostgreSQL, expire, work once and revoke existing sessions when successfully used.

Configure `PUBLIC_WEBPAGE_URL`, `PASSWORD_RESET_TTL_MINUTES` and SMTP host, port, username, password, sender address/name and TLS mode in the selected environment. STARTTLS commonly uses port 587; implicit TLS commonly uses 465. Use the provider's actual settings. The code lives in `routers/auth.py`, `services/email.py` and `app/security.py`.

SMTP acceptance is distinct from inbox delivery. Test request/reset behavior locally with a controlled mailbox or transport before an explicitly requested real email. Existing historical COM observations do not establish current delivery.

Email verification and email-change confirmation use separate token flows. Read the [backend tests](../backend/python/tests/README.md) for token reuse, expiry, claim and session checks, and [security](security.md) for authentication boundaries.

Reset, signup confirmation, email-change confirmation and News use one warm-ivory table layout with a transparent PNG logo and matching plain text. Account messages add Date and Message-ID and show the configured `PASSWORD_RESET_TTL_MINUTES` or `EMAIL_VERIFICATION_TTL_HOURS`, rather than fixed design-sample expiry text. Email change has distinct copy about confirming the new address while the current address remains active. These security messages remain separate from optional [News subscriptions](news-subscriptions.md) and contain no newsletter unsubscribe action.
