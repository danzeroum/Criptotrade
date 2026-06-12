#!/bin/sh
# One-time Let's Encrypt bootstrap for criptotrade.buildtovalue.cloud.
#
# nginx will not start without a certificate to load, but the certificate is
# obtained via an HTTP-01 challenge that nginx itself must serve — a chicken/egg
# problem. This script breaks it: create a throwaway self-signed cert so nginx
# can boot, request the real cert through the webroot challenge, then reload.
#
# Run ONCE on the host (with DNS for the domain already pointing here and ports
# 80/443 reachable) BEFORE the first `docker compose -f docker-compose.prod.yml up -d`.
# Adapted from https://github.com/wmnnd/nginx-certbot (MIT).
set -e

domain="criptotrade.buildtovalue.cloud"
email="danniellau@gmail.com"     # Let's Encrypt expiry/security notices
data_path="./data/certbot"
rsa_key_size=4096
staging=0                         # set to 1 to test against the LE staging CA

compose="docker compose -f docker-compose.prod.yml"
live_path="/etc/letsencrypt/live/$domain"

if [ -d "$data_path/conf/live/$domain" ]; then
  printf "Existing certificate found for %s. Replace it? (y/N) " "$domain"
  read decision
  case "$decision" in [Yy]*) ;; *) echo "Aborted."; exit 0 ;; esac
fi

echo "### Creating a dummy certificate so nginx can start ..."
mkdir -p "$data_path/conf" "$data_path/www" "$data_path/conf/live/$domain"
$compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1 \
    -keyout '$live_path/privkey.pem' \
    -out '$live_path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo "### Starting nginx ..."
$compose up --force-recreate -d nginx

echo "### Deleting the dummy certificate ..."
$compose run --rm --entrypoint "\
  rm -rf /etc/letsencrypt/live/$domain \
         /etc/letsencrypt/archive/$domain \
         /etc/letsencrypt/renewal/$domain.conf" certbot

echo "### Requesting the real Let's Encrypt certificate for $domain ..."
if [ "$staging" != "0" ]; then staging_arg="--staging"; else staging_arg=""; fi
$compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email $email \
    -d $domain \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --no-eff-email \
    --force-renewal" certbot

echo "### Reloading nginx with the real certificate ..."
$compose exec nginx nginx -s reload

echo "### Done. https://$domain should now serve a valid certificate."
echo "### Bring up the full stack with: $compose up -d"
