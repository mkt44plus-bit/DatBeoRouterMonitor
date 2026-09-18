#!/bin/sh
DB="/etc/datbeo-router-monitor/cameras.db"
BASE="/www/datbeo/camera-stream"
API_FILE="/etc/datbeo-router-monitor/api_key"
API_KEY="$(cat "$API_FILE" 2>/dev/null || true)"
REQ_KEY="$HTTP_X_API_KEY"
QUERY="$QUERY_STRING"

mkdir -p /etc/datbeo-router-monitor "$BASE"
[ -f "$DB" ] || : > "$DB"
chmod 600 "$DB"

json_escape() {
  printf "%s" "$1" | sed 's/\\/\\\\/g; s/"/\\\"/g'
}

decode() {
  printf '%b' "$(printf "%s" "$1" | sed 's/+/ /g; s/%/\\x/g')"
}

cred_escape() {
  printf "%s" "$1" | sed -e 's/%/%25/g' -e 's/@/%40/g' -e 's/:/%3A/g' -e 's/#/%23/g' -e 's/?/%3F/g' -e 's/ /%20/g'
}

param() {
  printf "%s" "$2" | tr '&' '\n' | sed -n "s/^$1=//p" | head -n 1
}

[ -n "$REQ_KEY" ] || REQ_KEY="$(param key "$QUERY")"
printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n'

if [ -z "$API_KEY" ] || [ "$REQ_KEY" != "$API_KEY" ]; then
  printf '{"ok":false,"error":"unauthorized"}\n'
  exit 0
fi

BODY=""
N="$CONTENT_LENGTH"
[ -n "$N" ] || N=0
if [ "$N" -gt 0 ] 2>/dev/null; then BODY="$(dd bs=1 count="$N" 2>/dev/null)"; fi
[ -n "$BODY" ] || BODY="$QUERY"

ACTION="$(param action "$BODY")"
ID="$(param id "$BODY")"

load_camera() {
  I=0
  while ID0="$(uci -q get datbeo_camera.@camera[$I].id 2>/dev/null)"; do
    if [ "$ID0" = "$ID" ]; then
      CAM_NAME="$(uci -q get datbeo_camera.@camera[$I].name 2>/dev/null || true)"
      CAM_IP="$(uci -q get datbeo_camera.@camera[$I].ip 2>/dev/null || true)"
      CAM_PORT="$(uci -q get datbeo_camera.@camera[$I].port 2>/dev/null || true)"
      [ -n "$CAM_PORT" ] || CAM_PORT=554
      CAM_PATH="$(uci -q get datbeo_camera.@camera[$I].rtsp_path 2>/dev/null || true)"
      CAM_USER="$(uci -q get datbeo_camera.@camera[$I].username 2>/dev/null || true)"
      CAM_PASS="$(uci -q get datbeo_camera.@camera[$I].password 2>/dev/null || true)"
      return 0
    fi
    I=$((I+1))
  done
  return 1
}

rtsp_url() {
  case "$CAM_PATH" in
    rtsp://*) printf "%s" "$CAM_PATH" ;;
    *)
      P="$CAM_PATH"
      case "$P" in /*) ;; *) P="/$P" ;; esac
      if [ -n "$CAM_USER" ]; then
        printf 'rtsp://%s:%s@%s:%s%s' "$(cred_escape "$CAM_USER")" "$(cred_escape "$CAM_PASS")" "$CAM_IP" "$CAM_PORT" "$P"
      else
        printf 'rtsp://%s:%s%s' "$CAM_IP" "$CAM_PORT" "$P"
      fi
      ;;
  esac
}

case "$ACTION" in
list)
  printf '{"cameras":['
  FIRST=1
  I=0
  while ID0="$(uci -q get datbeo_camera.@camera[$I].id 2>/dev/null)"; do
    [ "$FIRST" -eq 1 ] || printf ','
    FIRST=0
    N0="$(uci -q get datbeo_camera.@camera[$I].name 2>/dev/null || true)"
    IP0="$(uci -q get datbeo_camera.@camera[$I].ip 2>/dev/null || true)"
    P0="$(uci -q get datbeo_camera.@camera[$I].port 2>/dev/null || true)"; [ -n "$P0" ] || P0=554
    R0="$(uci -q get datbeo_camera.@camera[$I].rtsp_path 2>/dev/null || true)"
    U0="$(uci -q get datbeo_camera.@camera[$I].username 2>/dev/null || true)"
    PW0="$(uci -q get datbeo_camera.@camera[$I].password 2>/dev/null || true)"
    printf '{"id":"%s","name":"%s","ip":"%s","port":"%s","path":"%s","username":"%s","has_password":%s}' \
      "$(json_escape "$ID0")" "$(json_escape "$N0")" "$(json_escape "$IP0")" "$(json_escape "$P0")" "$(json_escape "$R0")" "$(json_escape "$U0")" \
      "$([ -n "$PW0" ] && printf true || printf false)"
    I=$((I+1))
  done
  printf ']}\n'
  ;;
save)
  N0="$(decode "$(param name "$BODY")")"
  IP0="$(decode "$(param ip "$BODY")")"
  P0="$(decode "$(param port "$BODY")")"; [ -n "$P0" ] || P0=554
  R0="$(decode "$(param rtsp_path "$BODY")")"
  U0="$(decode "$(param username "$BODY")")"
  PW0="$(decode "$(param password "$BODY")")"
  [ -n "$N0" ] && [ -n "$IP0" ] && [ -n "$R0" ] || { printf '{"ok":false,"error":"Thiếu thông tin camera"}\n'; exit 0; }
  [ -n "$ID" ] || ID="cam_$(hexdump -n 4 -e '4/1 "%02x"' /dev/urandom)"
  I=0; FOUND=-1
  while ID0="$(uci -q get datbeo_camera.@camera[$I].id 2>/dev/null)"; do
    if [ "$ID0" = "$ID" ]; then FOUND=$I; break; fi
    I=$((I+1))
  done
  if [ "$FOUND" -lt 0 ]; then
    uci add datbeo_camera camera >/dev/null
    COUNT="$(uci show datbeo_camera 2>/dev/null | grep -c '^datbeo_camera.@camera')"
    S=$((COUNT-1))
  else S="$FOUND"; fi
  uci set datbeo_camera.@camera[$S].id="$ID"
  uci set datbeo_camera.@camera[$S].name="$N0"
  uci set datbeo_camera.@camera[$S].ip="$IP0"
  uci set datbeo_camera.@camera[$S].port="$P0"
  uci set datbeo_camera.@camera[$S].rtsp_path="$R0"
  uci set datbeo_camera.@camera[$S].username="$U0"
  [ -n "$PW0" ] && uci set datbeo_camera.@camera[$S].password="$PW0"
  uci commit datbeo_camera
  printf '{"ok":true,"id":"%s"}\n' "$(json_escape "$ID")"
  ;;
delete)
  I=0
  while ID0="$(uci -q get datbeo_camera.@camera[$I].id 2>/dev/null)"; do
    if [ "$ID0" = "$ID" ]; then
      uci delete datbeo_camera.@camera[$I]
      uci commit datbeo_camera
      PIDFILE="/tmp/datbeo-camera-$ID.pid"
      if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
      rm -rf "$BASE/$ID"
      printf '{"ok":true}\n'
      exit 0
    fi
    I=$((I+1))
  done
  printf '{"ok":false,"error":"Không tìm thấy camera"}\n'
  ;;
test)
  FFP="$(command -v ffprobe 2>/dev/null || true)"
  [ -n "$ID" ] || { printf '{"ok":false,"error":"Thiếu id"}\n'; exit 0; }
  [ -n "$FFP" ] || { printf '{"ok":false,"error":"Router chưa có ffprobe. Chạy lại deploy."}\n'; exit 0; }
  load_camera || { printf '{"ok":false,"error":"Không tìm thấy camera"}\n'; exit 0; }
  URL="$(rtsp_url)"
  OUT="$(timeout 8 "$FFP" -v error -rtsp_transport tcp -rw_timeout 6000000 -show_entries stream=codec_name,codec_type,width,height -of compact=p=0:nk=1 "$URL" 2>/dev/null || true)"
  if [ -n "$OUT" ]; then
    SAFE="$(printf "%s" "$OUT" | tr '\n' ';' | cut -c1-500)"
    printf '{"ok":true,"message":"Kết nối RTSP OK","streams":"%s"}\n' "$(json_escape "$SAFE")"
  else
    printf '{"ok":false,"error":"Không kết nối được RTSP hoặc camera không phản hồi"}\n'
  fi
  ;;
stream)
  FFM="$(command -v ffmpeg 2>/dev/null || true)"
  [ -n "$ID" ] || { printf '{"ok":false,"error":"Thiếu id"}\n'; exit 0; }
  [ -n "$FFM" ] || { printf '{"ok":false,"error":"Router chưa có ffmpeg. Chạy lại deploy."}\n'; exit 0; }
  load_camera || { printf '{"ok":false,"error":"Không tìm thấy camera"}\n'; exit 0; }
  DIR="$BASE/$ID"; mkdir -p "$DIR"; PIDFILE="/tmp/datbeo-camera-$ID.pid"
  PID=""; [ -f "$PIDFILE" ] && PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null && [ -f "$DIR/index.m3u8" ]; then
    printf '{"ok":true,"url":"/datbeo/camera-stream/%s/index.m3u8"}\n' "$(json_escape "$ID")"; exit 0
  fi
  rm -f "$DIR"/*.m3u8 "$DIR"/*.ts 2>/dev/null || true
  URL="$(rtsp_url)"
  "$FFM" -hide_banner -loglevel error -rtsp_transport tcp -i "$URL" -map 0:v:0 -an -c:v copy -f hls -hls_time 1 -hls_list_size 3 -hls_flags delete_segments+append_list+omit_endlist -hls_segment_filename "$DIR/seg_%03d.ts" "$DIR/index.m3u8" >/dev/null 2>&1 </dev/null &
  echo $! > "$PIDFILE"
  sleep 2
  if [ -f "$DIR/index.m3u8" ]; then
    printf '{"ok":true,"url":"/datbeo/camera-stream/%s/index.m3u8"}\n' "$(json_escape "$ID")"
  else
    printf '{"ok":false,"error":"Không tạo được luồng HLS. Kiểm tra RTSP và codec camera."}\n'
  fi
  ;;
stop)
  PIDFILE="/tmp/datbeo-camera-$ID.pid"
  if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
  rm -f "$BASE/$ID"/*.m3u8 "$BASE/$ID"/*.ts 2>/dev/null || true
  printf '{"ok":true}\n'
  ;;
*)
  printf '{"ok":false,"error":"Action không hợp lệ"}\n'
  ;;
esac
