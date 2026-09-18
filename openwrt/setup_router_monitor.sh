#!/bin/sh
set -e

echo "== DatBeo Router Monitor: 24h DNS + traffic setup =="

apk update
apk add nlbwmon uhttpd dnsmasq

mkdir -p /etc/datbeo-router-monitor /www/cgi-bin /tmp/nlbwmon

if [ ! -f /etc/datbeo-router-monitor/api_key ]; then
    umask 077
    hexdump -n 32 -e '8/4 "%08x"' /dev/urandom > /etc/datbeo-router-monitor/api_key
fi
chmod 600 /etc/datbeo-router-monitor/api_key

uci set nlbwmon.@nlbwmon[0].database_directory='/tmp/nlbwmon'
uci set nlbwmon.@nlbwmon[0].database_generations='1'
uci set nlbwmon.@nlbwmon[0].commit_interval='1h'
uci set nlbwmon.@nlbwmon[0].refresh_interval='30s'
uci set nlbwmon.@nlbwmon[0].database_limit='10000'
uci commit nlbwmon

# dnsmasq logs queries to RAM. OpenWrt maps logqueries=1 to --log-queries=extra,
# which includes the requesting client IP in current OpenWrt dnsmasq builds.
uci set dhcp.@dnsmasq[0].logqueries='1'
uci set dhcp.@dnsmasq[0].logfacility='/tmp/datbeo-dns.log'
uci commit dhcp

# Clear DNS query history every day; /tmp is RAM and is lost on reboot.
mkdir -p /etc/crontabs
grep -v 'datbeo-dns' /etc/crontabs/root 2>/dev/null > /tmp/datbeo-cron 2>/dev/null || true
echo '5 0 * * * : > /tmp/datbeo-dns.log' >> /tmp/datbeo-cron
mv /tmp/datbeo-cron /etc/crontabs/root

/etc/init.d/nlbwmon enable
/etc/init.d/nlbwmon restart
/etc/init.d/dnsmasq restart
/etc/init.d/cron enable 2>/dev/null || true
/etc/init.d/cron restart 2>/dev/null || true
/etc/init.d/uhttpd enable
/etc/init.d/uhttpd restart

echo
echo "Router : $(uci -q get system.@system[0].hostname || hostname)"
echo "NetBird: $(ip -4 addr show wt0 2>/dev/null | awk '/inet / {sub(/\/.*/, "", $2); print $2; exit}')"
echo "LAN    : 10.1.1.0/24"
echo "API key:"
cat /etc/datbeo-router-monitor/api_key
echo
echo "DNS log: /tmp/datbeo-dns.log"
echo "History is kept in RAM and cleared daily at 00:05."
