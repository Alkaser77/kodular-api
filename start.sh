#!/bin/bash
python3 -m http.server $PORT &

export SSHPASS="$SSH_PASS"

exec sshpass -e autossh -M 0 -N -D 1080 -p 443 col@51.38.224.165 \
  -o "ProxyCommand=socat - OPENSSL:51.38.224.165:443,snihost=m.facebook.com,verify=0" \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o ServerAliveInterval=30 \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no
