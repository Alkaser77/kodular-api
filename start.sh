#!/bin/bash
sshpass -p "$SSH_PASS" autossh -M 0 -N -D 1080 -p 443 $SSH_USER@$SSH_HOST -o "ProxyCommand socat - OPENSSL:$SSH_HOST:443,snihost=m.facebook.com,verify=0" -o "UserKnownHostsFile=/dev/null" -o "StrictHostKeyChecking=no" -o "ServerAliveInterval=30"
