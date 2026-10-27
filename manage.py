"""Admin chores.
  py -3 manage.py create-admin you@example.com        create (or reset) an admin account
  py -3 manage.py daily                                the daily job: billing, education emails, nudges, follow-ups, backup
  py -3 manage.py report                               the evening report by email; schedule it every hour, it sends once, at 7 pm
  py -3 manage.py report now                           send that report right away (still only once a day)
  py -3 manage.py run-billing                          billing only
  py -3 manage.py backup                               copy the database + documents to instance/backups
  py -3 manage.py restore instance/backups/<file>      put a backup back (stop the app first)
  py -3 manage.py demo                                 load sample data to click around
  py -3 manage.py setting require_admin_2fa 0          change one setting from the command line (for the few that
                                                       lock you out of the Settings page, like two-step sign-in)
"""
import getpass, os, sys
os.environ.setdefault("LUMINAZ_CLOCK", "0")    # the commands below run the jobs themselves; no clock thread here (change 30)
from luminaz import create_app
from luminaz.db import get_db, now
from werkzeug.security import generate_password_hash

app = create_app()

def create_admin(email):
    pw = getpass.getpass("Password for %s (10+ chars): " % email)
    if len(pw) < 10:
        print("Too short."); return 1
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if row:
            db.execute("UPDATE users SET password_hash = ?, role = 'admin', email_confirmed = 1 WHERE id = ?", (generate_password_hash(pw), row["id"]))
        else:
            db.execute("INSERT INTO users(email, password_hash, role, name, email_confirmed, created_at) VALUES (?, ?, 'admin', 'Luminaz admin', 1, ?)",
                       (email.lower(), generate_password_hash(pw), now()))
        db.commit()
    print("Admin ready:", email); return 0

def run_billing():
    from luminaz import billing
    with app.app_context():
        print(billing.run_billing())
    return 0

def daily():
    from luminaz import jobs
    with app.app_context(), app.test_request_context(base_url=_base_url()):
        print(jobs.run_all())
    return 0

def report(right_now=False):
    from luminaz import jobs
    with app.app_context():
        sent = jobs.daily_summary(force=right_now)
        hour = jobs.report_hour()
    print("Evening report sent." if sent else
          "Nothing sent. The report goes out once a day, at or after %d:00 on this computer's clock, "
          "and only while it is switched on in Settings." % hour)
    return 0

def backup():
    from luminaz import jobs
    with app.app_context():
        print("Backup written:", jobs.backup())
    return 0

def restore(path):
    from luminaz import jobs
    with app.app_context():
        print("Restored", path, "->", jobs.restore(path))
    return 0

def _base_url():
    """Links in emails sent from the command line need a host name."""
    import os
    from luminaz.db import setting
    with app.app_context():
        host = os.environ.get("LUMINAZ_PUBLIC_HOST") or setting("investor_host", "") or "127.0.0.1:5000"
    scheme = "https" if app.config.get("PREFERRED_URL_SCHEME") == "https" or os.environ.get("LUMINAZ_HTTPS") else "http"
    return "%s://%s/" % (scheme, host)

def set_one(key, value):
    from luminaz.db import DEFAULT_SETTINGS, set_setting, setting
    if key not in DEFAULT_SETTINGS:
        print("Unknown setting. Known:", ", ".join(sorted(DEFAULT_SETTINGS))); return 1
    with app.app_context():
        set_setting(key, value)
        print("%s = %s" % (key, setting(key)))
    return 0

def demo():
    from tests.demo_data import load
    with app.app_context():
        load()
    print("Demo data loaded. Sign in as admin@luminaz.test / manager@luminaz.test / investor@luminaz.test, password: luminaz-demo-2026")
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create-admin" and len(sys.argv) > 2: sys.exit(create_admin(sys.argv[2]))
    if cmd == "run-billing": sys.exit(run_billing())
    if cmd == "daily": sys.exit(daily())
    if cmd == "report": sys.exit(report(right_now=sys.argv[2:3] == ["now"]))
    if cmd == "backup": sys.exit(backup())
    if cmd == "restore" and len(sys.argv) > 2: sys.exit(restore(sys.argv[2]))
    if cmd == "demo": sys.exit(demo())
    if cmd == "setting" and len(sys.argv) > 3: sys.exit(set_one(sys.argv[2], sys.argv[3]))
    print(__doc__); sys.exit(1)
