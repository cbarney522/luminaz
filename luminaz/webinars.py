"""Webinars: the sign-up page Diane chose as the way to collect investor contacts (9 October 2026),
and the fund manager webinar from Launch Tasks Block 4C.

What it does: a public list of open webinars, a sign-up form (name, email, recorded consent, the
?src= tag), a confirmation email with a personal join link that records who joined, a reminder
the day before, a replay email afterwards, and an admin page to create webinars and mark who
attended. Zoom only hosts the call; Diane pastes the meeting link in.

The lock (AGENTS.md section 5, Diane's rule): nothing webinar-related reaches real people until
the attorney has approved the terms and privacy policy. The Settings switch `attorney_approved`
keeps the public pages closed and the emails unsent until it is 1. Admins can preview everything
while it is 0.
"""
import datetime as dt
import secrets

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from .auth import login_required
from .db import get_db, now, audit, setting
from . import mail

bp = Blueprint("webinars", __name__)

CONSENT_WEBINAR = ("I agree to receive the details of this webinar, a reminder, the replay, and ongoing educational emails from "
                   "Luminaz. I can unsubscribe at any time using the link in every email.")


def approved():
    return setting("attorney_approved", "0") == "1"


def _admin():
    return bool(g.user and g.user["role"] == "admin")


def _open(w):
    return w["status"] == "open"


def counts(webinar_id):
    db = get_db()
    r = db.execute("SELECT COUNT(*) AS registered, SUM(joined_at IS NOT NULL) AS joined, SUM(attended) AS attended"
                   " FROM webinar_registrations WHERE webinar_id = ?", (webinar_id,)).fetchone()
    return {"registered": r["registered"] or 0, "joined": r["joined"] or 0, "attended": r["attended"] or 0}


# ---------------------------------------------------------------- public

@bp.route("/webinars")
def index():
    db = get_db()
    if not approved() and not _admin():
        return render_template("webinars/soon.html")
    rows = db.execute("SELECT * FROM webinars WHERE status = 'open' ORDER BY starts_at ASC").fetchall()
    return render_template("webinars/index.html", webinars=rows, preview=not approved())


@bp.route("/webinars/<int:webinar_id>", methods=("GET", "POST"))
def signup(webinar_id):
    db = get_db()
    w = db.execute("SELECT * FROM webinars WHERE id = ?", (webinar_id,)).fetchone()
    if not w or (not _open(w) and not _admin()):
        abort(404)
    if not approved() and not _admin():
        return render_template("webinars/soon.html")
    if request.method == "POST":
        if not approved():
            flash("Sign-ups are locked until the attorney approves the terms. You are seeing a preview.", "error")
            return redirect(url_for("webinars.signup", webinar_id=webinar_id))
        name = request.form.get("name", "").strip()[:120]
        email = request.form.get("email", "").strip().lower()
        if not name or "@" not in email:
            flash("Your name and a working email, please.", "error")
            return render_template("webinars/signup.html", w=w, name=name, email=email)
        if not request.form.get("consent"):
            flash("Please tick the box agreeing to receive the webinar details and emails.", "error")
            return render_template("webinars/signup.html", w=w, name=name, email=email)
        existing = db.execute("SELECT * FROM webinar_registrations WHERE webinar_id = ? AND email = ?", (webinar_id, email)).fetchone()
        if existing:
            return render_template("webinars/registered.html", w=w, reg=existing, again=True)
        token = "w" + secrets.token_urlsafe(24)
        source = (request.args.get("src") or session.get("src", "") or "")[:40].lower()
        db.execute("INSERT INTO webinar_registrations(webinar_id, name, email, source, consent_at, consent_text, token, created_at, campaign)"
                   " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (webinar_id, name, email, source, now(), CONSENT_WEBINAR, token, now(), (session.get("campaign") or "")[:12]))
        audit("webinar_registered", {"webinar_id": webinar_id, "source": source})
        db.commit()
        reg = db.execute("SELECT * FROM webinar_registrations WHERE token = ?", (token,)).fetchone()
        note = ""
        if mail.suppressed(email):
            # Rule 4.8: this address asked not to be emailed. The registration stands and the join link
            # is in this (transactional) email; the reminder and replay go only if they confirm.
            from .support import send_resubscribe_link
            send_resubscribe_link(email, what="the reminder, the replay and our other emails")
            note = ("\n\nThis address had unsubscribed from Luminaz emails, so the reminder and the replay will not be sent "
                    "unless you confirm with the separate email we have just sent you.")
        mail.send(email, "You're registered: %s" % w["title"],
                  "Hi %s,\n\nYou're registered for \"%s\" on %s.\n\nYour personal link to join (please don't share it):\n%s\n\n"
                  "We'll send a reminder the day before and the replay afterwards.%s\n\nTo stop these emails: %s\n\n%s"
                  % (name.split(" ")[0], w["title"], when(w), url_for("webinars.join", webinar_id=webinar_id, token=token, _external=True),
                     note, url_for("support.unsubscribe", token=token, _external=True), setting("company_name")))
        return render_template("webinars/registered.html", w=w, reg=reg, again=False)
    return render_template("webinars/signup.html", w=w, name="", email="", preview=not approved())


@bp.route("/webinars/<int:webinar_id>/join/<token>")
def join(webinar_id, token):
    """The personal link in every email. Records that this person joined, then sends them to Zoom."""
    db = get_db()
    reg = db.execute("SELECT * FROM webinar_registrations WHERE webinar_id = ? AND token = ?", (webinar_id, token)).fetchone()
    w = db.execute("SELECT * FROM webinars WHERE id = ?", (webinar_id,)).fetchone()
    if not reg or not w:
        abort(404)
    if not reg["joined_at"]:
        db.execute("UPDATE webinar_registrations SET joined_at = ? WHERE id = ?", (now(), reg["id"]))
        db.commit()
    if not w["zoom_url"]:
        return render_template("webinars/registered.html", w=w, reg=reg, again=True, no_link=True)
    return redirect(w["zoom_url"])


def when(w):
    try:
        d = dt.datetime.fromisoformat(w["starts_at"])
        return d.strftime("%A %d %B %Y at %I:%M %p").replace(" 0", " ")
    except ValueError:
        return w["starts_at"]


# ---------------------------------------------------------------- admin

@bp.route("/admin/webinars", methods=("GET", "POST"))
@login_required("admin")
def admin_index():
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        starts = request.form.get("starts_at", "").strip()
        audience = request.form.get("audience", "investors")
        if not title or not starts or audience not in ("investors", "managers"):
            flash("A title, a date and time, and the audience are needed.", "error")
        else:
            db.execute("INSERT INTO webinars(title, audience, starts_at, zoom_url, description, status, created_at) VALUES (?, ?, ?, ?, ?, 'draft', ?)",
                       (title, audience, starts, request.form.get("zoom_url", "").strip(), request.form.get("description", "").strip(), now()))
            audit("webinar_created", {"title": title}, user_id=g.user["id"])
            db.commit()
            flash("Webinar created as a draft. Open it, check the details, then set it to open.", "ok")
        return redirect(url_for("webinars.admin_index"))
    rows = db.execute("SELECT * FROM webinars ORDER BY starts_at DESC").fetchall()
    return render_template("admin/webinars.html", webinars=[(w, counts(w["id"])) for w in rows], approved=approved())


@bp.route("/admin/webinars/<int:webinar_id>", methods=("GET", "POST"))
@login_required("admin")
def admin_webinar(webinar_id):
    db = get_db()
    w = db.execute("SELECT * FROM webinars WHERE id = ?", (webinar_id,)).fetchone()
    if not w:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            status = request.form.get("status", w["status"])
            if status not in ("draft", "open", "done"):
                status = w["status"]
            db.execute("UPDATE webinars SET title = ?, audience = ?, starts_at = ?, zoom_url = ?, replay_url = ?, description = ?, status = ? WHERE id = ?",
                       (request.form.get("title", w["title"]).strip() or w["title"], request.form.get("audience", w["audience"]),
                        request.form.get("starts_at", w["starts_at"]).strip() or w["starts_at"], request.form.get("zoom_url", "").strip(),
                        request.form.get("replay_url", "").strip(), request.form.get("description", "").strip(), status, webinar_id))
            audit("webinar_saved", {"webinar_id": webinar_id, "status": status}, user_id=g.user["id"])
            flash("Saved.", "ok")
        elif action == "attended":
            ids = {int(x) for x in request.form.getlist("attended") if x.isdigit()}
            regs = db.execute("SELECT id FROM webinar_registrations WHERE webinar_id = ?", (webinar_id,)).fetchall()
            for r in regs:
                db.execute("UPDATE webinar_registrations SET attended = ? WHERE id = ?", (1 if r["id"] in ids else 0, r["id"]))
            audit("webinar_attendance", {"webinar_id": webinar_id, "attended": len(ids)}, user_id=g.user["id"])
            flash("Attendance saved.", "ok")
        db.commit()
        return redirect(url_for("webinars.admin_webinar", webinar_id=webinar_id))
    regs = db.execute("SELECT * FROM webinar_registrations WHERE webinar_id = ? ORDER BY created_at DESC", (webinar_id,)).fetchall()
    by_source = db.execute("SELECT COALESCE(NULLIF(source,''),'(direct)') AS src, COUNT(*) AS n FROM webinar_registrations WHERE webinar_id = ? GROUP BY src ORDER BY n DESC", (webinar_id,)).fetchall()
    return render_template("admin/webinar.html", w=w, regs=regs, c=counts(webinar_id), by_source=by_source, approved=approved(),
                           signup_url=url_for("webinars.signup", webinar_id=webinar_id, _external=True))


# ---------------------------------------------------------------- the daily job's part

def _sendable(email):
    return not mail.suppressed(email)


def send_reminders(as_of=None):
    """The day before: one reminder per registrant, with the personal join link. Only once the
    attorney has approved (Settings), and never to a suppressed address."""
    if not approved():
        return 0
    db = get_db()
    as_of = as_of or dt.datetime.now()
    sent = 0
    for w in db.execute("SELECT * FROM webinars WHERE status = 'open'").fetchall():
        try:
            starts = dt.datetime.fromisoformat(w["starts_at"])
        except ValueError:
            continue
        # "Tomorrow" means the calendar day before the webinar, whatever hour the daily job runs
        # (6:15 am in DEPLOY.md). A webinar later today that was never reminded gets it too.
        if starts.date() not in (as_of.date() + dt.timedelta(days=1), as_of.date()) or starts < as_of:
            continue
        for reg in db.execute("SELECT * FROM webinar_registrations WHERE webinar_id = ? AND reminded_at IS NULL", (w["id"],)).fetchall():
            if not _sendable(reg["email"]):
                continue
            unsub = url_for("support.unsubscribe", token=reg["token"], _external=True)
            mail.send(reg["email"], "Tomorrow: %s" % w["title"],
                      "Hi %s,\n\n\"%s\" is on %s.\n\nYour personal link to join:\n%s\n\nSee you there.\n\n%s"
                      % ((reg["name"] or "there").split(" ")[0], w["title"], when(w),
                         url_for("webinars.join", webinar_id=w["id"], token=reg["token"], _external=True), setting("founder_name", "Diane")),
                      kind="marketing", unsubscribe_url=unsub)
            db.execute("UPDATE webinar_registrations SET reminded_at = ? WHERE id = ?", (now(), reg["id"]))
            sent += 1
    db.commit()
    return sent


def send_replays():
    """After a webinar is marked done and has a replay link: the replay to everyone registered,
    once. No-shows get it too; that was the plan."""
    if not approved():
        return 0
    db = get_db()
    sent = 0
    for w in db.execute("SELECT * FROM webinars WHERE status = 'done' AND replay_url != ''").fetchall():
        for reg in db.execute("SELECT * FROM webinar_registrations WHERE webinar_id = ? AND replay_sent_at IS NULL", (w["id"],)).fetchall():
            if not _sendable(reg["email"]):
                continue
            unsub = url_for("support.unsubscribe", token=reg["token"], _external=True)
            mail.send(reg["email"], "Replay: %s" % w["title"],
                      "Hi %s,\n\nThe replay of \"%s\" is here:\n%s\n\nQuestions? Reply to this email.\n\n%s"
                      % ((reg["name"] or "there").split(" ")[0], w["title"], w["replay_url"], setting("founder_name", "Diane")),
                      kind="marketing", unsubscribe_url=unsub)
            db.execute("UPDATE webinar_registrations SET replay_sent_at = ? WHERE id = ?", (now(), reg["id"]))
            sent += 1
    db.commit()
    return sent
