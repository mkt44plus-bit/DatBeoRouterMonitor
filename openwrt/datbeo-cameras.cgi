#!/bin/sh
DB="/etc/datbeo-router-monitor/cameras.db"
mkdir -p /etc/datbeo-router-monitor
[ -f "$DB" ] || : > "$DB"
chmod 600 "$DB"

json_escape(){ printf "%s" "$1" | sed 's/\\/\\\\/g; s/"/\\\"/g'; }
dec(){ printf "%b" "$(printf "%s" "$1" | sed 's/+/ /g; s/%/\\x/g')"; }

param(){ printf "%s" "$2" | tr "&" "\n" | sed -n "s/^$1=//p" | head -n1; }

API_FILE="/etc/datbeo-router-monitor/api_key"
API_KEY="$(cat "$API_FILE" 2>/dev/null || true)"
REQ_KEY="${HTTP_X_API_KEY:-}"
case "$REQ_KEY" in "") REQ_KEY="$(printf "%s" "$QUERY_STRING" | tr "&" "\n" | sed -n "s/^key=//p" | head -n1)";; esac
printf "Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n"
if [ -z "$API_KEY" ] || [ "$REQ_KEY" != "$API_KEY" ]; then
  printf '{ "ok": false, "error": "unauthorized" }\n'
  exit
fi
BODY=""
[ "${CONTENT_LENGTH:-0}" -gt 0 ] 2>/dev/null && BODY="$(dd bs=1 count="$CONTENT_LENGTH" 2>/dev/null)"
[ -n "$BODY" ] || BODY="$QUERY_STRING"
ACTION="$(param action "$BODY")"
ID="$(param id "$BODY")"

CAM_SECTION=""
CAM_NAME=""
CAM_IP=""
CAM_PORT="554"
CAM_PATH=""
CAM_USER=""
CAM_PASS=""

load_camera(){
  i=0
  while ID0="$(uci -q get datbeo_camera.@camera[$i].id 2>/dev/null)"; do
    if [ "$ID0" = "$ID" ]; then
      CAM_SECTION="@camera[$i]"
      CAM_NAME="$(uci -q get datbeo_camera.@camera[$i].name 2>/dev/null || true)"
      CAM_IP="$(uci -q get datbeo_camera.@camera[$i].ip 2>/dev/null || true)"
      CAM_PORT="$(uci -q get datbeo_camera.@camera[$i].port 2>/dev/null || echo 554)"
      CAM_PATH="$(uci -q get datbeo_camera.@camera[$i].rtsp_path 2>/dev/null || true)"
      CAM_USER="$(uci -q get datbeo_camera.@camera[$i].username 2>/dev/null || true)"
      CAM_PASS="$(uci -q get datbeo_camera.@camera[$i].password 2>/dev/null || true)"
      return 0
    fi
    i=$((i+1))
  done
  return 1
}

cred_escape(){
  printf '%s' "$1" | sed -e 's/%/%25/g' -e 's/@/%40/g' -e 's/:/%3A/g' -e 's/#/%23/g' -e 's/?/%3F/g' -e 's/ /%20/g'
}
rtsp_url(){
  case "$CAM_PATH" in
    rtsp://*) printf "%s" "$CAM_PATH" ;;
    *)
      p="$CAM_PATH"; case "$p" in /*) ;; *) p="/$p";; esac
      if [ -n "$CAM_USER" ]; then
        printf "rtsp://%s:%s@%s:%s%s" "$(cred_escape "$CAM_USER")" "$(cred_escape "$CAM_PASS")" "$CAM_IP" "${CAM_PORT:-554}" "$p"
      else
        printf "rtsp://%s:%s%s" "$CAM_IP" "${CAM_PORT:-554}" "$p"
      fi
      ;;
  esac
}

CAM_STREAM_BASE="/www/datbeo/camera-stream"
FFMPEG="$(command -v ffmpeg 2>/dev/null || true)"
FFPROBE="$(command -v ffprobe 2>/dev/null || true)"
case "$ACTION" in
list)
 printf '{"cameras":['
 first=1; i=0
 while ID0="$(uci -q get datbeo_camera.@camera[$i].id 2>/dev/null)"; do
   [ "$first" -eq 1 ] || printf ","; first=0
   N="$(uci -q get datbeo_camera.@camera[$i].name 2>/dev/null || true)"
   IP="$(uci -q get datbeo_camera.@camera[$i].ip 2>/dev/null || true)"
   P="$(uci -q get datbeo_camera.@camera[$i].port 2>/dev/null || echo 554)"
   R="$(uci -q get datbeo_camera.@camera[$i].rtsp_path 2>/dev/null || true)"
   U="$(uci -q get datbeo_camera.@camera[$i].username 2>/dev/null || true)"
   printf '{"id":"%s","name":"%s","ip":"%s","port":"%s","path":"%s","username":"%s","has_password":%s}' \

    "$(json_escape "$ID0")" "$(json_escape "$N")" "$(json_escape "$IP")" "$(json_escape "$P")" "$(json_escape "$R")" "$(json_escape "$U")" \

    "$([ -n "$(uci -q get datbeo_camera.@camera[$i].password 2>/dev/null || true)" ] && printf true || printf false)"
   i=$((i+1))
 done
 printf ']}\n"
 ;;
save)
 N="$(dec "$(param name "$BODY")")"; IP="$(dec "$(param ip "$BODY")")"; P="$(dec "$(param port "$BODY")")"
 R="$(dec "$(param rtsp_path "$BODY")")"; U="$(dec "$(param username "$BODY")")"; PW="$(dec "$(param password "$BODY")")"
 [ -n "$N" ] && [ -n "$IP" ] && [ -n "$R" ] || { printf '{"ok":false,"error":"Thiếu thông tin camera"}\n'; exit; }
 [ -n "$ID" ] || ID="cam_$(hexdump -n 4 -e "4/1 \"%02x\"" /dev/urandom)"
 i=0; found=0
 while ID0="$(uci -q get datbeo_camera.@camera[$i].id 2>/dev/null)"; do
   if [ "$ID0" = "$ID" ]; then found=$((i+1)); break; fi
   i=$((i+1))
 done
 if [ "$found" -gt 0 ]; then s=$((found-1)); else uci add datbeo_camera camera >/dev/null; s=$(( $(uci show datbeo_camera | grep -c "^datbeo_camera.@camera") - 1 )); fi
 uci set datbeo_camera.@camera[$s].id="$ID"
 uci set datbeo_camera.@camera[$s].name="$N"
 uci set datbeo_camera.@camera[$s].ip="$IP"
 uci set datbeo_camera.@camera[$s].port="${P:-554}"
 uci set datbeo_camera.@camera[$s].rtsp_path="$R"
 uci set datbeo_camera.@camera[$s].username="$U"
 [ -n "$PW" ] && uci set datbeo_camera.@camera[$s].password="$PW"
 uci commit datbeo_camera
 printf '{"ok":true,"id":"%s"}\n' "$(json_escape "$ID")"
 ;;
delete)
 i=0
 while ID0="$(uci -q get datbeo_camera.@camera[$i].id 2>/dev/null)"; do
   if [ "$ID0" = "$ID" ]; then uci delete datbeo_camera.@camera[$i]; uci commit datbeo_camera; printf '{"ok":true}\n'; exit; fi
   i=$((i+1))
 done
 printf '{"ok":false,"error":"Không tìm thấy camera"}\n"
 ;;

test)
  [ -n "$ID" ] || { printf '{"ok":false,"error":"Thiếu id"}\n'; exit; }
  [ -n "$FFPROBE" ] || { printf '{"ok":false,"error":"Thiếu ffprobe. Hãy chạy lại deploy để cài ffmpeg/ffprobe."}\n'; exit; }
  if ! load_camera; then printf '{"ok":false,"error":"Không tìm thấy camera"}\n'; exit; fi
  URL="$(rtsp_url)"
  OUT="$(timeout 8 "$FFPROBE" -v error -rtsp_transport tcp -rw_timeout 6000000 -show_entries stream=codec_type,codec_name,width,height -of compact=p=0:nk=1 "$URL" 2>/dev/null || true)"
  if [ -n "$OUT" ]; then
    SAFE="$(printf "%s" "$OUT" | tr "\n" ";" | cut -c1-500)"
    printf '{"ok":true,"message":"Kết nối RTSP OK","streams":"%s"}\n' "$(json_escape "$SAFE")"
  else
    printf '{"ok":false,"error":"Không kết nối được RTSP hoặc camera không phản hồi"}\n'
  fi
  ;;
stream)
  [ -n "$ID" ] || { printf '{"ok":false,"error":"Thiếu id"}\n'; exit; }
  [ -n "$FFMPEG" ] || { printf '{"ok":false,"error":"Thiếu ffmpeg. Hãy chạy lại deploy để cài ffmpeg."}\n'; exit; }
  if ! load_camera; then printf '{"ok":false,"error":"Không tìm thấy camera"}\n'; exit; fi
  DIR="$CAM_STREAM_BASE/$ID"
  mkdir -p "$DIR"
  PIDFILE="/tmp/datbeo-camera-$ID.pid"
  PID=""
  [ -f "$PIDFILE" ] && PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null && [ -f "$DIR/index.m3u8" ]; then
    printf '{"ok":true,"url":"/datbeo/camera-stream/%s/index.m3u8"}\n' "$(json_escape "$ID")"
    exit
  fi
  rm -f "$DIR"/*.m3u8 "$DIR"/*.ts 2>/dev/null || true
  URL="$(rtsp_url)"
  "$FFMPEG" -hide_banner -loglevel error -rtsp_transport tcp -i "$URL" -map 0:v:0 -an -c:v copy -f hls -hls_time 1 -hls_list_size 3 -hls_flags delete_segments+append_list+omit_endlist -hls_segment_filename "$DIR/seg_%03d.ts" "$DIR/index.m3u8" >/dev/null 2>&1 </dev/null &
  echo $! > "$PIDFILE"
  sleep 2
  printf '{"ok":true,"url":"/datbeo/camera-stream/%s/index.m3u8"}\n' "$(json_escape "$ID")"
  ;;
stop)
  [ -n "$ID" ] || { printf '{"ok":false,"error":"Thiếu id"}\n'; exit; }
  PIDFILE="/tmp/datbeo-camera-$ID.pid"
  if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
  rm -f "$CAM_STREAM_BASE/$ID"/*.m3u8 "$CAM_STREAM_BASE/$ID"/*.ts 2>/dev/null || true
  printf '{"ok":true}\n'
  ;;
*) printf '{"ok":false,"error":"Action không hợp lệ"}\n' ;;
esac
