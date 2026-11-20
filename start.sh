#!/bin/bash
python3 -m http.server $PORT &

cat > /tmp/vpn.exp <<'EOF'
#!/usr/bin/expect -f
set timeout -1
spawn autossh -M 0 -N -D 1080 -p 443 col@51.38.224.165 -o ProxyCommand "socat - OPENSSL:51.38.224.165:443,snihost=m.facebook.com,verify=0" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30
expect "password:"
send "$env(SSH_PASS)\r"
interact
EOF

chmod +x /tmp/vpn.exp
exec expect /tmp/vpn.exp
