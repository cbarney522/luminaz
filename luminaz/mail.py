"""Outgoing email.

Until a real provider (Postmark etc.) is configured, every message is written
to instance/outbox/ as a text file so it can be read during testing. Switch by
setting LUMINAZ_SMTP_HOST / PORT / USER / PASSWORD / FROM in the environment.
"""
import os
import smtplib
import datetime as dt
from email.message import EmailMessage

from flask import current_app

_cfg = {}


def init_app(app):
    _cfg.update({
        "host": os.environ.get("LUMINAZ_SMTP_HOST"),
        "port": int(os.environ.get("LUMINAZ_SMTP_PORT", "587")),
        "user": os.environ.get("LUMINAZ_SMTP_USER"),
        "password": os.environ.get("LUMINAZ_SMTP_PASSWORD"),
        "from": os.environ.get("LUMINAZ_MAIL_FROM", "Luminaz <no-reply@luminaztechnology.com>"),
    })
    os.makedirs(app.config["MAIL_OUTBOX"], exist_ok=True)


CONSENT_CALCULATOR = ("I agree to receive my result and ongoing educational emails about accredited investing from Luminaz. "
                      "I can unsubscribe at any time using the link in every email.")
CONSENT_ACCOUNT = ("I agree to receive account and service notices by email for as long as I have a Luminaz account, and ongoing "
                   "educational and platform updates, which I can stop at any time from Notifications or the link in every email.")


def suppressed(to):
    from .db import get_db
    return get_db().execute("SELECT 1 FROM suppressions WHERE email = ?", (to.strip().lower(),)).fetchone() is not None


def marketing_block():
    """Why no marketing email may go out right now, or None. Two locks, checked on every marketing
    send so that no sender can forget them (AGENTS.md section 5 and rule 4.8):
      - Diane's rule: nothing goes to real people until the attorney has approved the terms and the
        privacy policy (Settings: attorney_approved = 1);
      - CAN-SPAM: every marketing email must carry a real postal address, a street or box number,
        not just a town (Settings: postal_address)."""
    from .db import setting
    if setting("attorney_approved", "0") != "1":
        return "held until the attorney approves the terms and privacy policy (Settings: attorney_approved)"
    if not any(ch.isdigit() for ch in (setting("postal_address", "") or "")):
        return "held until Settings has a postal address with a street or box number (CAN-SPAM)"
    return None


def send(to, subject, body, kind="transactional", unsubscribe_url=None):
    """kind: 'transactional' (account notices, confirmations, invoices, requests; always sent) or
    'marketing' (education, outreach, updates; skipped for suppressed addresses, held while
    marketing_block() says so, and carries the postal address, an unsubscribe line, and
    List-Unsubscribe headers as CAN-SPAM requires). Returns 'held' or 'suppressed' when nothing
    was sent, so a caller can decide whether to count the send."""
    from .db import setting
    if kind == "marketing":
        if marketing_block():
            return "held"
        if suppressed(to):
            return "suppressed"
        body = body.rstrip() + "\n\n--\n%s\n%s" % (setting("company_name", "Luminaz"), setting("postal_address", ""))
        if unsubscribe_url:
            if unsubscribe_url not in body:
                body += "\nUnsubscribe: %s" % unsubscribe_url
    msg = EmailMessage()
    msg["From"] = _cfg["from"]
    msg["To"] = to
    msg["Subject"] = subject
    if kind == "marketing" and unsubscribe_url:
        msg["List-Unsubscribe"] = "<%s>" % unsubscribe_url
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(body)
    if _cfg.get("host"):
        with smtplib.SMTP(_cfg["host"], _cfg["port"]) as s:
            s.starttls()
            if _cfg.get("user"):
                s.login(_cfg["user"], _cfg["password"] or "")
            s.send_message(msg)
        return "sent"
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe = "".join(c if c.isalnum() else "_" for c in to)[:40]
    path = os.path.join(current_app.config["MAIL_OUTBOX"], "%s_%s.txt" % (stamp, safe))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(str(msg))
    return path
