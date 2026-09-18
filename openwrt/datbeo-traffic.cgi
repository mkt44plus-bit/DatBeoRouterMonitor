#!/bin/sh

API_FILE="/etc/datbeo-router-monitor/api_key"
KEY="$(cat "$API_FILE" 2>/dev/null)"
REQ="$(printf '%s' "$HTTP_X_API_KEY")"

if [ -z "$REQ" ] && [ -n "$QUERY_STRING" ]; then
    REQ="$(printf '%s' "$QUERY_STRING" | sed -n 's/^.*\(^\|&\)key=\([^&]*\).*$/\2/p')"
    [ -n "$REQ" ] || REQ="$(printf '%s' "$QUERY_STRING" | sed -n 's/^key=\([^&]*\).*$/\1/p')"
fi

printf 'Content-Type: application/json\r\n\r\n'

if [ -z "$KEY" ] || [ "$REQ" != "$KEY" ]; then
    printf '{"error":"unauthorized"}\n'
    exit 0
fi

HOSTNAME="$(uci -q get system.@system[0].hostname)"
[ -n "$HOSTNAME" ] || HOSTNAME="$(hostname)"

NETBIRD_IP="$(ip -4 addr show wt0 2>/dev/null | awk '/inet / {sub(/\/.*/, "", $2); print $2; exit}')"

TRAFFIC=""

if command -v nlbw >/dev/null 2>&1; then
    CSV="$(nlbw -c csv -g mac -o mac -q 2>/dev/null || true)"
    TRAFFIC="$(printf '%s\n' "$CSV" | awk '
        NR == 1 { next }
        NF >= 6 {
            if (!first) printf ","
            first=0
            printf "{\"mac\":\"%s\",\"conns\":%s,\"rx_bytes\":%s,\"rx_pkts\":%s,\"tx_bytes\":%s,\"tx_pkts\":%s}", $1,$2,$3,$4,$5,$6
        }
    ')"
fi
[ -n "$TRAFFIC" ] || TRAFFIC=""

printf '{"hostname":"%s","netbird_ip":"%s","lan":"10.1.1.0/24","traffic":[%s],"leases":['     "$HOSTNAME" "$NETBIRD_IP" "$TRAFFIC"

first=1
if [ -f /tmp/dhcp.leases ]; then
    while read -r EXP MAC IP NAME _; do
        [ -n "$MAC" ] || continue
        [ "$first" -eq 1 ] || printf ","
        first=0
        printf '{"mac":"%s","ip":"%s","name":"%s","expiry":"%s"}' "$MAC" "$IP" "$NAME" "$EXP"
    done < /tmp/dhcp.leases
fi

printf '],"websites":['

first=1
if [ -f /tmp/datbeo-dns.log ]; then
    tail -n 300 /tmp/datbeo-dns.log 2>/dev/null |
    sed -n 's/^\([^ ]* [^ ]* [^ ]*\).* query[^ ]* \([^ ]*\) from \([^ ]*\).*$/\1|\2|\3/p' |
    while IFS='|' read -r TM DOMAIN SRCIP; do
        [ -n "$DOMAIN" ] || continue
        case "$DOMAIN" in
            localhost|local|*in-addr.arpa|*ip6.arpa) continue ;;
        esac
        [ "$first" -eq 1 ] || printf ","
        first=0
        printf '{"time":"%s","domain":"%s","ip":"%s"}' "$TM" "$DOMAIN" "$SRCIP"
    done
fi

printf ']}\n'
