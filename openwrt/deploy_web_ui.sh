#!/bin/sh
set -eu

BASE="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/www/datbeo"
CGI="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/datbeo-traffic.cgi"
CAM="https://raw.githubusercontent.com/mkt44plus-bit/DatBeoRouterMonitor/main/openwrt/datbeo-cameras.cgi"
mkdir -p /www/datbeo /www/datbeo/camera-stream /etc/datbeo-router-monitor

if command -v apk >/dev/null 2>&1; then
  apk -U add ffmpeg ffprobe libffmpeg-full netcat >/dev/null 2>&1 || echo "WARN: ffmpeg/ffprobe/netcat not installed; camera test/live view/scan will be unavailable."

  # OpenWrt's stock FFmpeg disables patented native HEVC/H.265 decoding.
  # DatBeo publishes a matching ARMv7 build with software HEVC enabled.
  # Install it only when the stock binary does not expose the software decoder.
  if command -v ffmpeg >/dev/null 2>&1 && ! ffmpeg -hide_banner -decoders 2>/dev/null | grep -qE '^[[:space:]]*V.*[[:space:]]hevc[[:space:]]'; then
    HEVC_URL="https://github.com/mkt44plus-bit/DatBeoRouterMonitor/releases/download/ffmpeg-hevc-armv7/ffmpeg-hevc-armv7.tar.gz"
    TMP_HEVC="/tmp/datbeo-ffmpeg-hevc.tar.gz"
    TMP_HEVC_DIR="/tmp/datbeo-ffmpeg-hevc"
    rm -rf "$TMP_HEVC_DIR"
    mkdir -p "$TMP_HEVC_DIR"
    if wget -qO "$TMP_HEVC" "$HEVC_URL"; then
      tar -xzf "$TMP_HEVC" -C "$TMP_HEVC_DIR"
      if ls "$TMP_HEVC_DIR"/ffmpeg-*.apk "$TMP_HEVC_DIR"/ffprobe-*.apk "$TMP_HEVC_DIR"/libffmpeg-full-*.apk >/dev/null 2>&1; then
        apk del ffmpeg ffprobe libffmpeg-full >/dev/null 2>&1 || true
        if apk add --allow-untrusted "$TMP_HEVC_DIR"/libffmpeg-full-*.apk "$TMP_HEVC_DIR"/ffmpeg-*.apk "$TMP_HEVC_DIR"/ffprobe-*.apk >/dev/null 2>&1 &&
           ffmpeg -hide_banner -decoders 2>/dev/null | grep -qE '^[[:space:]]*V.*[[:space:]]hevc[[:space:]]'; then
          echo "DatBeo FFmpeg: software HEVC ready"
        else
          echo "WARN: custom HEVC FFmpeg install failed; restoring OpenWrt FFmpeg."
          apk add ffmpeg ffprobe libffmpeg-full >/dev/null 2>&1 || true
        fi
      fi
    else
      echo "WARN: custom HEVC FFmpeg release not available yet; keeping OpenWrt FFmpeg."
    fi
    rm -rf "$TMP_HEVC_DIR" "$TMP_HEVC"
  fi
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
