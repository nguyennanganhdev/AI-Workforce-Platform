#!/bin/bash
# Alert when the platform goes down or comes back. Run by awp-uptime.timer.
# Optional /etc/awp-guard/uptime.env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
# UPTIME_URLS (space separated). Without a token it only logs to the journal.
set -uo pipefail
[ -f /etc/awp-guard/uptime.env ] && . /etc/awp-guard/uptime.env
URLS=${UPTIME_URLS:-"https://vinhome-platform.duckdns.org/ https://vinhome-platform.duckdns.org/api/health"}
STATE_DIR=${UPTIME_STATE_DIR:-/var/lib/awp-guard}
mkdir -p "$STATE_DIR"
STATE="$STATE_DIR/uptime.state"   # "up" or "down:<consecutive failures>"
previous=$(cat "$STATE" 2>/dev/null || echo up)

failed=""
for url in $URLS; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url")
  [ "$code" = 200 ] || failed="$failed $url=$code"
done

notify() {
  logger -t awp-uptime "$1"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -s --max-time 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1" >/dev/null \
      || logger -t awp-uptime "Telegram alert could not be sent"
  fi
}

if [ -z "$failed" ]; then
  case "$previous" in
    down:[2-9]*|down:[1-9][0-9]*) notify "✅ vinhome-platform hoạt động trở lại ($(date '+%H:%M %d/%m'))." ;;
  esac
  echo up > "$STATE"
else
  count=1
  case "$previous" in down:*) count=$(( ${previous#down:} + 1 )) ;; esac
  echo "down:$count" > "$STATE"
  # Two failures in a row (about 4 minutes) before alerting, to skip blips and restarts.
  [ "$count" -eq 2 ] && notify "🔴 vinhome-platform không phản hồi:$failed ($(date '+%H:%M %d/%m'))."
  logger -t awp-uptime "check failed ($count):$failed"
fi
exit 0
