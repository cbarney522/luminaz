"""Luminaz for Fund Managers - the manager portal."""
import hashlib
import json
import os
import secrets

from werkzeug.utils import secure_filename

from flask import (Blueprint, abort, flash, g, redirect, render_template, request,
                   url_for, current_app)

from .auth import login_required, create_user
from .db import get_db, now, audit, setting, CATEGORIES
from . import billing

bp = Blueprint("manager", __name__, url_prefix="/managers")

FUND_FIELDS = ["name", "category", "strategy", "target_raise", "min_investment", "term_years", "key_terms"]
NUMERIC = {"target_raise", "min_investment", "term_years"}
REVIEWED_TEXT = {"name", "category", "strategy", "key_terms"}   # always reviewed by Luminaz


def _firm():
    return get_db().execute("SELECT * FROM firms WHERE owner_user_id = ?", (g.user["id"],)).fetchone()


def _fund(fund_id, firm):
    f = get_db().execute("SELECT * FROM funds WHERE id = ? AND firm_id = ?", (fund_id, firm["id"])).fetchone()
    if not f:
        abort(404)
    return f


def _agreement_text():
    path = os.path.join(os.path.dirname(__file__), "legal", "listing_agreement.md")
    text = open(path, encoding="utf-8").read()
    version = text.splitlines()[0].replace("#", "").strip()
    return text, version, hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- public

@bp.route("/")
def landing():
    return render_template("manager/landing.html", slots_left=billing.founding_slots_left(), billing_status=billing.billing_status(),
                           slots=billing.slot_summary())


@bp.route("/signup", methods=("GET", "POST"))
def signup():
    if request.method == "POST":
        if not request.form.get("consent"):
            flash("Please agree to receive account notices by email; listings can't work without them.", "error")
            return render_template("manager/signup.html")
        uid, err = create_user(request.form["email"], request.form["password"], "manager", request.form["name"])
        if err:
            flash(err, "error")
        else:
            db = get_db()
            db.execute("INSERT INTO firms(owner_user_id, name, phone, state, created_at) VALUES (?, ?, ?, ?, ?)",
                       (uid, request.form["firm_name"].strip(), request.form.get("phone", "").strip(),
                        request.form.get("state", "").strip().upper()[:2], now()))
            db.commit()
            return render_template("auth/check_email.html", email=request.form["email"])
    return render_template("manager/signup.html")


# ---------------------------------------------------------------- dashboard

@bp.route("/dashboard")
@login_required("manager")
def dashboard():
    db = get_db()
    firm = _firm()
    if not firm:
        abort(403)
    funds = db.execute("SELECT * FROM funds WHERE firm_id = ? ORDER BY created_at DESC", (firm["id"],)).fetchall()
    # Six counts per fund in four grouped queries, whatever the number of funds.
    stats = {f["id"]: {"views": 0, "shortlist": 0, "watch": 0, "requests": 0, "new_requests": 0, "pending_mod": 0} for f in funds}
    if stats:
        fid = "SELECT id FROM funds WHERE firm_id = ?"
        for r in db.execute("SELECT fund_id, COUNT(*) AS n FROM fund_views WHERE fund_id IN (%s) GROUP BY fund_id" % fid, (firm["id"],)):
            stats[r["fund_id"]]["views"] = r["n"]
        for r in db.execute("SELECT fund_id, kind, COUNT(*) AS n FROM interest WHERE fund_id IN (%s) GROUP BY fund_id, kind" % fid, (firm["id"],)):
            stats[r["fund_id"]][r["kind"]] = r["n"]
        for r in db.execute("SELECT fund_id, COUNT(*) AS n, SUM(status = 'new') AS new_n FROM requests WHERE fund_id IN (%s) GROUP BY fund_id" % fid, (firm["id"],)):
            stats[r["fund_id"]]["requests"] = r["n"]; stats[r["fund_id"]]["new_requests"] = r["new_n"] or 0
        for r in db.execute("SELECT fund_id, COUNT(*) AS n FROM fund_mods WHERE status = 'pending' AND fund_id IN (%s) GROUP BY fund_id" % fid, (firm["id"],)):
            stats[r["fund_id"]]["pending_mod"] = r["n"]
    signed = db.execute("SELECT COUNT(*) FROM agreements WHERE firm_id = ?", (firm["id"],)).fetchone()[0]
    open_invoices = db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM invoices WHERE firm_id = ? AND status = 'open'", (firm["id"],)).fetchone()
    positions = {f["id"]: i + 1 for i, f in enumerate(billing.the_line())}
    return render_template("manager/dashboard.html", firm=firm, funds=funds, stats=stats, signed=signed,
                           open_invoices=open_invoices, rate=billing.rate_for_firm(firm),
                           free_months=billing.free_months_for(firm), slots_left=billing.founding_slots_left(),
                           billing_status=billing.billing_status(), slots=billing.slot_summary(), positions=positions)


# ---------------------------------------------------------------- firm profile

@bp.route("/firm", methods=("GET", "POST"))
@login_required("manager")
def firm_profile():
    db = get_db()
    firm = _firm()
    if request.method == "POST":
        fields = {k: request.form.get(k, "").strip() for k in ("name", "website", "phone", "address", "state", "description", "principals")}
        fields["state"] = fields["state"].upper()[:2]
        if firm["status"] == "approved":
            # Approved profiles keep showing until Luminaz reviews the change
            db.execute("UPDATE firms SET pending_changes = ? WHERE id = ?", (json.dumps(fields), firm["id"]))
            flash("Your changes were sent to Luminaz for review. Your current profile stays visible until they are approved.", "ok")
        else:
            db.execute("UPDATE firms SET name=?, website=?, phone=?, address=?, state=?, description=?, principals=?, status='pending' WHERE id = ?",
                       (*[fields[k] for k in ("name", "website", "phone", "address", "state", "description", "principals")], firm["id"]))
            flash("Firm profile saved and sent to Luminaz for review.", "ok")
        audit("firm_profile_saved", {"firm_id": firm["id"]}, user_id=g.user["id"])
        db.commit()
        return redirect(url_for("manager.dashboard"))
    return render_template("manager/firm.html", firm=firm)


# ---------------------------------------------------------------- listings

def _parse_fund_form(form):
    data, errors = {}, []
    for k in FUND_FIELDS:
        v = form.get(k, "").strip()
        if k in NUMERIC:
            v = v.replace(",", "").replace("$", "")
            if v:
                try:
                    v = float(v)
                except ValueError:
                    errors.append("%s must be a number." % k.replace("_", " ").capitalize())
                    v = None
            else:
                v = None
        data[k] = v
    if not data["name"]:
        errors.append("The fund needs a name.")
    if data["category"] not in CATEGORIES:
        errors.append("Choose one of the Luminaz categories.")
    if not data["term_years"]:
        errors.append("Luminaz lists closed-end funds only; enter the fund's term in years.")
    if not data["strategy"]:
        errors.append("Describe the strategy - investors read this first.")
    if not form.get("confirm_506c"):
        errors.append("Confirm the offering relies on Rule 506(c).")
    if not form.get("confirm_closed_end"):
        errors.append("Confirm the fund is closed-end with a defined term.")
    return data, errors


@bp.route("/funds/new", methods=("GET", "POST"))
@login_required("manager")
def new_fund():
    firm = _firm()
    if request.method == "POST":
        data, errors = _parse_fund_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("manager/fund_form.html", fund=data, firm=firm, is_new=True)
        db = get_db()
        cur = db.execute("INSERT INTO funds(firm_id, name, category, strategy, target_raise, min_investment, term_years, key_terms, status, created_at)"
                         " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                         (firm["id"], data["name"], data["category"], data["strategy"], data["target_raise"],
                          data["min_investment"], data["term_years"], data["key_terms"], now()))
        db.commit()
        return redirect(url_for("manager.sign", fund_id=cur.lastrowid))
    return render_template("manager/fund_form.html", fund={}, firm=firm, is_new=True)


@bp.route("/funds/<int:fund_id>")
@login_required("manager")
def fund_detail(fund_id):
    db = get_db()
    firm = _firm()
    fund = _fund(fund_id, firm)
    mods = db.execute("SELECT * FROM fund_mods WHERE fund_id = ? ORDER BY mod_number DESC", (fund_id,)).fetchall()
    reqs = db.execute("SELECT r.*, u.name AS investor_name, u.email AS investor_email, u.accreditation_basis AS investor_accreditation"
                      " FROM requests r JOIN users u ON u.id = r.investor_id"
                      " WHERE r.fund_id = ? ORDER BY r.created_at DESC", (fund_id,)).fetchall()
    agreement = db.execute("SELECT * FROM agreements WHERE fund_id = ?", (fund_id,)).fetchone()
    docs = db.execute("SELECT * FROM fund_documents WHERE fund_id = ? ORDER BY uploaded_at DESC", (fund_id,)).fetchall()
    counts = {
        "views": db.execute("SELECT COUNT(*) FROM fund_views WHERE fund_id = ?", (fund_id,)).fetchone()[0],
        "shortlist": db.execute("SELECT COUNT(*) FROM interest WHERE fund_id = ? AND kind = 'shortlist'", (fund_id,)).fetchone()[0],
        "watch": db.execute("SELECT COUNT(*) FROM interest WHERE fund_id = ? AND kind = 'watch'", (fund_id,)).fetchone()[0],
    }
    pause = billing.open_pause(fund_id) if fund["status"] == "paused" else None
    return render_template("manager/fund_detail.html", fund=fund, firm=firm, mods=mods, reqs=reqs,
                           agreement=agreement, counts=counts, docs=docs, doc_kinds=DOC_KINDS, json=json,
                           pause=pause, billing_status=billing.billing_status(), slots=billing.slot_summary(),
                           position=billing.line_position(fund_id))


@bp.route("/funds/<int:fund_id>/edit", methods=("GET", "POST"))
@login_required("manager")
def edit_fund(fund_id):
    db = get_db()
    firm = _firm()
    fund = _fund(fund_id, firm)
    if request.method == "POST":
        data, errors = _parse_fund_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("manager/fund_form.html", fund=data, firm=firm, is_new=False, fund_id=fund_id)
        if fund["status"] in ("draft", "rejected"):
            db.execute("UPDATE funds SET name=?, category=?, strategy=?, target_raise=?, min_investment=?, term_years=?, key_terms=? WHERE id = ?",
                       (*[data[k] for k in FUND_FIELDS], fund_id))
            db.commit()
            flash("Saved.", "ok")
            return redirect(url_for("manager.fund_detail", fund_id=fund_id))
        # Live listing: record a modification. Routine numeric fields auto-approve.
        changes = {k: {"from": fund[k], "to": data[k]} for k in FUND_FIELDS if (fund[k] or "") != (data[k] or "")}
        if not changes:
            flash("Nothing changed.", "ok")
            return redirect(url_for("manager.fund_detail", fund_id=fund_id))
        auto_fields = set((setting("auto_approve_fields") or "").split(","))
        auto = all(k in auto_fields for k in changes)
        mod_no = (db.execute("SELECT MAX(mod_number) FROM fund_mods WHERE fund_id = ?", (fund_id,)).fetchone()[0] or 0) + 1
        db.execute("INSERT INTO fund_mods(fund_id, mod_number, changes, status, submitted_at, decided_at, note)"
                   " VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (fund_id, mod_no, json.dumps(changes), "auto" if auto else "pending", now(),
                    now() if auto else None, "Routine field change, approved by rule" if auto else ""))
        if auto:
            sets = ", ".join("%s = ?" % k for k in changes)
            db.execute("UPDATE funds SET %s WHERE id = ?" % sets, (*[changes[k]["to"] for k in changes], fund_id))
            flash("Fund %s, mod %d applied. Routine changes go live right away." % (fund["fund_number"], mod_no), "ok")
        else:
            flash("Fund %s, mod %d sent to Luminaz for review. Your listing keeps showing its approved details until then."
                  % (fund["fund_number"], mod_no), "ok")
        audit("fund_mod", {"fund_id": fund_id, "mod": mod_no, "auto": auto}, user_id=g.user["id"])
        db.commit()
        return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    return render_template("manager/fund_form.html", fund=dict(fund), firm=firm, is_new=False, fund_id=fund_id)


@bp.route("/funds/<int:fund_id>/sign", methods=("GET", "POST"))
@login_required("manager")
def sign(fund_id):
    db = get_db()
    firm = _firm()
    fund = _fund(fund_id, firm)
    text, version, digest = _agreement_text()
    existing = db.execute("SELECT * FROM agreements WHERE fund_id = ?", (fund_id,)).fetchone()
    if existing:
        return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    if request.method == "POST":
        name = request.form.get("signer_name", "").strip()
        title = request.form.get("signer_title", "").strip()
        if not name or not title or not request.form.get("agree"):
            flash("Type your full legal name and title, and tick the box to sign.", "error")
        else:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
            db.execute("INSERT INTO agreements(firm_id, fund_id, signer_user_id, signer_name, signer_title, signed_at, ip_address, agreement_version, agreement_sha256)"
                       " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (firm["id"], fund_id, g.user["id"], name, title, now(), ip, version, digest))
            db.execute("UPDATE funds SET status = 'submitted', submitted_at = ? WHERE id = ?", (now(), fund_id))
            db.commit()
            firm = billing.assign_status_on_first_signature(firm["id"])
            audit("agreement_signed", {"fund_id": fund_id, "version": version}, user_id=g.user["id"])
            db.commit()
            flash("Signed. Your listing is with Luminaz for review; you'll get an email when it's live.", "ok")
            return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    return render_template("manager/sign.html", fund=fund, firm=firm, agreement=text, version=version,
                           rate=billing.rate_for_firm(firm), free_months=billing.free_months_for(firm),
                           founding=(firm["locked_rate"] is not None and firm["founding_manager"]) or (firm["locked_rate"] is None and billing.founding_slots_left() > 0),
                           billing_status=billing.billing_status())


@bp.route("/funds/<int:fund_id>/publish", methods=("POST",))
@login_required("manager")
def publish(fund_id):
    """The manager's final click. Nothing goes live without it."""
    firm = _firm()
    fund = _fund(fund_id, firm)
    if fund["status"] != "approved":
        flash("This listing isn't ready to publish yet.", "error")
        return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    result = billing.publish_fund(fund_id, g.user["id"])
    if result is True:
        f2 = get_db().execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
        flash("Published. %s is live as fund %s. Send your promotion kit to your investor list this week." % (f2["name"], f2["fund_number"]), "ok")
    elif result == "queued":
        # Every listing slot is taken (change 27): the click puts the fund in line, and it goes live by
        # itself when a slot opens, in the order of the clicks.
        s = billing.slot_summary()
        flash("Every one of the %d listing slots is taken, so %s is in line at position %d of %d. It goes live by itself when a slot "
              "opens, in the order managers clicked Publish; you'll get an email that day, and nothing is charged while you wait."
              % (s["cap"], fund["name"], billing.line_position(fund_id), s["line"]), "ok")
    else:
        flash("This listing can't be published right now; Luminaz needs to complete a check first and will contact you.", "error")
    return redirect(url_for("manager.fund_detail", fund_id=fund_id))


@bp.route("/funds/<int:fund_id>/leave-line", methods=("POST",))
@login_required("manager")
def leave_line(fund_id):
    """Take an approved fund out of the line. It stays approved; Publish rejoins at the back."""
    firm = _firm()
    _fund(fund_id, firm)
    if billing.leave_line(fund_id, g.user["id"]):
        flash("Taken out of the line. Your listing stays approved; click Publish whenever you want to join the line again.", "ok")
    else:
        flash("This listing isn't in the line.", "error")
    return redirect(url_for("manager.fund_detail", fund_id=fund_id))


@bp.route("/mods/<int:mod_id>/publish", methods=("POST",))
@login_required("manager")
def publish_mod(mod_id):
    db = get_db()
    firm = _firm()
    m = db.execute("SELECT md.* FROM fund_mods md JOIN funds f ON f.id = md.fund_id WHERE md.id = ? AND f.firm_id = ?", (mod_id, firm["id"])).fetchone()
    if not m or m["status"] != "approved":
        abort(404)
    changes = json.loads(m["changes"])
    sets = ", ".join("%s = ?" % k for k in changes)
    db.execute("UPDATE funds SET %s WHERE id = ?" % sets, (*[changes[k]["to"] for k in changes], m["fund_id"]))
    db.execute("UPDATE fund_mods SET status = 'published' WHERE id = ?", (mod_id,))
    audit("mod_published", {"mod_id": mod_id}, user_id=g.user["id"])
    db.commit()
    flash("Mod %d published." % m["mod_number"], "ok")
    return redirect(url_for("manager.fund_detail", fund_id=m["fund_id"]))


DOC_KINDS = [("ppm", "Private placement memorandum"), ("operating_agreement", "Operating agreement"),
             ("subscription_docs", "Subscription documents"), ("other", "Other")]
ALLOWED_EXT = {"pdf", "doc", "docx"}


@bp.route("/funds/<int:fund_id>/documents", methods=("POST",))
@login_required("manager")
def upload_document(fund_id):
    """Fund documents for Luminaz's vetting only. Investors never see them."""
    firm = _firm()
    fund = _fund(fund_id, firm)
    f = request.files.get("file")
    kind = request.form.get("kind", "other")
    if not f or not f.filename or kind not in dict(DOC_KINDS):
        flash("Choose a file and a document type.", "error")
        return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        flash("PDF or Word documents only.", "error")
        return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    data = f.read()
    if len(data) > 25 * 1024 * 1024:
        flash("That file is over 25 MB.", "error")
        return redirect(url_for("manager.fund_detail", fund_id=fund_id))
    digest = hashlib.sha256(data).hexdigest()
    stored = "%d_%s_%s.%s" % (fund_id, kind, secrets.token_hex(8), ext)
    folder = os.path.join(current_app.instance_path, "documents")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, stored), "wb") as fh:
        fh.write(data)
    db = get_db()
    db.execute("INSERT INTO fund_documents(fund_id, kind, filename, stored_name, size, sha256, uploaded_by, uploaded_at)"
               " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (fund_id, kind, secure_filename(f.filename), stored, len(data), digest, g.user["id"], now()))
    audit("document_uploaded", {"fund_id": fund_id, "kind": kind}, user_id=g.user["id"])
    db.commit()
    flash("Uploaded. Luminaz uses this for vetting only; investors receive documents from you.", "ok")
    return redirect(url_for("manager.fund_detail", fund_id=fund_id))


@bp.route("/funds/<int:fund_id>/close", methods=("POST",))
@login_required("manager")
def close_fund(fund_id):
    firm = _firm()
    fund = _fund(fund_id, firm)
    if fund["status"] in ("live", "paused"):
        final = billing.close_fund(fund_id, g.user["id"])
        msg = "Listing closed. Nothing is charged after today."
        if final:
            msg += " Your final invoice, ${:,.2f}, covers the days this month the listing was live.".format(final)
        flash(msg, "ok")
    return redirect(url_for("manager.fund_detail", fund_id=fund_id))


@bp.route("/funds/<int:fund_id>/pause", methods=("POST",))
@login_required("manager")
def pause_fund(fund_id):
    """Pause: the listing stays visible with a 'paused' label, investors can't request materials, and
    paused days are not charged. Resume any time. (Diane, 14 October 2026.)"""
    firm = _firm()
    fund = _fund(fund_id, firm)
    if billing.pause_fund(fund_id, g.user["id"]):
        flash("Paused. Your listing stays visible with a 'paused' label, investors can't request materials, and you aren't charged for paused days. Resume whenever you like.", "ok")
    else:
        flash("Only a live listing can be paused.", "error")
    return redirect(url_for("manager.fund_detail", fund_id=fund_id))


@bp.route("/funds/<int:fund_id>/resume", methods=("POST",))
@login_required("manager")
def resume_fund(fund_id):
    firm = _firm()
    fund = _fund(fund_id, firm)
    if billing.resume_fund(fund_id, g.user["id"]):
        flash("Resumed. Your listing takes requests again from today.", "ok")
    else:
        pause = billing.open_pause(fund_id)
        if pause and pause["reason"] == "admin":
            flash("This listing was suspended by Luminaz. Please contact support.", "error")
        else:
            flash("This listing is paused for an unpaid invoice; it takes requests again when the invoice is paid.", "error")
    return redirect(url_for("manager.fund_detail", fund_id=fund_id))


@bp.route("/requests/<int:req_id>/status", methods=("POST",))
@login_required("manager")
def request_status(req_id):
    db = get_db()
    firm = _firm()
    r = db.execute("SELECT r.* FROM requests r JOIN funds f ON f.id = r.fund_id WHERE r.id = ? AND f.firm_id = ?", (req_id, firm["id"])).fetchone()
    if not r:
        abort(404)
    status = request.form.get("status")
    if status in ("new", "contacted", "in_diligence", "invested", "passed"):
        db.execute("UPDATE requests SET status = ?, updated_at = ? WHERE id = ?", (status, now(), req_id))
        db.commit()
    return redirect(url_for("manager.fund_detail", fund_id=r["fund_id"]))


@bp.route("/invoices")
@login_required("manager")
def invoices():
    firm = _firm()
    return render_template("manager/invoices.html", firm=firm, invoices=billing.firm_invoices(firm["id"]))


@bp.route("/invoices/<int:invoice_id>")
@login_required("manager")
def invoice(invoice_id):
    db = get_db()
    firm = _firm()
    inv = db.execute("SELECT i.*, f.name AS fund_name, f.fund_number FROM invoices i LEFT JOIN funds f ON f.id = i.fund_id"
                     " WHERE i.id = ? AND i.firm_id = ?", (invoice_id, firm["id"])).fetchone()
    if not inv:
        abort(404)
    return render_template("manager/invoice.html", firm=firm, inv=inv)


@bp.route("/promotion-kit/<int:fund_id>")
@login_required("manager")
def promotion_kit(fund_id):
    firm = _firm()
    fund = _fund(fund_id, firm)
    link = url_for("investor.fund", fund_id=fund_id, _external=True)
    return render_template("manager/promotion_kit.html", fund=fund, firm=firm, link=link)
