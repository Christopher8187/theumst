#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
trap 'say "Certificate step failed."' ERR

if [ -z "${CERT_EMAIL:-}" ]; then
    CERT_EMAIL_ARGS="--register-unsafely-without-email"
else
    CERT_EMAIL_ARGS="-m $(umst_shell_quote "$CERT_EMAIL")"
fi

say "Creating or renewing certificate."
echo "Target: $REMOTE"
echo "Domain: $DOMAIN www.$DOMAIN"
echo "Certificate: $CERT_NAME"
echo "Mode: $CERT_MODE"
echo

if [ "$(printf '%s' "$CERT_MODE" | tr '[:upper:]' '[:lower:]')" = "manual" ]; then
    echo "Using manual DNS certificate mode."
    echo "Certbot will ask you to create DNS TXT records."
    echo
    ssh -tt -i "$KEY" "$REMOTE" "$SUDO certbot certonly --manual --preferred-challenges dns --keep-until-expiring --agree-tos $CERT_EMAIL_ARGS --cert-name $CERT_NAME -d $DOMAIN -d www.$DOMAIN && ($SUDO nginx -t && $SUDO systemctl reload nginx || true)"
else
    echo "Using automatic standalone HTTP certificate mode."
    echo "Nginx will stop briefly so Certbot can use port 80."
    echo
    ssh -tt -i "$KEY" "$REMOTE" "$SUDO systemctl stop nginx || true; $SUDO certbot certonly --standalone --preferred-challenges http --keep-until-expiring --non-interactive --agree-tos $CERT_EMAIL_ARGS --cert-name $CERT_NAME -d $DOMAIN -d www.$DOMAIN; code=\$?; $SUDO systemctl start nginx || true; if [ \$code -ne 0 ]; then exit \$code; fi; $SUDO nginx -t && $SUDO systemctl reload nginx || true"
fi

say "Certificate step finished."
umst_pause_if_requested
