#!/bin/sh
set -eu

if [ -z "${COUCHDB_USER:-}" ] || [ -z "${COUCHDB_PASSWORD:-}" ]; then
  echo "COUCHDB_USER and COUCHDB_PASSWORD are required." >&2
  exit 1
fi

# Render generates a strong password. Keep it inside the container configuration.
printf '[admins]\n%s = %s\n' "$COUCHDB_USER" "$COUCHDB_PASSWORD" \
  > /opt/couchdb/etc/local.d/99-playshelf-admin.ini

/opt/couchdb/bin/couchdb &
couch_pid=$!

stop_services() {
  kill "$web_pid" "$couch_pid" 2>/dev/null || true
}
trap stop_services INT TERM EXIT

attempt=0
until curl --fail --silent --show-error http://127.0.0.1:5984/_up >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "CouchDB did not become ready." >&2
    exit 1
  fi
  sleep 1
done

python -m flask --app app init-db
waitress-serve --listen="0.0.0.0:${PORT:-10000}" app:app &
web_pid=$!
wait "$web_pid"
