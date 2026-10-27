"""The numbers, computed from what the app already records. Nothing here is
entered by hand. weekly() and daily() feed the admin Metrics page; summary() is the
Monday email and daily_text() the evening one."""
import datetime as dt

from .db import get_db, setting, day_bounds


def _week_start(d):
    return d - dt.timedelta(days=d.weekday())


def weekly(weeks=12, today=None):
    """One row per ISO week, newest last. Counts are events in that week; 'live_funds' and
    'mrr' are the state at the end of the week (as of today for the current week)."""
    db = get_db()
    today = today or dt.date.today()
    this_monday = _week_start(today)
    rows = []
    for k in range(weeks - 1, -1, -1):
        start = this_monday - dt.timedelta(days=7 * k)
        end = start + dt.timedelta(days=7)
        s, e = start.isoformat(), end.isoformat()
        c = lambda sql, args=(): db.execute(sql, args).fetchone()[0]
        r = {
            "week": s,
            "visitors": c("SELECT COUNT(DISTINCT day || visitor) FROM page_views WHERE day >= ? AND day < ?", (s, e)),
            "page_views": c("SELECT COUNT(*) FROM page_views WHERE day >= ? AND day < ?", (s, e)),
            "calculator_views": c("SELECT COUNT(*) FROM page_views WHERE path = '/calculator' AND day >= ? AND day < ?", (s, e)),
            "leads": c("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE created_at >= ? AND created_at < ?", (s, e)),
            "accredited_leads": c("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE result = 'accredited' AND created_at >= ? AND created_at < ?", (s, e)),
            "investor_signups": c("SELECT COUNT(*) FROM users WHERE role = 'investor' AND email_confirmed = 1 AND created_at >= ? AND created_at < ?", (s, e)),
            "manager_signups": c("SELECT COUNT(*) FROM users WHERE role = 'manager' AND email_confirmed = 1 AND created_at >= ? AND created_at < ?", (s, e)),
            "funds_submitted": c("SELECT COUNT(*) FROM funds WHERE submitted_at >= ? AND submitted_at < ?", (s, e)),
            "funds_published": c("SELECT COUNT(*) FROM funds WHERE live_since >= ? AND live_since < ?", (s, e)),
            "fund_views": c("SELECT COUNT(*) FROM fund_views WHERE viewed_at >= ? AND viewed_at < ?", (s, e)),
            "requests": c("SELECT COUNT(*) FROM requests WHERE created_at >= ? AND created_at < ?", (s, e)),
            "outreach_sent": c("SELECT COUNT(*) FROM outreach WHERE sent_at >= ? AND sent_at < ?", (s, e)),
            "outreach_yes": c("SELECT COUNT(*) FROM outreach WHERE status IN ('yes','listed') AND replied_at >= ? AND replied_at < ?", (s, e)),
            "posts_sent": c("SELECT COUNT(*) FROM posts WHERE published_at >= ? AND published_at < ?", (s, e)),
            "support_questions": c("SELECT COUNT(*) FROM support_tickets WHERE created_at >= ? AND created_at < ?", (s, e)),
            "invoiced": c("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE amount > 0 AND issued_at >= ? AND issued_at < ?", (s, e)),
            "paid": c("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status = 'paid' AND amount > 0 AND paid_at >= ? AND paid_at < ?", (s, e)),
        }
        as_of = min(end, today + dt.timedelta(days=1)).isoformat()
        r["live_funds"] = c("SELECT COUNT(*) FROM funds WHERE status = 'live' AND live_since < ?", (as_of,))
        # Nothing recurs until billing has started (free until the catalog opens): $0 before that day.
        from . import billing
        start = billing.billing_start(record=False)
        if start and start.isoformat() <= as_of:
            r["mrr"] = c("SELECT COALESCE(SUM(monthly_rate),0) FROM funds WHERE status = 'live' AND live_since < ? AND (free_until IS NULL OR free_until <= ?)", (as_of, as_of))
        else:
            r["mrr"] = 0
        rows.append(r)
    return rows


def daily(days=14, today=None):
    """One row per calendar day, newest first: who came and who signed up that day.
    Days follow this computer's clock (see db.day_bounds)."""
    db = get_db()
    today = today or dt.date.today()
    c = lambda sql, args=(): db.execute(sql, args).fetchone()[0]
    rows = []
    for k in range(days):
        day = today - dt.timedelta(days=k)
        d = day.isoformat()
        s, e = day_bounds(day)
        rows.append({
            "day": d,
            "weekday": day.strftime("%a"),
            "visitors": c("SELECT COUNT(DISTINCT visitor) FROM page_views WHERE day = ?", (d,)),
            "leads": c("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE created_at >= ? AND created_at < ?", (s, e)),
            "accredited_leads": c("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE result = 'accredited' AND created_at >= ? AND created_at < ?", (s, e)),
            "investor_signups": c("SELECT COUNT(*) FROM users WHERE role = 'investor' AND email_confirmed = 1 AND created_at >= ? AND created_at < ?", (s, e)),
            "manager_signups": c("SELECT COUNT(*) FROM users WHERE role = 'manager' AND email_confirmed = 1 AND created_at >= ? AND created_at < ?", (s, e)),
            "funds_published": c("SELECT COUNT(*) FROM funds WHERE live_since = ?", (d,)),
            "requests": c("SELECT COUNT(*) FROM requests WHERE created_at >= ? AND created_at < ?", (s, e)),
            "app_installs": c("SELECT COUNT(*) FROM app_events WHERE kind = 'installed' AND day = ?", (d,)),
            "app_opens": c("SELECT COUNT(*) FROM app_events WHERE kind = 'opened' AND day = ?", (d,)),
        })
    return rows


def waiting(today=None):
    """What is waiting on the founders right now, as (count, label) pairs, leaving out every queue
    that is empty. These are the queues the review desk, the Posts page, the outreach desk, the
    support page and the Billing page each show, counted in one place for the evening email."""
    db = get_db()
    d = (today or dt.date.today()).isoformat()
    c = lambda sql, args=(): db.execute(sql, args).fetchone()[0]
    queues = [
        (c("SELECT COUNT(*) FROM funds WHERE status = 'submitted'"), "fund to review", "funds to review"),
        (c("SELECT COUNT(*) FROM firms WHERE status = 'pending' OR pending_changes IS NOT NULL"),
         "firm profile to review", "firm profiles to review"),
        (c("SELECT COUNT(*) FROM fund_mods WHERE status = 'pending'"), "listing change to review", "listing changes to review"),
        (c("SELECT COUNT(*) FROM posts WHERE status = 'draft' AND scheduled_for >= ?", (d,)),
         "marketing post to approve", "marketing posts to approve"),
        (c("SELECT COUNT(*) FROM outreach WHERE status = 'drafted'"),
         "outreach email drafted, waiting for you to send", "outreach emails drafted, waiting for you to send"),
        (c("SELECT COUNT(*) FROM support_tickets WHERE kind = 'escalated'"),
         "support question that needs a person", "support questions that need a person"),
        (c("SELECT COUNT(*) FROM invoices WHERE status = 'open' AND due_at < ?", (d,)), "invoice past due", "invoices past due"),
    ]
    return [(n, one if n == 1 else many) for n, one, many in queues if n]


def daily_text(at=None):
    """Plain-text evening email: today so far beside yesterday's whole day, what is waiting on the
    founders, and the totals so far. `at` is the moment it is written (default: now). Every line
    stays under 76 characters so the copy saved in instance/outbox reads as plain text."""
    at = at or dt.datetime.now()
    today = at.date()
    t, y = daily(days=2, today=today)            # today so far, then yesterday
    tot = totals()
    todo = waiting(today)

    def line(label, key):
        return "  %-32s %6s   (yesterday, whole day: %s)" % (label, format(t[key], ","), format(y[key], ","))

    body = "Luminaz, %s, as of %s\n\n" % (today.strftime("%A %d %B %Y"), at.strftime("%I:%M %p").lstrip("0").lower())
    body += "TODAY SO FAR\n" + "\n".join([
        line("Visitors", "visitors"),
        line("Email sign-ups (calculator)", "leads"),
        line("  of which appear accredited", "accredited_leads"),
        line("Investor accounts", "investor_signups"),
        line("Fund managers", "manager_signups"),
        line("Funds published", "funds_published"),
        line("Requests for materials", "requests"),
        line("Added to a home screen", "app_installs"),
        line("Opened from a home screen", "app_opens")]) + "\n\n"
    body += "WAITING ON YOU\n"
    body += "".join("  %s %s\n" % (format(n, ","), label) for n, label in todo) if todo else "  Nothing is waiting on you tonight.\n"
    body += "\nTOTALS SO FAR\n"
    for label, value in (("Sign-ups that appear accredited", tot["accredited_leads"]), ("Investor accounts", tot["investors"]),
                         ("Fund managers", tot["managers"]), ("Live funds", tot["funds_live"])):
        body += "  %-32s %6s\n" % (label, format(value, ","))
    from . import billing
    s = billing.slot_summary()
    if s["cap"]:
        body += "  %-32s %6s   of %d slots\n" % ("Listing slots taken", format(s["used"], ","), s["cap"])
        body += "  %-32s %6s\n" % ("Listing slots open", format(s["open"], ","))
    body += "  %-32s %6s\n" % ("Funds in line to go live", format(s["line"], ","))
    body += "\nSOCIAL, LAST 7 DAYS\n" + "".join("  %-32s %6s\n" % (label, format(n, ",")) for label, n in social(today=today))
    body += ("\nWhat happens after this email is counted in tomorrow's\n"
             "\"yesterday, whole day\" figures.\n"
             "The day-by-day table is on the Metrics page of the review desk.\n"
             "Home-screen counts are partial: an iPhone reports an open,\n"
             "never an install.\n")
    subject = "Luminaz today: %s email sign-ups, %s investor accounts, %s fund managers" % (
        format(t["leads"], ","), format(t["investor_signups"], ","), format(t["manager_signups"], ","))
    if todo:
        subject += "; %s waiting on you" % format(sum(n for n, _ in todo), ",")
    return subject, body


def social(today=None):
    """Posts sent in the last seven days by purpose, and visitors who arrived from a social ?src=
    tag, as (label, count) pairs for the evening report (change 29)."""
    db = get_db()
    today = today or dt.date.today()
    since = (today - dt.timedelta(days=7)).isoformat()
    sent = {r["purpose"]: r["n"] for r in db.execute(
        "SELECT purpose, COUNT(*) AS n FROM posts WHERE published_at >= ? GROUP BY purpose", (since,))}
    drafts = db.execute("SELECT COUNT(*) FROM posts WHERE status = 'draft' AND scheduled_for >= ?", (today.isoformat(),)).fetchone()[0]
    out = [("Posts sent to investors", sent.get("investors", 0)), ("Posts sent to fund managers", sent.get("managers", 0)),
           ("Posts sent about webinars", sent.get("webinars", 0)), ("Posts waiting for approval", drafts)]
    for src, label in (("linkedin", "Visitors from LinkedIn"), ("facebook", "Visitors from Facebook"), ("x", "Visitors from X")):
        n = db.execute("SELECT COUNT(DISTINCT day || visitor) FROM page_views WHERE day >= ? AND LOWER(source) = ?", (since, src)).fetchone()[0]
        out.append((label, n))
    return out


def communications(weeks=8, today=None):
    """What every communication brought, for the Communications page and the Monday email (change 33):
    each sent post with the visitors, calculator leads and webinar sign-ups that arrived through its
    tagged link; totals by purpose and by platform; each webinar's registrations by source, joins,
    attendance and replays; the education series by step; manager outreach by status with the reply
    rate. Engagement that lives inside LinkedIn or Facebook (likes, impressions, followers) is not
    here: the app cannot see it; the posting service's own analytics do."""
    db = get_db()
    today = today or dt.date.today()
    since = (today - dt.timedelta(days=7 * weeks)).isoformat()
    posts = []
    for p in db.execute("SELECT id, scheduled_for, purpose, topic, hook, published_at, published_via FROM posts"
                        " WHERE status = 'published' AND published_at >= ? ORDER BY published_at DESC", (since,)).fetchall():
        camp = str(p["id"])
        visitors = db.execute("SELECT COUNT(DISTINCT day || visitor) FROM page_views WHERE campaign = ?", (camp,)).fetchone()[0]
        leads = db.execute("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE campaign = ?", (camp,)).fetchone()[0]
        accredited = db.execute("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE campaign = ? AND result = 'accredited'", (camp,)).fetchone()[0]
        webs = db.execute("SELECT COUNT(DISTINCT email) FROM webinar_registrations WHERE campaign = ?", (camp,)).fetchone()[0]
        by_platform = db.execute("SELECT LOWER(COALESCE(NULLIF(source,''),'direct')) AS s, COUNT(DISTINCT day || visitor) AS n FROM page_views"
                                 " WHERE campaign = ? GROUP BY 1 ORDER BY 2 DESC", (camp,)).fetchall()
        posts.append({"id": p["id"], "date": p["published_at"][:10], "scheduled_for": p["scheduled_for"], "purpose": p["purpose"],
                      "topic": p["topic"], "hook": p["hook"] or "", "via": p["published_via"], "visitors": visitors, "leads": leads,
                      "accredited": accredited, "webinar_signups": webs, "platforms": ", ".join("%s %d" % (r["s"], r["n"]) for r in by_platform)})
    by_purpose = {}
    for row in posts:
        b = by_purpose.setdefault(row["purpose"], {"posts": 0, "visitors": 0, "leads": 0, "accredited": 0, "webinar_signups": 0})
        b["posts"] += 1
        for k in ("visitors", "leads", "accredited", "webinar_signups"):
            b[k] += row[k]
    by_platform = db.execute("SELECT LOWER(COALESCE(NULLIF(source,''),'direct / unknown')) AS source, COUNT(DISTINCT day || visitor) AS visitors,"
                             " (SELECT COUNT(DISTINCT email) FROM calculator_leads l WHERE LOWER(COALESCE(NULLIF(l.source,''),'direct / unknown')) = LOWER(COALESCE(NULLIF(v.source,''),'direct / unknown')) AND l.created_at >= ?) AS leads"
                             " FROM page_views v WHERE day >= ? GROUP BY 1 ORDER BY 2 DESC LIMIT 12", (since, since)).fetchall()
    webinars = []
    for w in db.execute("SELECT * FROM webinars ORDER BY starts_at DESC LIMIT 20").fetchall():
        regs = db.execute("SELECT COUNT(*) FROM webinar_registrations WHERE webinar_id = ?", (w["id"],)).fetchone()[0]
        joined = db.execute("SELECT COUNT(*) FROM webinar_registrations WHERE webinar_id = ? AND joined_at IS NOT NULL", (w["id"],)).fetchone()[0]
        attended = db.execute("SELECT COUNT(*) FROM webinar_registrations WHERE webinar_id = ? AND attended = 1", (w["id"],)).fetchone()[0]
        replays = db.execute("SELECT COUNT(*) FROM webinar_registrations WHERE webinar_id = ? AND replay_sent_at IS NOT NULL", (w["id"],)).fetchone()[0]
        srcs = db.execute("SELECT LOWER(COALESCE(NULLIF(source,''),'direct')) AS s, COUNT(*) AS n FROM webinar_registrations WHERE webinar_id = ? GROUP BY 1 ORDER BY 2 DESC", (w["id"],)).fetchall()
        webinars.append({"id": w["id"], "title": w["title"], "audience": w["audience"], "starts_at": w["starts_at"], "status": w["status"],
                         "registrations": regs, "joined": joined, "attended": attended, "replays": replays,
                         "sources": ", ".join("%s %d" % (r["s"], r["n"]) for r in srcs),
                         "show_rate": (100 * joined // regs) if regs else 0})
    education = [{"step": r["sequence_step"], "leads": r["n"]} for r in db.execute(
        "SELECT sequence_step, COUNT(*) AS n FROM calculator_leads GROUP BY sequence_step ORDER BY sequence_step").fetchall()]
    outreach = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) AS n FROM outreach GROUP BY status").fetchall()}
    sent = db.execute("SELECT COUNT(*) FROM outreach WHERE sent_at IS NOT NULL").fetchone()[0]
    replied = db.execute("SELECT COUNT(*) FROM outreach WHERE replied_at IS NOT NULL").fetchone()[0]
    yes = outreach.get("yes", 0) + outreach.get("listed", 0)
    return {"since": since, "posts": posts, "by_purpose": by_purpose, "by_platform": by_platform, "webinars": webinars,
            "education": education, "outreach": {"by_status": outreach, "sent": sent, "replied": replied,
                                                 "reply_rate": (100 * replied // sent) if sent else 0, "yes": yes}}


def totals():
    db = get_db()
    c = lambda sql: db.execute(sql).fetchone()[0]
    return {
        "leads": c("SELECT COUNT(DISTINCT email) FROM calculator_leads"),
        "accredited_leads": c("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE result = 'accredited'"),
        "unsubscribed": c("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE unsubscribed = 1"),
        "investors": c("SELECT COUNT(*) FROM users WHERE role = 'investor' AND email_confirmed = 1"),
        "managers": c("SELECT COUNT(*) FROM users WHERE role = 'manager' AND email_confirmed = 1"),
        "firms_approved": c("SELECT COUNT(*) FROM firms WHERE status = 'approved'"),
        "founding_firms": c("SELECT COUNT(*) FROM firms WHERE founding_manager = 1"),
        "funds_live": c("SELECT COUNT(*) FROM funds WHERE status = 'live'"),
        "funds_closed": c("SELECT COUNT(*) FROM funds WHERE status = 'closed'"),
        "requests": c("SELECT COUNT(*) FROM requests"),
        "requests_invested": c("SELECT COUNT(*) FROM requests WHERE status = 'invested'"),
        "open_invoices": c("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status = 'open'"),
        "paid_total": c("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status = 'paid' AND amount > 0"),
        "outreach_total": c("SELECT COUNT(*) FROM outreach"),
        "outreach_sent": c("SELECT COUNT(*) FROM outreach WHERE status NOT IN ('new','drafted')"),
        "outreach_yes": c("SELECT COUNT(*) FROM outreach WHERE status IN ('yes','listed')"),
        "outreach_listed": c("SELECT COUNT(*) FROM outreach WHERE status = 'listed'"),
    }


def sources(days=28):
    """Where visitors and leads came from, last N days."""
    db = get_db()
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    visits = db.execute("SELECT COALESCE(NULLIF(source,''),'direct / unknown') AS source, COUNT(DISTINCT day || visitor) AS visitors"
                        " FROM page_views WHERE day >= ? GROUP BY 1 ORDER BY 2 DESC LIMIT 15", (since,)).fetchall()
    leads = db.execute("SELECT COALESCE(NULLIF(source,''),'direct / unknown') AS source, COUNT(DISTINCT email) AS leads"
                       " FROM calculator_leads WHERE created_at >= ? GROUP BY 1 ORDER BY 2 DESC LIMIT 15", (since,)).fetchall()
    pages = db.execute("SELECT path, COUNT(*) AS views FROM page_views WHERE day >= ? GROUP BY path ORDER BY 2 DESC LIMIT 15", (since,)).fetchall()
    return {"visits": visits, "leads": leads, "pages": pages}


def roi(months=6, today=None):
    """Marketing spend against what each source produced, month by month (Diane, 14 October 2026:
    "track ROI for marketing"). Leads are calculator leads plus webinar sign-ups carrying that
    ?src= tag; the cost per accredited lead is spend divided by accredited calculator leads.
    Spend is typed in by a founder; nothing here is tied to any investment."""
    db = get_db()
    today = today or dt.date.today()
    first = today.replace(day=1)
    keys = []
    m = first
    for _ in range(months):
        keys.append(m.strftime("%Y-%m"))
        m = (m - dt.timedelta(days=1)).replace(day=1)
    rows = []
    spend = {(r["month"], r["source"]): r["total"] for r in db.execute(
        "SELECT month, source, SUM(amount) AS total FROM marketing_spend GROUP BY month, source")}
    leads = {(r["month"], r["source"]): (r["n"], r["acc"]) for r in db.execute(
        "SELECT substr(created_at, 1, 7) AS month, LOWER(COALESCE(NULLIF(source,''),'direct / unknown')) AS source, COUNT(DISTINCT email) AS n,"
        " COUNT(DISTINCT CASE WHEN result = 'accredited' THEN email END) AS acc FROM calculator_leads GROUP BY 1, 2")}
    webs = {(r["month"], r["source"]): r["n"] for r in db.execute(
        "SELECT substr(created_at, 1, 7) AS month, LOWER(COALESCE(NULLIF(source,''),'direct / unknown')) AS source, COUNT(DISTINCT email) AS n"
        " FROM webinar_registrations GROUP BY 1, 2")}
    sources = sorted({k[1] for k in list(spend) + list(leads) + list(webs)})
    for key in keys:
        for src in sources:
            sp = spend.get((key, src), 0.0)
            n, acc = leads.get((key, src), (0, 0))
            wb = webs.get((key, src), 0)
            if not (sp or n or wb):
                continue
            rows.append({"month": key, "source": src, "spend": sp, "leads": n, "accredited": acc, "webinar": wb,
                         "cost_per_accredited": (sp / acc) if (sp and acc) else None})
    return rows


def top_funds(days=28):
    db = get_db()
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    return db.execute(
        "SELECT f.id, f.name, f.fund_number, f.status,"
        " (SELECT COUNT(*) FROM fund_views v WHERE v.fund_id = f.id AND v.viewed_at >= ?) AS views,"
        " (SELECT COUNT(*) FROM interest i WHERE i.fund_id = f.id) AS marks,"
        " (SELECT COUNT(*) FROM requests r WHERE r.fund_id = f.id AND r.created_at >= ?) AS requests"
        " FROM funds f WHERE f.status IN ('live','paused','closed') ORDER BY requests DESC, views DESC LIMIT 20", (since, since)).fetchall()


def summary(today=None):
    """Plain-text Monday email: last week vs the week before."""
    rows = weekly(weeks=2, today=today)
    prev, last = rows[0], rows[1]
    t = totals()

    def line(label, key, money=False):
        a, b = last[key], prev[key]
        fmt = (lambda v: "$%s" % format(v, ",.0f")) if money else (lambda v: format(v, ","))
        arrow = "up" if a > b else "down" if a < b else "flat"
        return "  %-26s %10s   (week before %s, %s)" % (label, fmt(a), fmt(b), arrow)

    body = "Luminaz, week of %s\n\n" % last["week"]
    body += "INVESTOR SIDE\n" + "\n".join([
        line("Visitors", "visitors"), line("Calculator views", "calculator_views"), line("Calculator leads", "leads"),
        line("  of which accredited", "accredited_leads"), line("Investor sign-ups", "investor_signups"),
        line("Fund page views", "fund_views"), line("Material requests", "requests")]) + "\n\n"
    body += "MANAGER SIDE\n" + "\n".join([
        line("Outreach emails sent", "outreach_sent"), line("Managers who said yes", "outreach_yes"),
        line("Manager sign-ups", "manager_signups"), line("Funds submitted", "funds_submitted"),
        line("Funds published", "funds_published")]) + "\n\n"
    body += "MONEY\n" + "\n".join([
        line("Invoiced", "invoiced", True), line("Paid", "paid", True),
        "  %-26s %10s" % ("Live funds now", format(last["live_funds"], ",")),
        "  %-26s %10s" % ("Monthly recurring now", "$%s" % format(last["mrr"], ",.0f")),
        "  %-26s %10s" % ("Open invoices", "$%s" % format(t["open_invoices"], ",.0f"))]) + "\n\n"
    c = communications(weeks=1, today=today)
    top = sorted(c["posts"], key=lambda r: (-r["visitors"], -r["leads"]))[:3]
    body += "COMMUNICATIONS, LAST WEEK\n"
    body += "  %-26s %10s\n" % ("Posts sent", format(len(c["posts"]), ","))
    for r in top:
        body += "  %-26s %10s   %s\n" % ((r["topic"][:24] + ("..." if len(r["topic"]) > 24 else "")), format(r["visitors"], ",") + " visitors", "%d leads" % r["leads"])
    for w in [w for w in c["webinars"] if w["registrations"]][:3]:
        body += "  %-26s %10s   %s\n" % ((w["title"][:24] + ("..." if len(w["title"]) > 24 else "")), format(w["registrations"], ",") + " signed up", "%d joined" % w["joined"])
    body += "  %-26s %10s   (%d replied, %d yes)\n\n" % ("Outreach emails ever sent", format(c["outreach"]["sent"], ","), c["outreach"]["replied"], c["outreach"]["yes"])
    body += "ALL TIME: %s accredited leads, %s investors, %s live funds, %s closed, %s requests (%s reported invested), %s paid.\n" % (
        format(t["accredited_leads"], ","), format(t["investors"], ","), t["funds_live"], t["funds_closed"],
        format(t["requests"], ","), t["requests_invested"], "$%s" % format(t["paid_total"], ",.0f"))
    body += "\nDetails: %s\n" % setting("investor_host", "the admin Metrics page")
    return "Luminaz weekly numbers: %s visitors, %s accredited leads, %s requests" % (
        format(last["visitors"], ","), format(last["accredited_leads"], ","), format(last["requests"], ",")), body
