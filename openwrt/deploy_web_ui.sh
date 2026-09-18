#!/bin/sh
set -eu

BASE="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/www/datbeo"
mkdir -p /www/datbeo

wget -qO /www/datbeo/index.html "$BASE/index.html"
wget -qO /www/datbeo/style.css "$BASE/style.css"
wget -qO /www/datbeo/app.js "$BASE/app.js"

chmod 0644 /www/datbeo/index.html /www/datbeo/style.css /www/datbeo/app.js

echo "DatBeo Web UI installed at http://$(ip -4 addr show wt0 2>/dev/null | awk '/inet /{sub(/\/.*,""$2);print $2;exit}')/datbeo/"
