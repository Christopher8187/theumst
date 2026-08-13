# theumst account recovery and team update

## Production status

SMTP account recovery was deployed to `https://theumst.com` on 12 August 2026.
The live recovery endpoint returned HTTP 202, and the server recorded the
message as accepted by the configured mail provider. The request and reset
pages were also checked in the live browser. Inbox placement is controlled by
the mail provider, so check the recipient's inbox and spam folder for the test
message titled **Reset your theumst password**. The test link expires after 60
minutes and can be ignored if no password change is wanted.

## What changed

- Tina now appears on the public About page as **Social Media Advisor**.
- Her previously committed team photo was restored from Git history with the
  project owner's explicit approval. Her repository-backed NYU/NYU Tandon CSSA
  biography was also restored with explicit approval.
- The login page now links to **Forgot your password?**.
- A user can enter their account email and receive a secure reset link.
- Reset links expire after 60 minutes by default, work once, and are stored only
  as hashes. Successful resets sign out all existing sessions.
- The request response is deliberately the same for matching and non-matching
  email addresses, which prevents account discovery.

## Configure outbound email

Password recovery needs an SMTP account. Add these values to the repository's
`.env` file; do not commit that file:

```dotenv
PUBLIC_WEBPAGE_URL=https://theumst.com
PASSWORD_RESET_TTL_MINUTES=60
SMTP_HOST=smtp.your-provider.example
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=accounts@theumst.com
SMTP_FROM_NAME=theumst
SMTP_STARTTLS=true
SMTP_USE_SSL=false
```

For implicit TLS, providers normally use port 465 with `SMTP_USE_SSL=true`.
For STARTTLS, providers normally use port 587 with `SMTP_STARTTLS=true`.

## User flow

1. Open `/login` and select **Forgot your password?**.
2. Enter the email address attached to the account.
3. Open the email and select **Choose a new password**.
4. Enter and confirm a password of at least eight characters.
5. Return to login and use the new password.

## Updating Tina's profile

The team details live in
`frontend/webpage/src/utils/language.js`; the member card is registered in
`frontend/webpage/src/pages/AboutPage.vue`. To replace the initials portrait,
put an approved image in `backend/assets/images` and add its filename to
Tina's member entry. Obtain Tina's approval before publishing a photo
or additional biographical claims.
