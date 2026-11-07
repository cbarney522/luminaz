#!/bin/bash
# Runs on the server, as root, each time GitHub uploads a new version (systemd starts it when the
# signal file changes). Copies the new code over the old, installs what it needs, restarts Luminaz,
# checks that the site answers, and puts the old version back if it does not.
#
# Never touches /opt/luminaz/app/instance: that folder is the database, uploads and backups.
set -euo pipefail

source /etc/luminaz/deploy.env        # INCOMING (where FTP uploads land), APP, PORT
LOG=/var/log/luminaz-deploy.log
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') deploy started: $(cat "$SIGNAL_FILE" 2>/dev/null || echo 'no signal text')"

# One deploy at a time
exec 9>/run/luminaz-deploy.lock
flock -n 9 || { echo "another deploy is running; stopping"; exit 0; }

sleep 5                                # let the signal file's upload finish closing
[ -f "$INCOMING/manage.py" ] || { echo "ERROR: $INCOMING has no manage.py; nothing deployed"; exit 1; }

PREV=/opt/luminaz/previous
rm -rf "$PREV"
mkdir -p "$PREV"
rsync -a --exclude instance "$APP"/ "$PREV"/

# New code in. --delete removes files that no longer exist in the repo; instance/ is protected.
rsync -a --delete --exclude instance --exclude venv --exclude '.ftp-deploy-sync-state*.json' "$INCOMING"/ "$APP"/
chown -R luminaz:luminaz "$APP"

# Python packages, as the luminaz user
runuser -u luminaz -- /opt/luminaz/venv/bin/pip install --quiet -r "$APP/requirements.txt"

systemctl restart luminaz

# Did it come up?
for i in $(seq 1 15); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/login"; then
    echo "OK: Luminaz answers on port $PORT. Deploy finished."
    exit 0
  fi
  sleep 2
done

echo "ERROR: Luminaz did not answer after the restart. Putting the previous version back."
rsync -a --delete --exclude instance "$PREV"/ "$APP"/
chown -R luminaz:luminaz "$APP"
systemctl restart luminaz
exit 1
