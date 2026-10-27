"""Support agent and the unsubscribe link.

The agent answers every platform question it can from a written knowledge base
(passwords, listings, invoices, how requests work) and gives ONE fixed reply to
any question about whether a fund is good, safe, or worth investing in. If an
Anthropic API key is set (LUMINAZ_ANTHROPIC_KEY), the agent composes answers
from the knowledge base with the model; otherwise it matches the knowledge base
directly. Either way the fund-merit rule is enforced in code, before the model.
Anything it cannot answer is escalated to the support inbox with the question.
"""
import json
import os
import re
import urllib.request

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .db import get_db, now, setting, audit
from . import mail

bp = Blueprint("support", __name__)

MERIT_PATTERNS = [
    r"\b(is|are)\b.*\b(good|safe|worth|solid|legit|legitimate|risky|a scam|reliable|trustworthy)\b",
    r"\bshould i (invest|put|buy|wire)\b", r"\bwhich fund\b", r"\bbest fund\b", r"\brecommend\b",
    r"\bwhat do you think (of|about)\b", r"\bexpected return\b", r"\bhow much (will|can) i (make|earn)\b",
    r"\bwill (it|this|the fund) (perform|pay|return)\b", r"\bdue diligence on\b",
]

MERIT_REPLY = ("Luminaz doesn't evaluate, rank, or recommend funds, so I can't tell you whether a fund is a good investment. "
               "What I can do: every listing shows the strategy, target raise, minimum, and term the manager entered, and you can "
               "request the offering documents directly from the manager with the \"Request materials\" button on the fund page. "
               "The questions worth asking them are in our education series (who the general partner is, all the fees, the fund's "
               "end date, how much of their own money is in, whether financials are audited, and whether any principal has "
               "regulatory history). Please talk to your own financial, legal, or tax adviser before investing in any private fund.")

KNOWLEDGE = [
    # (keywords, answer) -- platform how-to only
    (["password", "reset", "forgot", "sign in", "login", "log in", "can't get in"],
     "To reset your password, use the \"Forgot password?\" link on the sign-in page and we'll email you a reset link. "
     "If you never confirmed your email, check spam for the confirmation message; you can't sign in until it's confirmed."),
    (["accredited", "qualify", "calculator", "net worth", "income test"],
     "The accreditation calculator checks the SEC's income test ($200,000 for two years, or $300,000 jointly), the net worth test "
     "($1,000,000 not counting your home), and the license test (Series 7, 65, or 82). The figures you enter aren't stored; only "
     "the result and your email are. Luminaz doesn't verify accreditation; the fund manager verifies it before any investment."),
    (["request", "materials", "ppm", "documents", "contact the manager", "how do i invest"],
     "On any fund page, click \"Request materials.\" That's the only moment your name and email are shared with the manager. "
     "They'll send you the offering documents and verify your accredited status before accepting any investment. Luminaz "
     "doesn't process investments or hold money; everything from there is between you and the manager."),
    (["shortlist", "watch", "anonymous", "does the manager see"],
     "Shortlisting or watching a fund is anonymous: the manager sees only counts, never who. Your name reaches a manager only "
     "when you request materials."),
    (["sign up", "signup", "create an account", "not open", "closed", "when does the catalog open"],
     "Investor sign-up opens once enough funds are live and the accredited list is large enough for them, so nobody arrives to an "
     "empty catalog and no manager lists to an empty room. Take the calculator and, if you give your email, we'll send one note the day it opens."),
    (["pause", "paused", "pausing", "resume", "take a break", "hide my listing", "unpause", "pause my listing", "pause the listing", "pause a listing"],
     "Pause a live listing from its page: it stays visible with a 'paused' label, investors can't request materials, paused days "
     "aren't charged, and one click resumes it. A listing paused for an unpaid invoice resumes by itself when the invoice is paid."),
    (["list", "listing", "how much", "price", "fee", "cost", "per month", "monthly", "free months", "founding"],
     "Fund managers pay a flat {rate} per month per listing, billed at the end of each month for the days the listing was live, "
     "due in {net_days} days, pause or cancel any time. Every listing is free until the investor catalog opens, which happens when "
     "enough funds are live and the accredited list is large enough for them, so nobody pays for a listing investors can't see yet. "
     "The first {founding_cap} fund managers keep the rate they signed at on "
     "every fund they list. There is no percentage of the raise and no success fee. Investors never pay."),
    (["invoice", "pay", "payment", "bank transfer", "past due", "receipt"],
     "Invoices are in your dashboard under Invoices, with payment instructions printed on each one, and you get an emailed receipt "
     "when a payment is recorded. A listing whose invoice runs more than 10 days past due is paused until it's paid: it stays "
     "visible with a paused label, takes requests again by itself once the payment is recorded, and paused days are never charged."),
    (["publish", "approved", "go live", "when will my fund", "review", "how long"],
     "After you submit and sign, Luminaz reviews the listing (structure, 506(c), category, the Rule 506(d) check, documents on "
     "file, and marketing language). When it's approved you get an email and a Publish button; nothing appears to investors until "
     "you click it. Review usually takes a few business days."),
    (["edit", "change", "update my listing", "modification", "mod"],
     "Edit the listing from its page. On a live listing, changes to minimum investment and target raise apply immediately; "
     "anything else goes to Luminaz for review and is recorded as a numbered modification you then publish."),
    (["close", "fully subscribed", "cancel", "stop", "refund", "prorate"],
     "Close a listing from its page whenever the raise ends. Nothing is charged after the closing day; the final invoice covers "
     "only the days that month the listing was live."),
    (["upload", "document", "operating agreement", "subscription"],
     "Upload your PPM, operating agreement, and subscription documents from the fund page. Only Luminaz sees them, for vetting; "
     "investors receive documents from you after they request materials."),
    (["promotion", "promote", "email my investors", "kit"],
     "Once your fund is live, the Promotion kit on the fund page has a ready-to-send email and a short post with your listing link. "
     "Send it to your own investor list in your first week; that's where the first requests come from."),
    (["506(c)", "506c", "506(b)", "reg d", "regulation d", "form d"],
     "Luminaz lists only funds relying on Rule 506(c) of Regulation D, which allows public advertising provided every investor is "
     "verified as accredited. A 506(b) fund can't be listed publicly. Form D is the manager's own SEC filing; Luminaz does not check it."),
    (["unsubscribe", "stop emails", "too many emails"],
     "Every education email has an unsubscribe link at the bottom. Account notices continue while you have an account."),
    (["delete", "close my account", "privacy", "my data", "sell my"],
     "Luminaz never sells information about investors or managers. To close your account or ask for your data to be deleted, "
     "email the support address and we'll handle it within a few days (subject to records we're required to keep)."),
]


def _fill(text):
    """Prices and limits are read from Settings when an answer is given, never typed into the answers."""
    if "{" not in text:
        return text
    from . import billing
    try:
        return text.format(rate="${:,.0f}".format(billing.quoted_rate()), founding_cap=setting("founding_manager_cap", ""),
                           free_months=setting("founding_free_months", ""), net_days=setting("net_days", "30"))
    except (KeyError, IndexError, ValueError):
        return text


def is_merit_question(q):
    return any(re.search(p, q, re.I) for p in MERIT_PATTERNS)


def answer(question):
    """Returns (answer_text, kind) where kind is 'auto' or 'escalated'."""
    q = question.strip()
    if not q:
        return "", "auto"
    if is_merit_question(q):
        return MERIT_REPLY, "auto"
    key = os.environ.get("LUMINAZ_ANTHROPIC_KEY")
    if key:
        composed = _compose_with_model(q, key)
        if composed:
            return composed, "auto"
    ql = q.lower()
    best, score = None, 0
    for keywords, text in KNOWLEDGE:
        s = sum(1 for k in keywords if k in ql)
        if s > score:
            best, score = text, s
    if best:
        return _fill(best), "auto"
    return ("I don't have an answer for that one, so I've passed it to a person at Luminaz. You'll hear back at the email on your "
            "account, usually within one business day."), "escalated"


def _compose_with_model(question, key):
    """Ask the model to answer ONLY from the knowledge base. If the answer isn't there, it must say so."""
    kb = "\n\n".join("- " + _fill(t) for _, t in KNOWLEDGE)
    system = ("You are the Luminaz support assistant. Answer platform questions using ONLY the facts below. Be brief and plain. "
              "Never evaluate, compare, or recommend any fund or investment; if asked, reply exactly: " + MERIT_REPLY +
              " If the facts below do not answer the question, reply exactly: ESCALATE\n\nFACTS:\n" + kb)
    payload = {"model": "claude-sonnet-4-5", "max_tokens": 400, "system": system,
               "messages": [{"role": "user", "content": question}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        text = "".join(b.get("text", "") for b in data.get("content", []))
        if not text or "ESCALATE" in text:
            return None
        return text.strip()
    except Exception:
        return None


@bp.route("/support", methods=("GET", "POST"))
def support():
    reply = None
    kind = None
    if request.method == "POST":
        q = request.form.get("question", "")[:1500]
        reply, kind = answer(q)
        db = get_db()
        email = (g.user["email"] if g.user else request.form.get("email", "")).strip()
        db.execute("INSERT INTO support_tickets(user_id, email, question, answer, kind, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (g.user["id"] if g.user else None, email, q, reply, kind, now()))
        db.commit()
        if kind == "escalated":
            mail.send(setting("support_email"), "Support question needs a person",
                      "From: %s\n\n%s\n\nReply to them directly." % (email or "(no email given)", q))
    return render_template("support.html", reply=reply, kind=kind)


@bp.route("/unsubscribe/<token>", methods=("GET", "POST"))
def unsubscribe(token):
    """One link works for calculator leads, account holders, and outreach contacts. POST is the
    one-click form mail clients send (RFC 8058); GET shows the page. Both stop the emails."""
    db = get_db()
    email = None
    lead = db.execute("SELECT email FROM calculator_leads WHERE unsub_token = ?", (token,)).fetchone()
    if lead:
        email = lead["email"]
        db.execute("UPDATE calculator_leads SET unsubscribed = 1 WHERE email = ?", (email,))
    user = db.execute("SELECT id, email FROM users WHERE unsub_token = ?", (token,)).fetchone()
    if user:
        email = user["email"]
        db.execute("UPDATE users SET marketing_opt_in = 0 WHERE id = ?", (user["id"],))
    contact = db.execute("SELECT id, email FROM outreach WHERE unsub_token = ?", (token,)).fetchone()
    if contact:
        email = contact["email"]
        db.execute("UPDATE outreach SET status = 'do_not_contact', updated_at = ? WHERE email = ?", (now(), email))
    reg = db.execute("SELECT id, email FROM webinar_registrations WHERE token = ?", (token,)).fetchone()
    if reg:
        email = reg["email"]
    if email:
        db.execute("INSERT OR IGNORE INTO suppressions(email, reason, created_at) VALUES (?, 'unsubscribe link', ?)", (email, now()))
        db.execute("UPDATE calculator_leads SET unsubscribed = 1 WHERE email = ?", (email,))
        db.execute("UPDATE users SET marketing_opt_in = 0 WHERE email = ?", (email,))
        audit("unsubscribed", {"email": email})
        db.commit()
    if request.method == "POST":
        return ("", 200)
    return render_template("unsubscribed.html", found=bool(email), email=email)


# ---------------------------------------------------------------- lifting an unsubscribe
#
# Rule 4.8. An address on the do-not-email list comes off it only when the person who owns the
# mailbox clicks a link sent to that mailbox. Typing the address into the public calculator or a
# webinar form (which anyone could do with anyone's address) no longer lifts anything; it sends
# this confirmation instead.

RESUBSCRIBE_DAYS = 7


def send_resubscribe_link(email, what="the educational emails"):
    """One short transactional email with a single-use link. Returns the link."""
    import secrets
    db = get_db()
    token = "r" + secrets.token_urlsafe(24)
    db.execute("INSERT INTO resubscribes(token, email, created_at) VALUES (?, ?, ?)", (token, email, now()))
    db.commit()
    link = url_for("support.resubscribe", token=token, _external=True)
    mail.send(email, "Confirm: start Luminaz emails again?",
              "This address asked us earlier to stop emailing it, and someone has just entered it on the Luminaz website.\n\n"
              "If that was you and you want %s again, click this link (it works once, for %d days):\n%s\n\n"
              "If it wasn't you, ignore this email; nothing changes and you will not hear from us.\n\n%s"
              % (what, RESUBSCRIBE_DAYS, link, setting("company_name")))
    audit("resubscribe_link_sent", {"email": email})
    return link


def lift_suppression(email, reason="confirmed by email link"):
    """Take an address off the do-not-email list and switch its calculator lead back on."""
    db = get_db()
    db.execute("DELETE FROM suppressions WHERE email = ?", (email,))
    db.execute("UPDATE calculator_leads SET unsubscribed = 0 WHERE email = ?", (email,))
    audit("resubscribed", {"email": email, "how": reason})


@bp.route("/resubscribe/<token>")
def resubscribe(token):
    db = get_db()
    row = db.execute("SELECT * FROM resubscribes WHERE token = ?", (token,)).fetchone()
    ok = bool(row) and not row["used_at"]
    if ok:
        import datetime as dt
        made = dt.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        age = dt.datetime.now(made.tzinfo) - made if made.tzinfo else dt.datetime.now() - made
        ok = age <= dt.timedelta(days=RESUBSCRIBE_DAYS)
    if ok:
        db.execute("UPDATE resubscribes SET used_at = ? WHERE token = ?", (now(), token))
        lift_suppression(row["email"])
        db.commit()
    return render_template("resubscribed.html", found=ok, email=row["email"] if ok else None, days=RESUBSCRIBE_DAYS)


@bp.route("/notifications", methods=("GET", "POST"))
def notifications():
    """Signed-in users choose which emails they get. Account notices can't be turned off
    while the account exists; everything else can."""
    if g.user is None:
        return redirect(url_for("auth.login", next="/notifications"))
    db = get_db()
    if request.method == "POST" and request.form.get("action") in ("pause", "resume"):
        # An investor pauses: no educational emails, shortlist hidden, account kept. Resume with one click.
        if request.form["action"] == "pause":
            # marketing_opt_in is left as it was, so resuming restores the choice they had made.
            db.execute("UPDATE users SET paused_at = ? WHERE id = ?", (now(), g.user["id"]))
            db.execute("INSERT OR IGNORE INTO suppressions(email, reason, created_at) VALUES (?, 'account paused', ?)", (g.user["email"], now()))
            db.execute("UPDATE calculator_leads SET unsubscribed = 1 WHERE email = ?", (g.user["email"],))
            flash("Paused. You'll get no educational emails and your shortlist is hidden until you resume. Account notices continue.", "ok")
        else:
            db.execute("UPDATE users SET paused_at = NULL WHERE id = ?", (g.user["id"],))
            db.execute("DELETE FROM suppressions WHERE email = ? AND reason = 'account paused'", (g.user["email"],))
            still_off = db.execute("SELECT 1 FROM suppressions WHERE email = ?", (g.user["email"],)).fetchone() or not g.user["marketing_opt_in"]
            if not still_off:
                db.execute("UPDATE calculator_leads SET unsubscribed = 0 WHERE email = ?", (g.user["email"],))
            flash("Welcome back. Your shortlist is on again%s." % ("" if not still_off else "; educational emails stay off, as you had them"), "ok")
        audit("account_" + request.form["action"] + "d", user_id=g.user["id"])
        db.commit()
        return redirect(url_for("support.notifications"))
    if request.method == "POST":
        on = 1 if request.form.get("marketing") else 0
        db.execute("UPDATE users SET marketing_opt_in = ? WHERE id = ?", (on, g.user["id"]))
        if on:
            db.execute("DELETE FROM suppressions WHERE email = ?", (g.user["email"],))
            db.execute("UPDATE calculator_leads SET unsubscribed = 0 WHERE email = ?", (g.user["email"],))
        else:
            db.execute("INSERT OR IGNORE INTO suppressions(email, reason, created_at) VALUES (?, 'notifications page', ?)", (g.user["email"], now()))
            db.execute("UPDATE calculator_leads SET unsubscribed = 1 WHERE email = ?", (g.user["email"],))
        audit("notifications_changed", {"marketing": on}, user_id=g.user["id"])
        db.commit()
        flash("Saved." if on else "Saved. You'll get account notices only.", "ok")
        return redirect(url_for("support.notifications"))
    user = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return render_template("notifications.html", user=user)


def user_unsub_url(user_id):
    """A stable per-account unsubscribe link, created on first use."""
    db = get_db()
    row = db.execute("SELECT unsub_token FROM users WHERE id = ?", (user_id,)).fetchone()
    token = row["unsub_token"] if row else None
    if not token:
        import secrets
        token = "u" + secrets.token_urlsafe(24)
        db.execute("UPDATE users SET unsub_token = ? WHERE id = ?", (token, user_id))
        db.commit()
    return url_for("support.unsubscribe", token=token, _external=True)
