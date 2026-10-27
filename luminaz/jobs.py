"""The daily job. Run once a day in production (`py -3 manage.py daily`, or the
admin's "Run daily tasks" button). Everything here is idempotent: running it
twice in a day does nothing the second time.

  1. Billing: issue this month's invoices, pause late funds, resume paid ones.
  2. Education sequence: send the next weekly email to calculator leads.
  3. Request nudges: remind managers of material requests untouched for N days.
  4. Outreach follow-ups: send the second email to managers who did not reply.
  5. Marketing posts: draft this week's and next week's three posts for approval;
     send the approved ones whose day has come (webhook or email).
  5b. Webinars: the reminder the day before and the replay afterwards, only once the
     attorney has approved (Settings: attorney_approved).
  6. Backup: copy the database to instance/backups, keep the last 30.
  7. Numbers for the founders: on Mondays, last week's; and the evening report, which
     is also run on its own every hour (`py -3 manage.py report`) so that it goes out
     at the hour set in Settings whatever time the rest of this job runs.
"""
import datetime as dt
import os
import secrets
import shutil
import sqlite3

from flask import current_app, url_for

from .db import get_db, now, audit, setting
from . import billing, mail, marketing, metrics
from .content.education import EMAILS


def run_all(admin_id=None, at=None):
    """`at` is the moment the job runs (default: now); only the evening report looks at the hour."""
    out = {"billing": billing.run_billing(admin_id=admin_id)}
    out["line_filled"] = billing.fill_slots()      # safety net: anything in line that fits an open slot goes live (change 27)
    out["education"] = send_education()
    out["catalog_open_notices"] = send_catalog_open_notices()
    out["nudges"] = nudge_managers()
    out["outreach_followups"] = outreach_followups()
    out["posts_drafted"] = marketing.plan_posts()
    out["posts_sent"] = marketing.publish_posts()
    from . import webinars
    out["webinar_reminders"] = webinars.send_reminders()
    out["webinar_replays"] = webinars.send_replays()
    out["weekly_summary"] = weekly_summary()
    out["daily_summary"] = daily_summary(at=at)
    out["backup"] = backup()
    out["offsite"] = current_app.config.get("LAST_OFFSITE", "off")
    audit("daily_job", out, user_id=admin_id)
    get_db().commit()
    return out


# ---------------------------------------------------------------- education sequence

def _first_name(email):
    local = email.split("@")[0]
    part = local.replace(".", " ").replace("_", " ").split(" ")[0]
    return part.capitalize() if part.isalpha() and len(part) > 1 else "there"


def send_education(as_of=None):
    """One email per lead per week, in order. Accredited leads only; not-accredited
    leads got their single result email and nothing more."""
    db = get_db()
    if mail.marketing_block():
        return 0            # section 5: nothing to real people until the attorney approves; the sequence waits where it is
    as_of = as_of or dt.datetime.now(dt.timezone.utc)
    week_ago = (as_of - dt.timedelta(days=7)).replace(microsecond=0).isoformat()
    due = db.execute("SELECT l.* FROM calculator_leads l WHERE l.result = 'accredited' AND l.unsubscribed = 0"
                     " AND l.sequence_step < ? AND (l.last_sent_at IS NULL OR l.last_sent_at <= ?)"
                     " AND l.email NOT IN (SELECT email FROM suppressions)"
                     " AND l.email NOT IN (SELECT email FROM users WHERE marketing_opt_in = 0)", (len(EMAILS), week_ago)).fetchall()
    sent = 0
    seen = set()
    for lead in due:
        if lead["email"] in seen:
            continue
        seen.add(lead["email"])
        token = lead["unsub_token"]
        if not token:
            token = secrets.token_urlsafe(24)
            db.execute("UPDATE calculator_leads SET unsub_token = ? WHERE email = ?", (token, lead["email"]))
        e = EMAILS[lead["sequence_step"]]
        body = e["body"].format(first_name=_first_name(lead["email"]),
                                unsubscribe_url=url_for("support.unsubscribe", token=token, _external=True),
                                calculator_url=url_for("investor.home", _external=True))
        mail.send(lead["email"], e["subject"], body, kind="marketing", unsubscribe_url=url_for("support.unsubscribe", token=token, _external=True))
        db.execute("UPDATE calculator_leads SET sequence_step = sequence_step + 1, last_sent_at = ? WHERE email = ?",
                   (as_of.replace(microsecond=0).isoformat(), lead["email"]))
        sent += 1
    db.commit()
    return sent


# ---------------------------------------------------------------- the catalog-open note

def send_catalog_open_notices(limit=500):
    """The one email the calculator pages promise: "we'll email you the day it opens". Once the
    catalog has opened, each calculator lead who appears accredited, has not unsubscribed, and has
    not had it yet gets a single note with the sign-up link. Marketing rules apply: held until the
    attorney approves, never to a suppressed address, postal address and unsubscribe link on it.
    At most `limit` a day so a big list goes out over a few mornings."""
    db = get_db()
    if mail.marketing_block() or billing.catalog_opened(record=False) is None:
        return 0
    due = db.execute("SELECT * FROM calculator_leads WHERE result = 'accredited' AND unsubscribed = 0 AND catalog_notified_at IS NULL"
                     " AND email NOT IN (SELECT email FROM suppressions)"
                     " AND email NOT IN (SELECT email FROM users WHERE marketing_opt_in = 0 OR role != 'investor')"
                     " ORDER BY created_at LIMIT ?", (limit,)).fetchall()
    sent = 0
    seen = set()
    for lead in due:
        if lead["email"] in seen:
            continue
        seen.add(lead["email"])
        token = lead["unsub_token"]
        if not token:
            token = secrets.token_urlsafe(24)
            db.execute("UPDATE calculator_leads SET unsub_token = ? WHERE email = ?", (token, lead["email"]))
        unsub = url_for("support.unsubscribe", token=token, _external=True)
        result = mail.send(lead["email"], "The Luminaz catalog is open",
                           "Hi %s,\n\nYou took the accredited investor calculator and asked to hear when the Luminaz catalog opened. "
                           "It is open today.\n\nCreate your free account and browse the funds, listed in the order they arrived, no "
                           "ranking and no fees for investors:\n%s\n\nA fund manager verifies your accredited status before any investment; "
                           "Luminaz is not part of that step.\n\n%s"
                           % (_first_name(lead["email"]), url_for("investor.signup", _external=True), setting("founder_name", "Diane")),
                           kind="marketing", unsubscribe_url=unsub)
        if result in ("held", "suppressed"):
            continue
        db.execute("UPDATE calculator_leads SET catalog_notified_at = ? WHERE email = ?", (now(), lead["email"]))
        sent += 1
    db.commit()
    return sent


# ---------------------------------------------------------------- request nudges

def nudge_managers(as_of=None):
    db = get_db()
    days = int(setting("request_nudge_days", "3"))
    cutoff = ((as_of or dt.datetime.now(dt.timezone.utc)) - dt.timedelta(days=days)).replace(microsecond=0).isoformat()
    stale = db.execute(
        "SELECT r.id, r.created_at, f.name AS fund_name, f.id AS fund_id, u.email AS manager_email, u.name AS manager_name"
        " FROM requests r JOIN funds f ON f.id = r.fund_id JOIN firms m ON m.id = f.firm_id JOIN users u ON u.id = m.owner_user_id"
        " WHERE r.status = 'new' AND r.created_at <= ? AND (r.updated_at IS NULL OR r.updated_at < r.created_at)", (cutoff,)).fetchall()
    by_manager = {}
    for r in stale:
        by_manager.setdefault(r["manager_email"], []).append(r)
    for email, rows in by_manager.items():
        lines = "\n".join("- %s (requested %s): %s" % (r["fund_name"], r["created_at"][:10],
                                                       url_for("manager.fund_detail", fund_id=r["fund_id"], _external=True)) for r in rows)
        mail.send(email, "Luminaz: %d investor request%s waiting on you" % (len(rows), "" if len(rows) == 1 else "s"),
                  "Hello %s,\n\nThese material requests have been open for more than %d days with no update:\n\n%s\n\n"
                  "Investors who hear nothing stop requesting. Please contact them and move the stage in your pipeline.\n\n%s"
                  % (rows[0]["manager_name"], days, lines, setting("company_name")))
        for r in rows:
            db.execute("UPDATE requests SET updated_at = ? WHERE id = ?", (now(), r["id"]))
    db.commit()
    return len(by_manager)


# ---------------------------------------------------------------- outreach follow-ups

FOLLOWUP = """Hi {first},

Bumping this once. If the answer is no, that's useful too: I'd rather hear why than guess. If it's "not yet," I'll check back when the catalog is live.

{founder}
Luminaz"""


def outreach_followups(as_of=None):
    """Rule 4.7: the daily job drafts, it never sends. After outreach_followup_days with no reply,
    the follow-up is written onto the lead and the lead goes to the top of the outreach desk, where
    a founder reads it and clicks "Approve and send follow-up" (admin.outreach_lead)."""
    db = get_db()
    days = int(setting("outreach_followup_days", "5"))
    cutoff = ((as_of or dt.datetime.now(dt.timezone.utc)) - dt.timedelta(days=days)).replace(microsecond=0).isoformat()
    due = db.execute("SELECT * FROM outreach WHERE status = 'sent' AND sent_at <= ? AND followup_sent_at IS NULL AND email != ''"
                     " AND email NOT IN (SELECT email FROM suppressions)", (cutoff,)).fetchall()
    for o in due:
        first = (o["contact_name"] or "there").split(" ")[0]
        db.execute("UPDATE outreach SET status = 'followup_drafted', followup_body = ?, updated_at = ? WHERE id = ?",
                   (FOLLOWUP.format(first=first, founder=setting("founder_name", "Diane Barney")), now(), o["id"]))
    db.commit()
    return len(due)


# ---------------------------------------------------------------- Monday numbers

def weekly_summary(today=None):
    """On Mondays, email last week's numbers to the founders (post_notify_email, else support_email).
    Also trims page_views older than 13 months. Returns 1 if sent."""
    db = get_db()
    today = today or dt.date.today()
    if today.weekday() != 0:
        return 0
    marker = '"week": "%s"' % (today - dt.timedelta(days=7)).isoformat()
    if db.execute("SELECT 1 FROM audit WHERE action = 'weekly_summary' AND detail LIKE ?", ("%" + marker + "%",)).fetchone():
        return 0
    subject, body = metrics.summary(today=today - dt.timedelta(days=1))
    mail.send(setting("post_notify_email", "") or setting("support_email"), subject, body)
    db.execute("DELETE FROM page_views WHERE day < ?", ((today - dt.timedelta(days=395)).isoformat(),))
    audit("weekly_summary", {"week": (today - dt.timedelta(days=7)).isoformat()})
    db.commit()
    return 1


# ---------------------------------------------------------------- the evening report

def report_hour():
    """The hour the evening report goes out, 0 to 23 on this computer's clock, from Settings.
    Anything that is not such a number means 19 (7 pm), the hour Diane asked for."""
    try:
        hour = int(setting("daily_summary_hour", "19"))
    except (TypeError, ValueError):
        return 19
    return hour if 0 <= hour <= 23 else 19


def daily_summary(at=None, force=False):
    """Each evening, email the founders how the day went: today's numbers so far, what is waiting on
    them, and the totals (to post_notify_email, else support_email). Sent once per day, at or after
    report_hour(), and only while the daily_summary setting is 1. `at` is the moment it runs
    (default: now). force=True skips the wait for the hour, for `manage.py report now`; it still
    sends only once a day and never while switched off. Returns 1 if sent."""
    db = get_db()
    if setting("daily_summary", "1") != "1":
        return 0
    at = at or dt.datetime.now()
    if not force and at.hour < report_hour():
        return 0
    day = at.date().isoformat()
    marker = '"day": "%s"' % day
    if db.execute("SELECT 1 FROM audit WHERE action = 'daily_summary' AND detail LIKE ?", ("%" + marker + "%",)).fetchone():
        return 0
    subject, body = metrics.daily_text(at=at)
    mail.send(setting("post_notify_email", "") or setting("support_email"), subject, body)
    audit("daily_summary", {"day": day})
    db.commit()
    return 1


# ---------------------------------------------------------------- backup

def backup(keep=30):
    src = current_app.config["DATABASE"]
    if not os.path.exists(src):
        return None
    folder = os.path.join(current_app.instance_path, "backups")
    os.makedirs(folder, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(folder, "luminaz-%s.sqlite" % stamp)
    # sqlite's own backup API copies a consistent snapshot even while the app is running
    with sqlite3.connect(src) as s, sqlite3.connect(dest) as d:
        s.backup(d)
    docs = os.path.join(current_app.instance_path, "documents")
    docs_zip = None
    if os.path.isdir(docs):
        docs_zip = shutil.make_archive(dest[:-7] + "-documents", "zip", docs)
    # Finding 12: the privacy policy promises an off-server copy. When Settings names a folder that is
    # synced or mounted elsewhere (OneDrive, Dropbox, a mounted drive), the newest backup is copied there.
    copy_dir = (setting("backup_copy_dir", "") or "").strip()
    if copy_dir and os.path.isdir(copy_dir):
        shutil.copy2(dest, os.path.join(copy_dir, os.path.basename(dest)))
        if docs_zip:
            shutil.copy2(docs_zip, os.path.join(copy_dir, os.path.basename(docs_zip)))
    # Change 31: the off-server copy a cloud host can make: an S3-compatible bucket, when Cliff has
    # typed its five settings into the host (see offsite.py). Logged, never fatal.
    from . import offsite
    try:
        current_app.config["LAST_OFFSITE"] = offsite.upload_backup([dest, docs_zip], keep=keep)
    except Exception as e:
        current_app.config["LAST_OFFSITE"] = "failed (%s)" % e.__class__.__name__
        current_app.logger.exception("off-server backup failed")
    files = sorted(f for f in os.listdir(folder) if f.startswith("luminaz-") and f.endswith(".sqlite"))
    for old in files[:-keep]:
        os.remove(os.path.join(folder, old))
        z = os.path.join(folder, old[:-7] + "-documents.zip")
        if os.path.exists(z):
            os.remove(z)
    return dest


def restore(path):
    """Replace the live database with a backup. Stop the app first."""
    dest = current_app.config["DATABASE"]
    shutil.copy2(dest, dest + ".before-restore")
    shutil.copy2(path, dest)
    return dest
