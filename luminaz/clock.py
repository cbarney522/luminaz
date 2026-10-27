"""The app's own clock (change 30, 22 October 2026).

Why: on Render and Railway a scheduled "cron job" runs in its own container, which cannot open the
web service's instance disk, so `manage.py daily` and `manage.py report` would start there, find no
database, and do nothing: no invoices, no education emails, no backups, no 7 pm report. Running the
schedule inside the web service needs nothing from the host.

How: every web worker starts one background thread at boot. Every few minutes it asks the
database whether anything is due. The daily job runs once a day at or after `daily_job_hour`
(Settings, 6 = 6 am on the server's clock; set TZ=America/New_York on the host). The evening
report is tried every tick and sends itself once, at or after its own hour (jobs.daily_summary).
Two workers never run the same thing twice: the first to update the day stamp in the settings
table wins (SQLite serialises writes), the other sees the stamp already set and skips.

Off under tests and whenever LUMINAZ_CLOCK=0 (manage.py sets that, because it runs the jobs
itself). The "Run daily tasks" button and the manage.py commands keep working as before.
"""
import datetime as dt
import os
import threading
import time

from .db import get_db, setting

TICK_SECONDS = 300
_started = {}


def enabled(app):
    return not app.config.get("TESTING") and os.environ.get("LUMINAZ_CLOCK", "1") == "1"


def start(app):
    """Start the clock thread for this process, once. Returns the thread, or None when off."""
    if not enabled(app) or _started.get(id(app)):
        return None
    t = threading.Thread(target=_loop, args=(app,), name="luminaz-clock", daemon=True)
    _started[id(app)] = t
    t.start()
    return t


def _loop(app):
    time.sleep(10)                      # let the worker finish booting before the first look
    while True:
        try:
            tick(app)
        except Exception:               # a failed tick must never kill the clock
            app.logger.exception("clock tick failed")
        time.sleep(TICK_SECONDS)


def _claim(db, key, day):
    """True for exactly one caller per day: an atomic compare-and-set on a settings row."""
    db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, '')", (key,))
    cur = db.execute("UPDATE settings SET value = ? WHERE key = ? AND value != ?", (day, key, day))
    db.commit()
    return cur.rowcount == 1


def job_hour():
    try:
        h = int(setting("daily_job_hour", "6"))
    except (TypeError, ValueError):
        return 6
    return h if 0 <= h <= 23 else 6


def tick(app, at=None):
    """Run whatever is due at `at` (default: now). Returns what ran: {"daily": 0/1, "report": 0/1}."""
    from . import jobs
    at = at or dt.datetime.now()
    day = at.date().isoformat()
    out = {"daily": 0, "report": 0}
    # url_for(_external=True) needs a request context to build full URLs.
    # We push a fake one here so jobs.py can construct email links without a live request.
    # The base_url is derived from the stored investor_host setting (falling back to localhost).
    with app.app_context():
        scheme = "https" if os.environ.get("LUMINAZ_HTTPS") else "http"
        host = setting("investor_host", "") or "127.0.0.1:5000"
        base_url = "%s://%s/" % (scheme, host)
    with app.test_request_context("/", base_url=base_url):
        db = get_db()
        if at.hour >= job_hour() and _claim(db, "clock_daily_last", day):
            jobs.run_all(at=at)
            out["daily"] = 1
        if at.hour >= jobs.report_hour() and setting("daily_summary", "1") == "1" and _claim(db, "clock_report_last", day):
            out["report"] = jobs.daily_summary(at=at)
            db.commit()
    return out


def status():
    """For the Settings page: when the clock last ran each thing."""
    return {"daily": setting("clock_daily_last", "") or "never", "report": setting("clock_report_last", "") or "never",
            "on": os.environ.get("LUMINAZ_CLOCK", "1") == "1"}
