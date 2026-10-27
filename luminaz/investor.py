"""Luminaz - the investor portal. Free, always."""
from flask import (Blueprint, abort, flash, g, redirect, render_template, request, session, url_for)

from .auth import login_required, create_user, ACCREDITATION_BASES
from .db import get_db, now, today, audit, setting, CATEGORIES
from .visitors import visitor_hash, is_bot
from . import mail

bp = Blueprint("investor", __name__)


def signup_open():
    """Investor sign-up opens when the catalog does: enough live funds and an accredited list large
    enough for them (billing.readiness). The switch in Settings forces it open (testers; nobody's
    billing starts) or closed (an emergency; even after the catalog opened)."""
    from . import billing
    mode = setting("investor_signup_open", "auto")
    if mode == "open":
        return True
    if mode == "closed":
        return False
    return billing.catalog_opened(record=False) is not None


@bp.route("/")
def home():
    from . import billing
    return render_template("investor/home.html", ready=billing.readiness(), open=signup_open())


@bp.route("/about")
def about():
    return render_template("investor/about.html")


# ---------------------------------------------------------------- learn (public, indexable)

def _slug(t):
    import re
    return re.sub(r"[^a-z0-9]+", "-", t.lower().replace("'", "")).strip("-")


def learn_articles():
    """The 36 marketing posts double as public pages: one indexable article per topic."""
    from .content.posts import POSTS
    out = []
    for i, p in enumerate(POSTS):
        import re
        body = re.sub(r"[:.]?\s*\{calculator_url\}", ".", p["long"]).replace("..", ".").strip()
        summary = body.split("\n")[0][:155]
        out.append({"slug": _slug(p["topic"]), "title": p["topic"], "body": body, "summary": summary, "tags": p["tags"], "n": i})
    return out


@bp.route("/learn")
def learn():
    from .content.verification import ARTICLE
    return render_template("investor/learn.html", articles=learn_articles(), featured=ARTICLE)


@bp.route("/learn/<slug>")
def article(slug):
    from .content.verification import ARTICLE
    arts = learn_articles()
    if slug == ARTICLE["slug"]:
        return render_template("investor/article.html", a=ARTICLE, related=arts[:3])
    for i, a in enumerate(arts):
        if a["slug"] == slug:
            related = [arts[(i + k) % len(arts)] for k in (1, 2, 3)]
            return render_template("investor/article.html", a=a, related=related)
    abort(404)


@bp.route("/sitemap.xml")
def sitemap():
    from flask import Response
    from .content.verification import ARTICLE
    urls = [url_for("investor.home", _external=True), url_for("investor.calculator", _external=True),
            url_for("investor.learn", _external=True), url_for("investor.about", _external=True),
            url_for("manager.landing", _external=True), url_for("support.support", _external=True)]
    urls += [url_for("investor.legal", doc=d, _external=True) for d in ("terms", "manager-terms", "privacy")]
    urls += [url_for("investor.article", slug=ARTICLE["slug"], _external=True)]
    urls += [url_for("investor.article", slug=a["slug"], _external=True) for a in learn_articles()]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + \
          "".join("<url><loc>%s</loc></url>" % u for u in urls) + "</urlset>"
    return Response(xml, mimetype="application/xml")


@bp.route("/robots.txt")
def robots():
    from flask import Response
    return Response("User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /managers/dashboard\nDisallow: /managers/funds\n"
                    "Disallow: /me\nDisallow: /login\nDisallow: /unsubscribe/\nSitemap: %s\n" % url_for("investor.sitemap", _external=True),
                    mimetype="text/plain")


# ---------------------------------------------------------------- calculator

@bp.route("/calculator", methods=("GET", "POST"))
def calculator():
    """
    Checks the SEC income and net worth tests. Figures entered are used for the
    result and then discarded - only the result and the email are kept.
    """
    if request.method == "POST":
        def num(k):
            try:
                return float(request.form.get(k, "0").replace(",", "").replace("$", "") or 0)
            except ValueError:
                return 0.0
        joint = request.form.get("joint") == "yes"
        income_ok = num("income_last") >= (300000 if joint else 200000) and num("income_prior") >= (300000 if joint else 200000) and request.form.get("income_expect") == "yes"
        net_worth = num("assets") - num("home_value") - (num("liabilities") - num("mortgage"))
        # Mortgage up to the home's value is excluded along with the home; the excess counts as a liability
        excess_mortgage = max(0.0, num("mortgage") - num("home_value"))
        net_worth -= excess_mortgage
        nw_ok = net_worth >= 1000000
        license_ok = request.form.get("license") == "yes"
        result = "accredited" if (income_ok or nw_ok or license_ok) else "not_accredited"
        basis = "income" if income_ok else ("net_worth" if nw_ok else ("license" if license_ok else None))
        email = request.form.get("email", "").strip().lower()
        if email and "@" in email and not request.form.get("consent"):
            flash("Please tick the box agreeing to receive your result and the educational emails, or leave the email blank.", "error")
            return redirect(url_for("investor.calculator"))
        if email and "@" in email:
            db = get_db()
            db.execute("INSERT INTO calculator_leads(email, result, basis, source, created_at, consent_at, consent_text, campaign) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (email, result, basis, (request.args.get("src") or session.get("src", ""))[:40].lower(), now(), now(), mail.CONSENT_CALCULATOR,
                        (session.get("campaign") or "")[:12]))
            db.commit()
            if mail.suppressed(email):
                # Rule 4.8: an unsubscribe is lifted only by the mailbox owner, through the link this sends.
                # The result email below is transactional and still goes; the weekly emails wait.
                from .support import send_resubscribe_link
                send_resubscribe_link(email)
            if result == "accredited":
                mail.send(email, "Your result: you may qualify as an accredited investor",
                          "Based on what you entered, you appear to meet the SEC's accredited investor definition (%s test).\n\n"
                          "This is not legal or investment advice, and a fund manager will verify your status before any investment.\n\n"
                          "What that means, and what to ask before wiring money into a private fund: %s\n\n%s"
                          % (basis.replace("_", " "), url_for("investor.home", _external=True), setting("company_name")))
            else:
                mail.send(email, "Your accredited investor result",
                          "Based on what you entered, you do not currently appear to meet the SEC's accredited investor tests.\n\n"
                          "The thresholds are $200,000 income ($300,000 joint) for two years, or $1,000,000 net worth excluding your home. "
                          "Nothing you entered was stored.\n\n%s" % setting("company_name"))
        return render_template("investor/calculator_result.html", result=result, basis=basis, open=signup_open())
    return render_template("investor/calculator.html")


# ---------------------------------------------------------------- sign-up

@bp.route("/signup", methods=("GET", "POST"))
def signup():
    if not signup_open():
        return render_template("investor/signup_closed.html")
    if request.method == "POST":
        basis = request.form.get("basis")
        if basis not in dict(ACCREDITATION_BASES):
            flash("Choose the basis on which you qualify as an accredited investor.", "error")
        elif not request.form.get("attest"):
            flash("Please confirm the attestation.", "error")
        elif not request.form.get("consent"):
            flash("Please agree to receive account notices by email; the account can't work without them.", "error")
        else:
            uid, err = create_user(request.form["email"], request.form["password"], "investor", request.form["name"], basis)
            if err:
                flash(err, "error")
            else:
                return render_template("auth/check_email.html", email=request.form["email"])
    return render_template("investor/signup.html", bases=ACCREDITATION_BASES)


# ---------------------------------------------------------------- catalog

def _number(text):
    text = (text or "").replace(",", "").replace("$", "").strip()
    try:
        v = float(text)
        return v if v > 0 else None
    except ValueError:
        return None


def criteria_for(investor_id):
    """The investor's own saved criteria (change 34), or None. They are filters the investor chose,
    applied in posting order; nothing here scores or ranks a fund (rule 4.1, section 5)."""
    row = get_db().execute("SELECT * FROM investor_criteria WHERE investor_id = ?", (investor_id,)).fetchone()
    if not row:
        return None
    return {"categories": [c for c in (row["categories"] or "").split("|") if c in CATEGORIES],
            "max_min": row["max_min"], "max_term": row["max_term"], "updated_at": row["updated_at"]}


# Yes / Maybe / No on a fund (change 34). Yes is the shortlist and Maybe is watch, so managers keep
# seeing anonymous counts exactly as before; No hides the fund from this investor and is never shown
# to anyone else.
ANSWERS = {"yes": "shortlist", "maybe": "watch"}


def answer_for(investor_id, fund_id):
    db = get_db()
    if db.execute("SELECT 1 FROM fund_passes WHERE investor_id = ? AND fund_id = ?", (investor_id, fund_id)).fetchone():
        return "no"
    kinds = {r["kind"] for r in db.execute("SELECT kind FROM interest WHERE investor_id = ? AND fund_id = ?", (investor_id, fund_id))}
    return "yes" if "shortlist" in kinds else "maybe" if "watch" in kinds else None


@bp.route("/funds")
@login_required("investor")
def catalog():
    db = get_db()
    q = "SELECT f.*, m.name AS firm_name, m.state AS firm_state FROM funds f JOIN firms m ON m.id = f.firm_id WHERE f.status IN ('live','paused')"
    args = []
    crit = criteria_for(g.user["id"])
    typed = any(request.args.get(k) for k in ("category", "max_min", "max_term"))
    # The investor's saved criteria are the starting filters; typing a filter or "Show all" sets them aside.
    using_criteria = bool(crit) and not typed and not request.args.get("all")
    cat = request.args.get("category")
    max_min = request.args.get("max_min")
    max_term = request.args.get("max_term")
    cats = [cat] if cat in CATEGORIES else []
    if using_criteria:
        cats = crit["categories"]
        max_min = "%g" % crit["max_min"] if crit["max_min"] else ""
        max_term = "%g" % crit["max_term"] if crit["max_term"] else ""
    if cats:
        q += " AND f.category IN (%s)" % ",".join("?" * len(cats))
        args += cats
    if _number(max_min):
        q += " AND (f.min_investment IS NULL OR f.min_investment <= ?)"
        args.append(_number(max_min))
    if _number(max_term):
        q += " AND (f.term_years IS NULL OR f.term_years <= ?)"
        args.append(_number(max_term))
    q += " ORDER BY f.live_since ASC, f.fund_number ASC"      # posting order. No ranking, ever.
    funds = db.execute(q, args).fetchall()
    passed = {r["fund_id"] for r in db.execute("SELECT fund_id FROM fund_passes WHERE investor_id = ?", (g.user["id"],))}
    hidden = sum(1 for f in funds if f["id"] in passed)
    if not request.args.get("show_no"):
        funds = [f for f in funds if f["id"] not in passed]
    marks = {(r["fund_id"], r["kind"]) for r in db.execute("SELECT fund_id, kind FROM interest WHERE investor_id = ?", (g.user["id"],))}
    requested = {r["fund_id"] for r in db.execute("SELECT fund_id FROM requests WHERE investor_id = ?", (g.user["id"],))}
    return render_template("investor/catalog.html", funds=funds, marks=marks, requested=requested, cat=cat if not using_criteria else None,
                           max_min=max_min, max_term=max_term, crit=crit, using_criteria=using_criteria, passed=passed, hidden=hidden,
                           show_no=bool(request.args.get("show_no")))


@bp.route("/criteria", methods=("GET", "POST"))
@login_required("investor")
def criteria():
    """What the investor is looking for. Saved as their own catalog filters (change 34)."""
    db = get_db()
    if request.method == "POST":
        cats = [c for c in request.form.getlist("categories") if c in CATEGORIES]
        db.execute("INSERT INTO investor_criteria(investor_id, categories, max_min, max_term, updated_at) VALUES (?, ?, ?, ?, ?)"
                   " ON CONFLICT(investor_id) DO UPDATE SET categories = excluded.categories, max_min = excluded.max_min,"
                   " max_term = excluded.max_term, updated_at = excluded.updated_at",
                   (g.user["id"], "|".join(cats), _number(request.form.get("max_min")), _number(request.form.get("max_term")), now()))
        audit("investor_criteria_saved", {"categories": len(cats)}, user_id=g.user["id"])
        db.commit()
        flash("Saved. The catalog now starts with funds that fit what you told us, in the order they were listed. You can always show all funds.", "ok")
        return redirect(url_for("investor.catalog"))
    return render_template("investor/criteria.html", crit=criteria_for(g.user["id"]) or {"categories": [], "max_min": None, "max_term": None})


@bp.route("/funds/<int:fund_id>/answer/<choice>", methods=("POST",))
@login_required("investor")
def answer(fund_id, choice):
    """Yes, Maybe, No, or clear: one answer per fund."""
    if choice not in ("yes", "maybe", "no", "clear"):
        abort(400)
    db = get_db()
    if not db.execute("SELECT 1 FROM funds WHERE id = ? AND status IN ('live','paused','closed')", (fund_id,)).fetchone():
        abort(404)
    uid = g.user["id"]
    db.execute("DELETE FROM interest WHERE investor_id = ? AND fund_id = ?", (uid, fund_id))
    db.execute("DELETE FROM fund_passes WHERE investor_id = ? AND fund_id = ?", (uid, fund_id))
    if choice in ANSWERS:
        db.execute("INSERT INTO interest(investor_id, fund_id, kind, created_at) VALUES (?, ?, ?, ?)", (uid, fund_id, ANSWERS[choice], now()))
    elif choice == "no":
        db.execute("INSERT INTO fund_passes(investor_id, fund_id, created_at) VALUES (?, ?, ?)", (uid, fund_id, now()))
    db.commit()
    if choice == "no":
        flash("Marked No. This fund is hidden from your catalog; you can undo it on My funds.", "ok")
    return redirect(request.referrer or url_for("investor.fund", fund_id=fund_id))


@bp.route("/funds/<int:fund_id>")
@login_required("investor")
def fund(fund_id):
    db = get_db()
    f = db.execute("SELECT f.*, m.name AS firm_name, m.website, m.description AS firm_description, m.state AS firm_state, m.principals"
                   " FROM funds f JOIN firms m ON m.id = f.firm_id WHERE f.id = ? AND f.status IN ('live','paused','closed')", (fund_id,)).fetchone()
    if not f:
        abort(404)
    db.execute("INSERT INTO fund_views(fund_id, investor_id, viewed_at) VALUES (?, ?, ?)", (fund_id, g.user["id"], now()))
    db.commit()
    marks = {r["kind"] for r in db.execute("SELECT kind FROM interest WHERE investor_id = ? AND fund_id = ?", (g.user["id"], fund_id))}
    choice = answer_for(g.user["id"], fund_id)
    req = db.execute("SELECT * FROM requests WHERE investor_id = ? AND fund_id = ?", (g.user["id"], fund_id)).fetchone()
    member_invested = f["founder_invested_at"]      # recorded by Luminaz on the review desk, never by the manager
    from .content.verification import ARTICLE
    return render_template("investor/fund.html", fund=f, marks=marks, req=req, member_invested=bool(member_invested), verification_slug=ARTICLE["slug"], choice=choice)


@bp.route("/funds/<int:fund_id>/mark/<kind>", methods=("POST",))
@login_required("investor")
def mark(fund_id, kind):
    if kind not in ("shortlist", "watch"):
        abort(400)
    db = get_db()
    # Only a fund investors can see; a draft, submitted or rejected fund's name must not leak through the shortlist.
    if not db.execute("SELECT 1 FROM funds WHERE id = ? AND status IN ('live','paused','closed')", (fund_id,)).fetchone():
        abort(404)
    exists = db.execute("SELECT 1 FROM interest WHERE investor_id = ? AND fund_id = ? AND kind = ?", (g.user["id"], fund_id, kind)).fetchone()
    if exists:
        db.execute("DELETE FROM interest WHERE investor_id = ? AND fund_id = ? AND kind = ?", (g.user["id"], fund_id, kind))
    else:
        db.execute("INSERT INTO interest(investor_id, fund_id, kind, created_at) VALUES (?, ?, ?, ?)", (g.user["id"], fund_id, kind, now()))
    db.commit()
    return redirect(request.referrer or url_for("investor.fund", fund_id=fund_id))


@bp.route("/funds/<int:fund_id>/request", methods=("POST",))
@login_required("investor")
def request_materials(fund_id):
    """The one moment an investor's name and email reach a manager."""
    db = get_db()
    f = db.execute("SELECT f.*, u.email AS manager_email, u.name AS manager_name FROM funds f JOIN firms m ON m.id = f.firm_id"
                   " JOIN users u ON u.id = m.owner_user_id WHERE f.id = ? AND f.status = 'live'", (fund_id,)).fetchone()
    if not f:
        abort(404)
    if db.execute("SELECT 1 FROM requests WHERE investor_id = ? AND fund_id = ?", (g.user["id"], fund_id)).fetchone():
        flash("You've already requested materials for this fund.", "ok")
        return redirect(url_for("investor.fund", fund_id=fund_id))
    msg = request.form.get("message", "").strip()[:1000]
    db.execute("INSERT INTO requests(fund_id, investor_id, message, created_at) VALUES (?, ?, ?, ?)", (fund_id, g.user["id"], msg, now()))
    audit("material_request", {"fund_id": fund_id}, user_id=g.user["id"])
    db.commit()
    mail.send(f["manager_email"], "Luminaz: an investor requested materials for %s" % f["name"],
              "%s (%s) has requested materials for %s.\n\nSelf-attested accreditation basis: %s. You are responsible for verifying "
              "accreditation before accepting any investment.\n\nTheir note: %s\n\nSee your pipeline: %s\n\n%s"
              % (g.user["name"], g.user["email"], f["name"], (g.user["accreditation_basis"] or "not stated").replace("_", " "),
                 msg or "(none)", url_for("manager.fund_detail", fund_id=fund_id, _external=True), setting("company_name")))
    mail.send(g.user["email"], "Your request was sent to %s" % f["firm_name"] if "firm_name" in f.keys() else "Your Luminaz request was sent",
              "Your request for materials on %s was sent to the fund manager, who will contact you directly. Luminaz is not part of that "
              "conversation and does not recommend any fund.\n\n%s" % (f["name"], setting("company_name")))
    flash("Sent. The manager will contact you directly.", "ok")
    return redirect(url_for("investor.fund", fund_id=fund_id))


# ---------------------------------------------------------------- installed-app counter

@bp.route("/app-event", methods=("POST",))
def app_event():
    """static/app.js posts here: 'installed' when someone adds Luminaz to a home screen, and 'opened'
    when they launch it from there. One row per visitor per day, using the same no-cookie hash as
    the page counter. It records nothing about the person."""
    kind = request.form.get("kind", "")
    if kind not in ("installed", "opened"):
        abort(400)
    if not is_bot(request.headers.get("User-Agent", "")):
        db = get_db()
        day = today()
        db.execute("INSERT OR IGNORE INTO app_events(day, kind, visitor) VALUES (?, ?, ?)", (day, kind, visitor_hash(day)))
        db.commit()
    return ("", 204)


@bp.route("/me")
@login_required("investor")
def me():
    db = get_db()
    paused = db.execute("SELECT paused_at FROM users WHERE id = ?", (g.user["id"],)).fetchone()["paused_at"]
    if paused:
        return render_template("investor/me.html", short=[], reqs=[], paused=paused, nos=[], crit=None)
    short = db.execute("SELECT f.*, i.kind FROM interest i JOIN funds f ON f.id = i.fund_id WHERE i.investor_id = ?"
                       " AND f.status IN ('live','paused','closed') ORDER BY i.created_at DESC", (g.user["id"],)).fetchall()
    reqs = db.execute("SELECT r.*, f.name FROM requests r JOIN funds f ON f.id = r.fund_id WHERE r.investor_id = ? ORDER BY r.created_at DESC", (g.user["id"],)).fetchall()
    nos = db.execute("SELECT f.* FROM fund_passes p JOIN funds f ON f.id = p.fund_id WHERE p.investor_id = ?"
                     " AND f.status IN ('live','paused','closed') ORDER BY p.created_at DESC", (g.user["id"],)).fetchall()
    return render_template("investor/me.html", short=short, reqs=reqs, paused=None, nos=nos, crit=criteria_for(g.user["id"]))


@bp.route("/legal/<doc>")
def legal(doc):
    import os
    allowed = {"terms": "investor_terms.md", "privacy": "privacy_policy.md", "manager-terms": "manager_terms.md", "listing-agreement": "listing_agreement.md"}
    if doc not in allowed:
        abort(404)
    path = os.path.join(os.path.dirname(__file__), "legal", allowed[doc])
    text = open(path, encoding="utf-8").read()
    return render_template("legal.html", text=text, doc=doc)
