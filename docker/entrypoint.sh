#!/usr/bin/env sh
set -eu

# Preserve env values with spaces for optional debugging/sourcing.
printenv | while IFS='=' read -r key value; do
  esc_value=$(printf "%s" "$value" | sed "s/'/'\"'\"'/g")
  printf "export %s='%s'\n" "$key" "$esc_value"
done > /app/.env.sh
chmod 600 /app/.env.sh

INTERVAL="${SCRAPE_INTERVAL_SECONDS:-30}"
case "$INTERVAL" in
  ''|*[!0-9]*)
    echo "SCRAPE_INTERVAL_SECONDS must be a positive integer, got: $INTERVAL" >&2
    exit 1
    ;;
esac
if [ "$INTERVAL" -le 0 ]; then
  echo "SCRAPE_INTERVAL_SECONDS must be > 0, got: $INTERVAL" >&2
  exit 1
fi

echo "Starting scraper loop with interval ${INTERVAL}s"
while true; do
  if ! python /app/src/main.py; then
    echo "Scrape run failed; retrying in ${INTERVAL}s" >&2
  fi
  sleep "$INTERVAL"
done
