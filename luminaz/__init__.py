"""Luminaz - where accredited investors discover private funds.

Two portals, one application:
  /            Luminaz (investors): calculator, catalog, shortlist, requests
  /managers    Luminaz for Fund Managers: listings, agreement, pipeline, invoices
  /admin       Luminaz review desk: approvals, mods, 506(d) checks, billing

Run locally:   py -3 run.py     then open http://127.0.0.1:5000
"""
import datetime as _dt
import gzip
import hashlib
import os
import secrets

from flask import Flask, abort, g, session, redirect, url_for, request

from . import db as dbm
from . import visitors


def create_app(test_config=None):
    # Tests pass INSTANCE_PATH (a temp folder) so nothing they create - uploads, backups, the
    # secret key - lands in the real instance folder next to real data. Normal runs leave it unset.
    app = Flask(__name__, instance_relative_config=True, instance_path=(test_config or {}).get("INSTANCE_PATH"))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("LUMINAZ_SECRET") or _load_or_make_secret(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "luminaz.sqlite"),
        MAIL_OUTBOX=os.path.join(app.instance_path, "outbox"),
        REPORTS_DIR=os.path.join(app.instance_path, "reports"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=bool(os.environ.get("LUMINAZ_HTTPS")),
        PREFERRED_URL_SCHEME="https" if os.environ.get("LUMINAZ_HTTPS") else "http",
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=26 * 1024 * 1024,
        SEND_FILE_MAX_AGE_DEFAULT=7 * 24 * 3600,     # static css/js cached a week; Flask adds ETags so edits still show
        TEMPLATES_AUTO_RELOAD=False,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    dbm.init_app(app)

    from . import auth, investor, manager, admin, billing, mail, support, webinars
    app.register_blueprint(auth.bp)
    app.register_blueprint(investor.bp)
    app.register_blueprint(manager.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(support.bp)
    app.register_blueprint(webinars.bp)
    mail.init_app(app)

    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("user_id")
        if uid:
            g.user = dbm.get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
            if g.user is None:
                session.clear()

    @app.before_request
    def route_by_host():
        """Two domains, one app. If both hosts are set, manager and admin paths
        live on the manager host and investor paths on the investor host."""
        inv_host = dbm.setting("investor_host", "") or ""
        mgr_host = dbm.setting("manager_host", "") or ""
        if not inv_host or not mgr_host:
            return None
        host = (request.host or "").split(":")[0].lower()
        path = request.path
        manager_side = path.startswith("/managers") or path.startswith("/admin") or path.startswith("/security")
        shared = path.startswith("/static") or path.startswith("/login") or path.startswith("/logout") \
            or path.startswith("/confirm") or path.startswith("/reset") or path.startswith("/forgot") \
            or path.startswith("/legal") or path.startswith("/support") or path.startswith("/unsubscribe") or path.startswith("/resubscribe") or path.startswith("/notifications") \
            or path.startswith("/app-event")
        if shared:
            return None
        if manager_side and host == inv_host.lower():
            return redirect("https://%s%s" % (mgr_host, request.full_path.rstrip("?")), code=302)
        if not manager_side and host == mgr_host.lower():
            if path == "/":
                return redirect(url_for("manager.landing"))
            return redirect("https://%s%s" % (inv_host, request.full_path.rstrip("?")), code=302)
        return None

    @app.before_request
    def block_cross_site_posts():
        """Cross-site request forgery guard: a form post must come from this site. Browsers send
        Sec-Fetch-Site / Origin on every post; a cross-site one is refused. Together with the
        SameSite=Lax cookie this covers CSRF without a token in every form. One-click unsubscribe
        posts come from mail servers, so that path is exempt."""
        if request.method not in ("POST", "PUT", "DELETE") or request.path.startswith("/unsubscribe/"):
            return None
        if app.config.get("TESTING") and not request.headers.get("Origin") and not request.headers.get("Sec-Fetch-Site"):
            return None
        sfs = request.headers.get("Sec-Fetch-Site")
        if sfs and sfs not in ("same-origin", "same-site", "none"):
            abort(403)
        origin = request.headers.get("Origin")
        if origin and origin.split("//")[-1].split("/")[0].lower() != (request.host or "").lower():
            abort(403)
        return None

    @app.before_request
    def remember_source():
        """?src=linkedin on any link is kept for the visit so the calculator lead records where it came from."""
        src = request.args.get("src")
        if src:
            session["src"] = src[:40].lower()        # lowercase, so "LinkedIn" on a link and "linkedin" on the spend form meet
        camp = request.args.get("p")
        if camp and camp.isdigit():
            session["campaign"] = camp[:12]           # the post the link came from, so the Communications page can credit it (change 33)

    @app.after_request
    def count_view(resp):
        """First-party traffic count: one row per page view, visitor = daily salted hash, no cookie, no third party.
        Static files, redirects, admin pages, and bots that identify themselves are skipped."""
        try:
            path = request.path
            if request.method != "GET" or resp.status_code != 200 or path.startswith(("/static", "/admin", "/robots", "/sitemap")):
                return resp
            if visitors.is_bot(request.headers.get("User-Agent", "")):
                return resp
            day = _dt.date.today().isoformat()
            visitor = visitors.visitor_hash(day)
            ref = request.referrer or ""
            src = session.get("src") or request.args.get("src") or ""
            if not src and ref and request.host not in ref:
                src = ref.split("/")[2] if "//" in ref else ref[:40]
            src = src.lower()
            camp = session.get("campaign") or (request.args.get("p") if (request.args.get("p") or "").isdigit() else "") or ""
            dbm.get_db().execute("INSERT INTO page_views(day, path, source, visitor, signed_in, campaign) VALUES (?, ?, ?, ?, ?, ?)",
                                 (day, path[:120], src[:60], visitor, 1 if g.get("user") else 0, camp[:12]))
            dbm.get_db().commit()
        except Exception:
            pass
        return resp

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("error.html", code=404, title="That page isn't here",
                               text="The link may be old or mistyped. The calculator, the guide, and the fund manager page are in the menu."), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("error.html", code=500, title="Something went wrong on our side",
                               text="It's been logged. Try again in a minute, or write to support if it keeps happening."), 500

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("error.html", code=403, title="You don't have access to that page",
                               text="If you think you should, sign in with the right account or contact support."), 403

    @app.context_processor
    def inject():
        host = dbm.setting("investor_host", "") or ""
        if host and (request.path.startswith("/managers") or request.path.startswith("/admin")):
            host = dbm.setting("manager_host", "") or host
        canonical = ("https://%s%s" % (host, request.path)) if host else request.base_url
        return {
            "canonical_url": canonical,
            "setting": dbm.setting,
            "founding_free_text": billing.founding_free_text,
            "categories": dbm.CATEGORIES,
            "category_notes": dbm.CATEGORY_NOTES,
            "company": dbm.setting("company_name", "Luminaz Technology LLC"),
            "now_year": _dt.date.today().year,
        }

    @app.template_filter("money")
    def money(v):
        if v in (None, ""):
            return "—"
        try:
            return "${:,.0f}".format(float(v))
        except (TypeError, ValueError):
            return str(v)

    @app.template_filter("date")
    def fmt_date(v):
        return (v or "")[:10]

    @app.after_request
    def headers(resp):
        if request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "public, max-age=604800"
        else:
            resp.headers["Cache-Control"] = "no-store"       # signed-in pages are never cached by proxies
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        # gzip text responses over 1 KB when the browser accepts it (hosts without a CDN in front)
        ct = resp.headers.get("Content-Type", "")
        if ("text/" in ct or "json" in ct) and "gzip" in request.headers.get("Accept-Encoding", "") \
                and not resp.direct_passthrough and resp.status_code == 200 and "Content-Encoding" not in resp.headers:
            data = resp.get_data()
            if len(data) > 1024:
                resp.set_data(gzip.compress(data, 6))
                resp.headers["Content-Encoding"] = "gzip"
                resp.headers["Vary"] = "Accept-Encoding"
                resp.headers["Content-Length"] = str(len(resp.get_data()))
        return resp

    from . import clock                 # change 30: the daily job and the evening report run inside the web service
    clock.start(app)
    return app


def _load_or_make_secret(instance_path):
    os.makedirs(instance_path, exist_ok=True)
    p = os.path.join(instance_path, "secret_key")
    if os.path.exists(p):
        return open(p).read().strip()
    key = secrets.token_hex(32)
    with open(p, "w") as fh:
        fh.write(key)
    return key
