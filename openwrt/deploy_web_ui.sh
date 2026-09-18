#!/bin/sh
set -eu

BASE="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/www/datbeo"
CGI="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/datbeo-traffic.cgi"
CAM="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/datbeo-cameras.cgi"
mkdir -p /www/datbeo /www/datbeo/camera-stream /etc/datbeo-router-monitor

if command -v apk >/dev/null 2>&1; then
  apk -U add ffmpeg ffprobe netcat >/dev/null 2>&1 || echo "WARN: ffmpeg/ffprobe/netcat not installed; camera test/live view/scan will be unavailable."
fi

wget -qO /www/datbeo/index.html "$BASE/index.html"
wget -qO /www/datbeo/style.css "$BASE/style.css"
wget -qO /www/datbeo/app.js "$BASE/app.js"
wget -qO /www/datbeo/logo.svg "$BASE/logo.svg"
wget -qO /www/datbeo/hls.min.js "https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js" || echo "WARN: không tải được hls.js; native HLS fallback sẽ được dùng."
wget -qO /www/cgi-bin/datbeo-traffic "$CGI"
wget -qO /www/cgi-bin/datbeo-cameras "$CAM"

chmod 0644 /www/datbeo/index.html /www/datbeo/style.css /www/datbeo/app.js /www/datbeo/hls.min.js /www/datbeo/logo.svg
chmod 0755 /www/cgi-bin/datbeo-traffic /www/cgi-bin/datbeo-cameras

IP="$(ip -4 addr show wt0 2>/dev/null | awk '/inet / {sub("/.*", "", $2); print $2; exit}')"
echo "DatBeo Web UI installed: http://${IP:-100.81.163.26}/datbeo/"
echo "Camera RTSP support: $([ -x "$(command -v ffmpeg 2>/dev/null || true)" ] && echo ready || echo not-ready)"
