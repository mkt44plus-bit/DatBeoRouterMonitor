#!/bin/sh
DB="/etc/datbeo-router-monitor/cameras.db"
mkdir -p /etc/datbeo-router-monitor
[ -f "$DB" ] || : > "$DB"
chmod 600 "$DB"

json_escape(){ printf "%s" "$1" | sed 's/\\/\\\\/g; s/"/\\\"/g'; }
dec(){ printf "%b" "$(printf "%s" "$1" | sed 's/+/ /g; s/%/\\x/g')"; }

param(){ printf "%s" "$2" | tr "&" "\n" | sed -n "s/^$1=//p" | head -n1; }

printf "Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n"
BODY=""
[ "${CONTENT_LENGTH:-0}" -gt 0 ] 2>/dev/null && BODY="$(dd bs=1 count="$CONTENT_LENGTH" 2>/dev/null)"
[ -n "$BODY" ] || BODY="$QUERY_STRING"
ACTION="$(param action "$BODY")"
ID="$(param id "$BODY")"

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
*) printf '{"ok":false,"error":"Action không hợp lệ"}\n' ;;
esac
