#!/bin/bash
set -e
cd /opt/netbet/auth-service
export CERT_PASSWORD=$(grep '^CERT_PASSWORD=' .env | cut -d= -f2- | tr -d '\r\n' | sed 's/^"//;s/"$//')
cd certs
openssl pkcs12 -in client-2048.p12 -clcerts -nokeys -out client-2048.crt -passin pass:"$CERT_PASSWORD"
openssl pkcs12 -in client-2048.p12 -nocerts -nodes -out client-2048.key -passin pass:"$CERT_PASSWORD"
chmod 600 client-2048.crt client-2048.key
ls -la client-2048.crt client-2048.key
