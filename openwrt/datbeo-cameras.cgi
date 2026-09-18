#!/bin/sh
DB="/etc/datbeo-router-monitor/cameras.db"
BASE="/www/datbeo/camera-stream"
API_FILE="/etc/datbeo-router-monitor/api_key"
API_KEY="$(cat "$API_FILE" 2>/dev/null || true)"
REQ_KEY="$HTTP_X_API_KEY"
QUERY="$QUERY_STRING"

mkdir -p /etc/datbeo-router-monitor /etc/config "$BASE"
[ -f "$DB" ] || : > "$DB"
[ -f /etc/config/datbeo_camera ] || : > /etc/config/datbeo_camera
chmod 600 "$DB" /etc/config/datbeo_camera

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
lan_info)
  LAN_DEV="$(uci -q get network.lan.device 2>/dev/null || uci -q get network.lan.ifname 2>/dev/null || printf br-lan)"
  LAN_ADDR="$(ip -4 addr show dev "$LAN_DEV" 2>/dev/null | awk '/inet /{print $2; exit}')"
  NB_ADDR="$(ip -4 addr show dev wt0 2>/dev/null | awk '/inet /{print $2; exit}')"
  [ -n "$LAN_ADDR" ] || LAN_ADDR=""
  printf '{"ok":true,"lan_dev":"%s","lan_cidr":"%s","netbird":"%s"}\n' "$(json_escape "$LAN_DEV")" "$(json_escape "$LAN_ADDR")" "$(json_escape "$NB_ADDR")"
  ;;
scan)
  CIDR="$(decode "$(param cidr "$BODY")")"
  LAN_DEV="$(uci -q get network.lan.device 2>/dev/null || uci -q get network.lan.ifname 2>/dev/null || printf br-lan)"
  if [ "$CIDR" = "auto" ] || [ -z "$CIDR" ]; then
    CIDR="$(ip -4 addr show dev "$LAN_DEV" 2>/dev/null | awk '/inet /{print $2; exit}')"
  fi
  command -v nc >/dev/null 2>&1 || { printf '{"ok":false,"error":"Router chưa có nc để quét mạng"}\n'; exit 0; }
  command -v ping >/dev/null 2>&1 || { printf '{"ok":false,"error":"Router chưa có ping để quét mạng"}\n'; exit 0; }
  case "$CIDR" in */*) ;; *) printf '{"ok":false,"error":"Không xác định được dải LAN của router"}\n'; exit 0 ;; esac
  IP0="${CIDR%/*}"; PREFIX="${CIDR#*/}"
  case "$PREFIX" in *[!0-9]*|"") printf '{"ok":false,"error":"CIDR không hợp lệ"}\n'; exit 0 ;; esac
  [ "$PREFIX" -ge 16 ] 2>/dev/null && [ "$PREFIX" -le 32 ] 2>/dev/null || { printf '{"ok":false,"error":"Chỉ hỗ trợ IPv4 /16 đến /32"}\n'; exit 0; }
  OLDIFS="$IFS"; IFS=.
  set -- $IP0
  IFS="$OLDIFS"
  [ "$#" -eq 4 ] || { printf '{"ok":false,"error":"IP không hợp lệ"}\n'; exit 0; }
  for O in "$@"; do
    case "$O" in *[!0-9]*|"") printf '{"ok":false,"error":"IP không hợp lệ"}\n'; exit 0 ;; esac
    [ "$O" -ge 0 ] 2>/dev/null && [ "$O" -le 255 ] 2>/dev/null || { printf '{"ok":false,"error":"IP không hợp lệ"}\n'; exit 0; }
  done
  A="$1"; B="$2"; C="$3"; D="$4"
  IPNUM=$((A*16777216+B*65536+C*256+D))
  HOSTBITS=$((32-PREFIX))
  BLOCK=1
  HB=0
  while [ "$HB" -lt "$HOSTBITS" ]; do BLOCK=$((BLOCK*2)); HB=$((HB+1)); done
  [ "$BLOCK" -le 1024 ] || { printf '{"ok":false,"error":"Dải quá lớn; giới hạn 1024 địa chỉ mỗi lần quét"}\n'; exit 0; }
  NET=$((IPNUM-(IPNUM % BLOCK)))
  START="$NET"; END=$((NET+BLOCK-1))
  if [ "$PREFIX" -le 30 ]; then START=$((NET+1)); END=$((END-1)); fi

  LEASE_FILES="/tmp/dhcp.leases /var/dhcp.leases"
  OUT="/tmp/datbeo-scan-$$.txt"
  : > "$OUT"

  scan_host() {
    N="$1"
    SIP="$((N/16777216)).$(((N/65536)%256)).$(((N/256)%256)).$((N%256))"
    ALIVE=0

    NEIGH="$(ip neigh show "$SIP" dev "$LAN_DEV" 2>/dev/null | head -n 1 || true)"
    case "$NEIGH" in
      *" FAILED"*|*" INCOMPLETE"*) ;;
      "") ;;
      *) ALIVE=1 ;;
    esac

    ping -c 1 -W 1 "$SIP" >/dev/null 2>&1 && ALIVE=1

    RTSP_PORT=""
    HTTP_PORT=""

    for PORT in 554 8554 10554; do
      if nc -z -w 1 "$SIP" "$PORT" >/dev/null 2>&1; then
        RTSP_PORT="$PORT"
        ALIVE=1
        break
      fi
    done

    for PORT in 80 443 8000 8080 8081 8888; do
      if nc -z -w 1 "$SIP" "$PORT" >/dev/null 2>&1; then
        HTTP_PORT="$PORT"
        ALIVE=1
        break
      fi
    done

    [ "$ALIVE" -eq 1 ] || return 0

    MAC=""
    case "$NEIGH" in
      *" lladdr "*)
        MAC="$(printf "%s" "$NEIGH" | sed -n 's/.* lladdr \([^ ]*\).*/\1/p')"
        ;;
    esac

    NAME=""
    for LF in $LEASE_FILES; do
      if [ -f "$LF" ]; then
        L="$(awk -v ip="$SIP" '$3==ip{print $2"|"$4; exit}' "$LF" 2>/dev/null || true)"
        if [ -n "$L" ]; then
          LMAC="${L%%|*}"
          LNAME="${L#*|}"
          [ -n "$MAC" ] || MAC="$LMAC"
          [ "$LNAME" = "*" ] || NAME="$LNAME"
          break
        fi
      fi
    done

    PROTO="HTTP"
    PORT="$HTTP_PORT"
    [ -n "$RTSP_PORT" ] && { PROTO="RTSP"; PORT="$RTSP_PORT"; }

    printf '%s|%s|%s|%s|%s\n' "$SIP" "$PROTO" "$PORT" "$MAC" "$NAME" >> "$OUT"
  }

  WORKERS=16
  RANGE=$((END-START+1))
  [ "$RANGE" -lt "$WORKERS" ] && WORKERS="$RANGE"
  NEXT="$START"
  while [ "$NEXT" -le "$END" ]; do
    W=0
    while [ "$W" -lt "$WORKERS" ] && [ $((NEXT+W)) -le "$END" ]; do
      scan_host "$((NEXT+W))" &
      W=$((W+1))
    done
    wait
    NEXT=$((NEXT+WORKERS))
  done

  printf '{"ok":true,"devices":['
  FIRST=1
  while IFS='|' read -r SIP PROTO SPORT MAC NAME; do
    [ -n "$SIP" ] || continue
    [ "$FIRST" -eq 1 ] || printf ","
    FIRST=0
    printf '{"ip":"%s","protocol":"%s","port":"%s","mac":"%s","name":"%s"}'       "$(json_escape "$SIP")" "$(json_escape "$PROTO")" "$(json_escape "$SPORT")" "$(json_escape "$MAC")" "$(json_escape "$NAME")"
  done < "$OUT"
  printf '],"cidr":"%s","lan_dev":"%s"}\n' "$(json_escape "$CIDR")" "$(json_escape "$LAN_DEV")"
  rm -f "$OUT"
  ;;
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
  chmod 600 /etc/config/datbeo_camera 2>/dev/null || true
  printf '{"ok":true,"id":"%s"}\n' "$(json_escape "$ID")"
  ;;
delete)
  I=0
  while ID0="$(uci -q get datbeo_camera.@camera[$I].id 2>/dev/null)"; do
    if [ "$ID0" = "$ID" ]; then
      uci delete datbeo_camera.@camera[$I]
      uci commit datbeo_camera
      chmod 600 /etc/config/datbeo_camera 2>/dev/null || true
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
test_form)
  FFP="$(command -v ffprobe 2>/dev/null || true)"
  [ -n "$FFP" ] || { printf '{"ok":false,"error":"Router chưa có ffprobe. Chạy lại deploy."}\n'; exit 0; }
  CAM_NAME="$(decode "$(param name "$BODY")")"
  CAM_IP="$(decode "$(param ip "$BODY")")"
  CAM_PORT="$(decode "$(param port "$BODY")")"; [ -n "$CAM_PORT" ] || CAM_PORT=554
  CAM_PATH="$(decode "$(param rtsp_path "$BODY")")"
  CAM_USER="$(decode "$(param username "$BODY")")"
  CAM_PASS="$(decode "$(param password "$BODY")")"
  [ -n "$CAM_IP" ] && [ -n "$CAM_PATH" ] || { printf '{"ok":false,"error":"Thiếu IP hoặc đường dẫn RTSP"}\n'; exit 0; }
  URL="$(rtsp_url)"
  OUT="$(timeout 8 "$FFP" -v error -rtsp_transport tcp -rw_timeout 6000000 -show_entries stream=codec_name,codec_type,width,height -of compact=p=0:nk=1 "$URL" 2>/dev/null || true)"
  if [ -n "$OUT" ]; then
    SAFE="$(printf "%s" "$OUT" | tr '\n' ';' | cut -c1-500)"
    printf '{"ok":true,"message":"Kết nối RTSP OK","streams":"%s"}\n' "$(json_escape "$SAFE")"
  else
    printf '{"ok":false,"error":"Không kết nối được RTSP hoặc camera không phản hồi"}\n'
  fi
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
