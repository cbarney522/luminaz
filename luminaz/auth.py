"""Sign-up, sign-in, email confirmation, role guards."""
import datetime as dt
import functools
import secrets

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for, abort, current_app)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, now, audit, setting
from . import mail
from . import twofactor

bp = Blueprint("auth", __name__)

ACCREDITATION_BASES = [
    ("income", "Income: over $200,000 in each of the last two years ($300,000 with a spouse or partner), and I expect the same this year"),
    ("net_worth", "Net worth: over $1,000,000, alone or with a spouse or partner, not counting my primary home"),
    ("license", "Professional license: I hold a Series 7, 65, or 82 license in good standing"),
    ("entity", "Qualifying entity: I am investing through an entity that meets the SEC's accredited investor definition"),
]


def login_required(role=None):
    def deco(view):
        @functools.wraps(view)
        def wrapped(**kw):
            if g.user is None:
                return redirect(url_for("auth.login", next=request.path))
            if role and g.user["role"] != role and g.user["role"] != "admin":
                abort(403)
            if role == "admin" and g.user["role"] != "admin":
                abort(403)
            if role == "admin" and not g.user["totp_enabled"] and setting("require_admin_2fa", "1") == "1":
                # Finding 12: the privacy policy promises admin access needs two-step sign-in. An admin
                # without it is sent to set it up before any admin page opens.
                flash("Set up two-step sign-in before using the review desk. It takes two minutes with any authenticator app.", "error")
                return redirect(url_for("auth.security"))
            return view(**kw)
        return wrapped
    return deco


def _home_for(user):
    return {"admin": "admin.queue", "manager": "manager.dashboard"}.get(user["role"], "investor.catalog")


MAX_FAILURES = 8          # per email or address in the window
FAILURE_WINDOW_MIN = 15


def _too_many_failures(email):
    """Brute-force guard: after MAX_FAILURES wrong passwords for an email (or from an address)
    in FAILURE_WINDOW_MIN minutes, sign-in for that email pauses until the window passes."""
    db = get_db()
    import datetime as dt
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=FAILURE_WINDOW_MIN)).replace(microsecond=0).isoformat()
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()
    n = db.execute("SELECT COUNT(*) FROM audit WHERE action = 'login_failed' AND at >= ? AND (detail LIKE ? OR detail LIKE ?)",
                   (cutoff, '%"email": "' + email + '"%', '%"ip": "' + ip + '"%')).fetchone()[0]
    return n >= MAX_FAILURES


def safe_next(nxt):
    """Only a path on this site may follow a sign-in. '//evil.example' and 'https://...' are refused
    (HANDOFF finding 7): a link could otherwise bounce a person to another website right after
    they typed their password."""
    from urllib.parse import urlsplit
    if not nxt or not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/\\"):
        return None
    parts = urlsplit(nxt)
    if parts.scheme or parts.netloc:
        return None
    return nxt


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()
        if _too_many_failures(email):
            flash("Too many sign-in attempts. Wait %d minutes and try again, or reset your password." % FAILURE_WINDOW_MIN, "error")
            return render_template("auth/login.html"), 429
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], request.form["password"]):
            audit("login_failed", {"email": email, "ip": ip})
            get_db().commit()
            flash("That email and password don't match.", "error")
        elif not user["email_confirmed"]:
            flash("Please confirm your email first. Check your inbox for the link.", "error")
        elif user["role"] == "admin" and user["totp_enabled"]:
            session.clear()
            session["pending_2fa_user"] = user["id"]
            session["pending_next"] = request.args.get("next")
            session["pending_2fa_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            session["pending_2fa_fails"] = 0
            return redirect(url_for("auth.second_step"))
        else:
            _complete_login(user)
            nxt = safe_next(request.args.get("next"))
            return redirect(nxt or url_for(_home_for(user)))
    return render_template("auth/login.html")


def _complete_login(user):
    session.clear()
    session["user_id"] = user["id"]
    get_db().execute("UPDATE users SET last_login = ? WHERE id = ?", (now(), user["id"]))
    audit("login", user_id=user["id"])
    get_db().commit()


@bp.route("/login/verify", methods=("GET", "POST"))
def second_step():
    uid = session.get("pending_2fa_user")
    if not uid:
        return redirect(url_for("auth.login"))
    # The half-finished sign-in lasts SECOND_STEP_MINUTES and allows SECOND_STEP_TRIES wrong codes;
    # then it is thrown away and the password has to be typed again (a six-digit code can be guessed).
    started = session.get("pending_2fa_at")
    try:
        too_old = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(started) > dt.timedelta(minutes=SECOND_STEP_MINUTES)
    except (TypeError, ValueError):
        too_old = True
    if too_old:
        _drop_pending()
        flash("That sign-in took too long. Please sign in again.", "error")
        return redirect(url_for("auth.login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if request.method == "POST":
        code = request.form.get("code", "")
        secret = twofactor.decrypt(user["totp_secret"], current_app.config["SECRET_KEY"])
        ok = twofactor.verify(secret, code)
        if not ok:
            remaining = twofactor.use_recovery_code(user["recovery_codes"], code)
            if remaining is not None:
                db.execute("UPDATE users SET recovery_codes = ? WHERE id = ?", (remaining, uid))
                audit("recovery_code_used", user_id=uid)
                ok = True
        if ok:
            nxt = safe_next(session.get("pending_next"))
            _complete_login(user)
            return redirect(nxt or url_for(_home_for(user)))
        audit("2fa_failed", user_id=uid)
        db.commit()
        session["pending_2fa_fails"] = int(session.get("pending_2fa_fails") or 0) + 1
        if session["pending_2fa_fails"] >= SECOND_STEP_TRIES:
            _drop_pending()
            flash("Too many wrong codes. Please sign in again.", "error")
            return redirect(url_for("auth.login"))
        flash("That code didn't match. Try the current code from your authenticator app, or a recovery code.", "error")
    return render_template("auth/second_step.html")


SECOND_STEP_MINUTES = 10
SECOND_STEP_TRIES = 5


def _drop_pending():
    for k in ("pending_2fa_user", "pending_next", "pending_2fa_at", "pending_2fa_fails"):
        session.pop(k, None)


@bp.route("/security", methods=("GET", "POST"))
def security():
    """Admins set up or reset two-step sign-in here. Recovery codes are shown once."""
    if g.user is None or g.user["role"] != "admin":
        abort(403)
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "start":
            secret = twofactor.new_secret()
            session["setup_secret"] = secret
            uri = twofactor.provisioning_uri(secret, g.user["email"])
            return render_template("auth/security.html", setup_secret=secret, uri=uri, enabled=g.user["totp_enabled"])
        if action == "confirm":
            secret = session.get("setup_secret")
            if secret and twofactor.verify(secret, request.form.get("code", "")):
                codes = twofactor.new_recovery_codes()
                db.execute("UPDATE users SET totp_secret = ?, totp_enabled = 1, recovery_codes = ? WHERE id = ?",
                           (twofactor.encrypt(secret, current_app.config["SECRET_KEY"]), twofactor.hash_codes(codes), g.user["id"]))
                audit("2fa_enabled", user_id=g.user["id"])
                db.commit()
                session.pop("setup_secret", None)
                return render_template("auth/security.html", recovery_codes=codes, enabled=1)
            flash("The code didn't match. Scan the QR again and enter the current code.", "error")
        if action == "disable":
            db.execute("UPDATE users SET totp_enabled = 0, totp_secret = NULL, recovery_codes = NULL WHERE id = ?", (g.user["id"],))
            audit("2fa_disabled", user_id=g.user["id"])
            db.commit()
            flash("Two-step sign-in turned off. Turn it back on before launch.", "ok")
            return redirect(url_for("auth.security"))
    return render_template("auth/security.html", enabled=g.user["totp_enabled"])


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("investor.home"))


def create_user(email, password, role, name="", accreditation_basis=None):
    db = get_db()
    email = email.strip().lower()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        return None, "An account with that email already exists. Try signing in."
    if len(password) < 10:
        return None, "Use a password of at least 10 characters."
    token = secrets.token_urlsafe(32)
    cur = db.execute(
        "INSERT INTO users(email, password_hash, role, name, confirm_token, accreditation_basis, accreditation_attested_at, created_at,"
        " consent_at, consent_text, unsub_token) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (email, generate_password_hash(password), role, name.strip(), token,
         accreditation_basis, now() if accreditation_basis else None, now(), now(), mail.CONSENT_ACCOUNT, "u" + secrets.token_urlsafe(24)))
    db.commit()
    link = url_for("auth.confirm", token=token, _external=True)
    mail.send(email, "Confirm your Luminaz email",
              "Hello %s,\n\nPlease confirm your email address to finish setting up your Luminaz account:\n\n%s\n\n"
              "If you did not create this account, ignore this message.\n\n%s" % (name or email, link, setting("company_name")))
    audit("signup", {"email": email, "role": role}, user_id=cur.lastrowid)
    db.commit()
    return cur.lastrowid, None


@bp.route("/confirm/<token>")
def confirm(token):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE confirm_token = ?", (token,)).fetchone()
    if not user:
        flash("That confirmation link is not valid or was already used.", "error")
        return redirect(url_for("auth.login"))
    db.execute("UPDATE users SET email_confirmed = 1, confirm_token = NULL WHERE id = ?", (user["id"],))
    db.commit()
    session.clear()
    session["user_id"] = user["id"]
    flash("Your email is confirmed. Welcome to Luminaz.", "ok")
    return redirect(url_for(_home_for(user)))


@bp.route("/forgot", methods=("GET", "POST"))
def forgot():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            db.execute("UPDATE users SET reset_token = ?, reset_sent_at = ? WHERE id = ?", (token, now(), user["id"]))
            db.commit()
            minutes = setting("reset_link_minutes", "60")
            mail.send(email, "Reset your Luminaz password",
                      "Use this link to choose a new password. It works for %s minutes and once only:\n\n%s\n\nIf you did not ask for this, ignore it."
                      % (minutes, url_for("auth.reset", token=token, _external=True)))
        flash("If that email has an account, a reset link is on its way.", "ok")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


def reset_link_valid(user, at=None):
    """A reset link is good for reset_link_minutes after it was sent, and once (finding 8)."""
    import datetime as dt
    if not user or not user["reset_token"] or not user["reset_sent_at"]:
        return False
    try:
        minutes = int(setting("reset_link_minutes", "60"))
    except ValueError:
        minutes = 60
    sent = dt.datetime.fromisoformat(user["reset_sent_at"])
    at = at or dt.datetime.now(dt.timezone.utc)
    return at - sent <= dt.timedelta(minutes=minutes)


@bp.route("/reset/<token>", methods=("GET", "POST"))
def reset(token):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE reset_token = ?", (token,)).fetchone()
    if not reset_link_valid(user):
        if user:
            db.execute("UPDATE users SET reset_token = NULL, reset_sent_at = NULL WHERE id = ?", (user["id"],)); db.commit()
        flash("That link has expired or was already used. Ask for a new one.", "error")
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        pw = request.form["password"]
        if len(pw) < 10:
            flash("Use a password of at least 10 characters.", "error")
        else:
            db.execute("UPDATE users SET password_hash = ?, reset_token = NULL, reset_sent_at = NULL, email_confirmed = 1 WHERE id = ?",
                       (generate_password_hash(pw), user["id"]))
            db.commit()
            flash("Password updated. Sign in with the new one.", "ok")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html")
