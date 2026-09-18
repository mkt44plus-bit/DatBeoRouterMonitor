#!/bin/sh
API_FILE="/etc/datbeo-router-monitor/api_key"
KEY="$(cat "$API_FILE" 2>/dev/null)"
REQ="$(printf '%s' "$HTTP_X_API_KEY")"

printf 'Content-Type: application/json\r\n\r\n'
if [ -z "$KEY" ] || [ "$REQ" != "$KEY" ]; then
    printf '{"error":"unauthorized"}\n'
    exit 0
fi

HOSTNAME="$(uci -q get system.@system[0].hostname)"
[ -n "$HOSTNAME" ] || HOSTNAME="$(hostname)"
NETBIRD_IP="$(ip -4 addr show wt0 2>/dev/null | awk '/inet / {sub(/\/.*/, "", $2); print $2; exit}')"

TRAFFIC="[]"
if command -v nlbw >/dev/null 2>&1; then
    TRAFFIC="$(nlbw -c csv -g mac -o mac -q 2>/dev/null | awk '
        NR == 1 { next }
        NF >= 6 {
            if (!first) printf(",")
            first=0
            printf("{\"mac\":\"%s\",\"conns\":%s,\"rx_bytes\":%s,\"rx_pkts\":%s,\"tx_bytes\":%s,\"tx_pkts\":%s}", $1,$2,$3,$4,$5,$6)
        }
    ')"
    [ -n "$TRAFFIC" ] || TRAFFIC="[]"
fi

printf '{"hostname":"%s","netbird_ip":"%s","lan":"10.1.1.0/24","traffic":[%s],"leases":[' "$HOSTNAME" "$NETBIRD_IP" "$TRAFFIC"

first=1
if [ -f /tmp/dhcp.leases ]; then
    while read -r EXP MAC IP NAME _; do
        [ -n "$MAC" ] || continue
        [ "$first" -eq 1 ] || printf ','
        first=0
        printf '{"mac":"%s","ip":"%s","name":"%s","expiry":"%s"}' "$MAC" "$IP" "$NAME" "$EXP"
    done < /tmp/dhcp.leases
fi
printf ']}\n'
