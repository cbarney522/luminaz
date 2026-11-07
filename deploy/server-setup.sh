#!/bin/bash
# One-time setup on the server. Run as root, from a copy of this repo:
#
#   git clone https://github.com/cbarney522/luminaz /root/luminaz-src
#   cd /root/luminaz-src
#   sudo bash deploy/server-setup.sh /home/FTPUSER/luminaz-incoming /home/FTPUSER/luminaz-signal
#
# The two arguments are the full server paths of the two folders the FTP account uploads into
# (the FTP paths "luminaz-incoming/" and "luminaz-signal/", seen from the server's side).
# Written for AlmaLinux 8. Safe to run twice. It does NOT touch Apache or InterWorx.
set -euo pipefail

INCOMING="${1:?first argument: full path of the luminaz-incoming folder}"
SIGNAL_DIR="${2:?second argument: full path of the luminaz-signal folder}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
SIGNAL_FILE="$SIGNAL_DIR/deploy-trigger.txt"

[ "$(id -u)" = 0 ] || { echo "Run as root."; exit 1; }
[ -d "$INCOMING" ] || { echo "Missing folder: $INCOMING (create it by uploading once over FTP, or mkdir it)"; exit 1; }
[ -d "$SIGNAL_DIR" ] || { echo "Missing folder: $SIGNAL_DIR"; exit 1; }

echo "1. Python 3.12 (alongside the system Python; the system one is not touched)"
dnf -y install python3.12 python3.12-pip rsync curl

echo "2. The luminaz user and folders"
id luminaz >/dev/null 2>&1 || useradd --system --home-dir /opt/luminaz --shell /sbin/nologin luminaz
mkdir -p /opt/luminaz/app /etc/luminaz
python3.12 -m venv /opt/luminaz/venv

echo "3. First copy of the code"
# Only if the code is already uploaded; otherwise the first GitHub deploy does this.
if [ -f "$INCOMING/manage.py" ]; then
  rsync -a --exclude instance "$INCOMING"/ /opt/luminaz/app/
else
  rsync -a --exclude instance --exclude .git --exclude tests --exclude deploy "$SRC"/ /opt/luminaz/app/
fi
chown -R luminaz:luminaz /opt/luminaz
runuser -u luminaz -- /opt/luminaz/venv/bin/pip install --quiet -r /opt/luminaz/app/requirements.txt

echo "4. Settings files (only created if missing, so a second run never overwrites your values)"
if [ ! -f /etc/luminaz/luminaz.env ]; then
  SECRET="$(python3.12 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > /etc/luminaz/luminaz.env <<EOF
# Luminaz settings. Keep this file private (root only). Never change LUMINAZ_SECRET after the first
# sign-in: it signs sessions and encrypts the admins' two-step codes.
LUMINAZ_SECRET=$SECRET
LUMINAZ_HTTPS=1
TZ=America/New_York
# Outgoing email: fill these in when you have the mail account's details. Until then email is
# written to instance/outbox and nothing is sent.
#LUMINAZ_SMTP_HOST=
#LUMINAZ_SMTP_PORT=587
#LUMINAZ_SMTP_USER=
#LUMINAZ_SMTP_PASSWORD=
#LUMINAZ_MAIL_FROM=
EOF
  chmod 600 /etc/luminaz/luminaz.env
  chown root:root /etc/luminaz/luminaz.env
fi
cat > /etc/luminaz/deploy.env <<EOF
INCOMING=$INCOMING
SIGNAL_FILE=$SIGNAL_FILE
APP=/opt/luminaz/app
PORT=8000
EOF
chmod 600 /etc/luminaz/deploy.env

echo "5. The services"
install -m 755 "$SRC/deploy/luminaz-deploy.sh" /opt/luminaz/luminaz-deploy.sh
install -m 644 "$SRC/deploy/luminaz.service" /etc/systemd/system/luminaz.service
install -m 644 "$SRC/deploy/luminaz-deploy.service" /etc/systemd/system/luminaz-deploy.service
sed "s|__SIGNAL_FILE__|$SIGNAL_FILE|" "$SRC/deploy/luminaz-deploy.path" > /etc/systemd/system/luminaz-deploy.path
systemctl daemon-reload
systemctl enable --now luminaz
systemctl enable --now luminaz-deploy.path

echo "6. Check"
sleep 3
if curl -fsS -o /dev/null http://127.0.0.1:8000/login; then
  echo "Luminaz answers on 127.0.0.1:8000."
else
  echo "Luminaz did not answer. Look at: journalctl -u luminaz -n 50"
  exit 1
fi
echo
echo "Next: create the first admin (as the luminaz user, from /opt/luminaz/app):"
echo "  cd /opt/luminaz/app && runuser -u luminaz -- /opt/luminaz/venv/bin/python manage.py create-admin you@example.com"
echo "Then point Apache at port 8000 (deploy/apache-proxy.conf.example)."
