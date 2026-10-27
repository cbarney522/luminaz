"""Marketing posts by purpose: to accredited investors, to fund managers, and about webinars.

How it runs:
  1. plan_posts()    the daily job keeps this week and next week drafted. Each purpose has its
                     own weekdays on Settings (post_days_investors, post_days_managers,
                     post_days_webinars): investor posts come in order from content/posts.py
                     POSTS, manager posts from MANAGER_POSTS, and a webinar post is drafted only
                     when an open webinar starts within post_webinar_lead_days and the attorney
                     switch is on (its sign-up page is locked until then). New drafts trigger one
                     email: "n posts waiting for your approval."
  2. Approval        a founder reads each post on /admin/marketing, edits the hook and the text
                     if she likes, and clicks Approve (or Skip). Nothing goes out unapproved
                     (rule 4.7).
  3. publish_posts() on the scheduled day the daily job sends every approved post, rendered once
                     per platform the purpose is set to (Settings: post_platforms_*), each with
                     its link tagged ?src=<platform> so the Metrics page can tell the platforms
                     apart: to the webhook in Settings (Zapier / Make / Buffer) when one is set,
                     otherwise as an email to the founder with the ready-to-paste text.
Posts that were never approved simply pass their date and stay listed as drafts.
"""
import datetime as dt
import json
import urllib.request

from flask import url_for

from .db import get_db, now, audit, setting
from . import mail
from .content.posts import POSTS, MANAGER_POSTS, WEBINAR_TEMPLATES, DISCLAIMER, MANAGER_DISCLAIMER, hook_for

PURPOSES = ("investors", "managers", "webinars")
PURPOSE_LABEL = {"investors": "to accredited investors", "managers": "to fund managers", "webinars": "about a webinar"}
WEEKDAYS = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
SLOTS = list(WEEKDAYS)          # kept for older imports
PLATFORM_LABEL = {"linkedin": "LinkedIn", "facebook": "Facebook", "x": "X / Threads", "threads": "Threads",
                  "newsletter": "Newsletter", "youtube": "YouTube"}
LINK_PLACEHOLDERS = ("{calculator_url}", "{manager_url}", "{signup_url}")


def days_for(purpose):
    """[(weekday name, index)] from Settings, in weekday order; names it does not know are ignored."""
    raw = setting("post_days_%s" % purpose, "") or ""
    names = [n.strip().capitalize() for n in raw.split(",") if n.strip()]
    return sorted([(n, WEEKDAYS[n]) for n in names if n in WEEKDAYS], key=lambda x: x[1])


def platforms_for(purpose):
    raw = setting("post_platforms_%s" % purpose, "") or ""
    return [p.strip().lower() for p in raw.split(",") if p.strip()] or ["linkedin"]


def _next_bank_index(db, purpose, bank):
    row = db.execute("SELECT MAX(bank_index) FROM posts WHERE purpose = ? AND webinar_id IS NULL", (purpose,)).fetchone()
    return 0 if row[0] is None else (row[0] + 1) % len(bank)


def _notify_to():
    return setting("post_notify_email", "") or setting("support_email")


def _webinar_draft(db, date):
    """A post about the next open webinar within the lead window, or None. 'announce' until three
    days before, then 'last_call'; one of each per webinar. Nothing while the attorney switch is
    0: the sign-up page the post links to is locked (section 5)."""
    if setting("attorney_approved", "0") != "1":
        return None
    try:
        lead = int(setting("post_webinar_lead_days", "14") or 14)
    except ValueError:
        lead = 14
    rows = db.execute("SELECT * FROM webinars WHERE status = 'open' ORDER BY starts_at").fetchall()
    for w in rows:
        try:
            starts = dt.datetime.fromisoformat(w["starts_at"]).date()
        except ValueError:
            continue
        days_to = (starts - date).days
        if days_to < 0 or days_to > lead:
            continue
        kind = 1 if days_to <= 3 else 0          # bank_index: 0 = announce, 1 = last call
        if db.execute("SELECT 1 FROM posts WHERE webinar_id = ? AND bank_index = ? AND status != 'skipped'", (w["id"], kind)).fetchone():
            continue
        from .webinars import when
        t = WEBINAR_TEMPLATES[w["audience"]]["last_call" if kind else "announce"]
        fill = lambda s: s.replace("{title}", w["title"]).replace("{when}", when(w))
        return {"topic": fill(t["topic"]), "hook": fill(t["hook"]), "long": fill(t["long"]), "short": fill(t["short"]),
                "tags": t["tags"], "bank_index": kind, "webinar_id": w["id"]}
    return None


def _draft_for(db, purpose, date):
    if purpose == "webinars":
        return _webinar_draft(db, date)
    bank = POSTS if purpose == "investors" else MANAGER_POSTS
    idx = _next_bank_index(db, purpose, bank)
    p = bank[idx]
    return {"topic": p["topic"], "hook": p.get("hook") or hook_for(p["long"]), "long": p["long"], "short": p["short"],
            "tags": p["tags"], "bank_index": idx, "webinar_id": None}


def plan_posts(today=None):
    """Make sure this week and next week are drafted for every purpose. Returns how many were created."""
    db = get_db()
    today = today or dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    created = []
    for week_start in (monday, monday + dt.timedelta(days=7)):
        for purpose in PURPOSES:
            for slot, idx in days_for(purpose):
                date = week_start + dt.timedelta(days=idx)
                if date < today:
                    continue
                if db.execute("SELECT 1 FROM posts WHERE scheduled_for = ? AND slot = ?", (date.isoformat(), slot)).fetchone():
                    continue
                d = _draft_for(db, purpose, date)
                if not d:
                    continue
                db.execute("INSERT INTO posts(scheduled_for, slot, bank_index, topic, long_body, short_body, tags, created_at, purpose, hook, webinar_id)"
                           " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (date.isoformat(), slot, d["bank_index"], d["topic"], d["long"], d["short"], d["tags"], now(),
                            purpose, d["hook"], d["webinar_id"]))
                created.append((date, slot, purpose, d["topic"]))
    if created:
        lines = "\n".join("- %s %s (%s): %s" % (d.isoformat(), s, PURPOSE_LABEL[p], t) for d, s, p, t in created)
        mail.send(_notify_to(), "Luminaz: %d marketing post%s waiting for your approval" % (len(created), "" if len(created) == 1 else "s"),
                  "The agent drafted these posts:\n\n%s\n\nRead, edit, and approve them here:\n%s\n\n"
                  "Nothing is sent until you click Approve." % (lines, url_for("admin.marketing", _external=True)))
        audit("posts_drafted", {"count": len(created)})
    db.commit()
    return len(created)


def _base_link(post):
    purpose = post["purpose"] if "purpose" in post.keys() else "investors"
    if purpose == "managers":
        return url_for("manager.landing", _external=True)
    if purpose == "webinars" and post["webinar_id"]:
        return url_for("webinars.signup", webinar_id=post["webinar_id"], _external=True)
    return url_for("investor.calculator", _external=True)


def _tagged(base, platform, post_id=None):
    """?src=<platform> says where the visitor came from; &p=<post id> says which post, so the
    Communications page can credit visitors, leads and webinar sign-ups to the post (change 33)."""
    tag = "src=" + (platform or "social")
    if post_id:
        tag += "&p=%d" % int(post_id)
    return base + ("&" if "?" in base else "?") + tag


def _fill(text, link):
    for ph in LINK_PLACEHOLDERS:
        text = text.replace(ph, link)
    return text


def _with_hook(hook, body):
    hook = (hook or "").strip()
    return body if not hook or body.lstrip().startswith(hook) else hook + "\n\n" + body


def render(post, platform=None):
    """The texts for one post. With no platform, links carry ?src=social; the 'platforms' entry
    holds one text per platform the purpose is set to, each with its own ?src= tag."""
    purpose = post["purpose"] if "purpose" in post.keys() else "investors"
    hook = post["hook"] if "hook" in post.keys() else ""
    disclaimer = MANAGER_DISCLAIMER if purpose in ("managers",) else DISCLAIMER
    if purpose == "webinars":
        w = get_db().execute("SELECT audience FROM webinars WHERE id = ?", (post["webinar_id"],)).fetchone() if post["webinar_id"] else None
        disclaimer = MANAGER_DISCLAIMER if (w and w["audience"] == "managers") else DISCLAIMER
    base = _base_link(post)
    long_body = _with_hook(hook, post["long_body"])

    post_id = post["id"] if "id" in post.keys() else None

    def texts(plat):
        link = _tagged(base, plat, post_id)
        return {"long": _fill(long_body, link) + "\n\n" + disclaimer, "short": _fill(post["short_body"], link), "link": link}

    out = texts(platform)
    out.update({"tags": post["tags"], "disclaimer": disclaimer, "hook": hook, "purpose": purpose, "platforms": {}})
    for plat in platforms_for(purpose):
        t = texts(plat)
        body = t["short"] if plat in ("x", "threads") else t["long"]
        if post["tags"] and len(body) + len(post["tags"]) + 2 <= (280 if plat in ("x", "threads") else 3000):
            body = body + "\n\n" + post["tags"]
        out["platforms"][plat] = {"label": PLATFORM_LABEL.get(plat, plat), "text": body, "link": t["link"]}
    return out


def publish_posts(today=None):
    """Send every approved post whose day has come. Returns how many went out."""
    db = get_db()
    today = (today or dt.date.today()).isoformat()
    due = db.execute("SELECT * FROM posts WHERE status = 'approved' AND scheduled_for <= ? ORDER BY scheduled_for, id", (today,)).fetchall()
    sent = 0
    for post in due:
        via = _deliver(post)
        db.execute("UPDATE posts SET status = 'published', published_at = ?, published_via = ? WHERE id = ?", (now(), via, post["id"]))
        audit("post_published", {"post_id": post["id"], "via": via, "purpose": post["purpose"]})
        sent += 1
    db.commit()
    return sent


def payload(post):
    """What the webhook receives: the old keys (long, short, hashtags) plus purpose, hook and one
    ready text per platform with its own ?src= link."""
    r = render(post)
    return {"scheduled_for": post["scheduled_for"], "slot": post["slot"], "purpose": r["purpose"], "topic": post["topic"],
            "hook": r["hook"], "long": r["long"], "short": r["short"], "hashtags": r["tags"], "disclaimer": r["disclaimer"],
            "platforms": {k: {"text": v["text"], "link": v["link"]} for k, v in r["platforms"].items()}}


def _paste_text(r):
    return "\n\n".join("--- %s ---\n%s" % (v["label"], v["text"]) for v in r["platforms"].values())


def _deliver(post):
    r = render(post)
    hook = setting("post_webhook_url", "")
    if hook:
        req = urllib.request.Request(hook, data=json.dumps(payload(post)).encode(), headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
            return "webhook"
        except Exception as e:
            mail.send(_notify_to(), "Luminaz: post could not reach the webhook, post it by hand",
                      "The webhook failed (%s). Here is the approved post for %s (%s):\n\n%s"
                      % (e, post["scheduled_for"], PURPOSE_LABEL.get(r["purpose"], r["purpose"]), _paste_text(r)))
            return "email (webhook failed)"
    mail.send(_notify_to(), "Luminaz: post this today (%s, %s)" % (post["slot"], post["topic"]),
              "Approved post for %s, %s. Copy and paste each block to its platform:\n\n%s\n\n"
              "Add a webhook in Settings and the app will post these for you." % (post["scheduled_for"], PURPOSE_LABEL.get(r["purpose"], r["purpose"]), _paste_text(r)))
    return "email"
