# Certificate renewal

COM uses standalone Certbot validation. Its installed renewal pre-hook stops host Nginx and the post-hook restarts it. The Certbot timer drives renewal; inspect the timer, renewal configuration and hooks and run a controlled dry run when renewal verification is requested. An existing certificate makes the deployment issuance function return early, so rerunning deployment alone does not establish renewal.

CN uses an interactive manual DNS challenge for its domain and wildcard. Add each requested TXT value, wait for public resolution, then continue Certbot. Keep earlier values while the challenge still requires them. Without DNS automation, this manual certificate does not renew unattended. Existing files likewise cause the deployment issuance helper to return; use an explicit reviewed renewal command for the named certificate.

Retain the current domain, certificate name, DNS method and Nginx configuration. [Operations](operations.md) owns shared setup and recovery. Certificate changes apply only to the environment requested by the user.
