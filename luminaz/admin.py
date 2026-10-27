"""Luminaz review desk: approvals, modifications, 506(d) checks, billing, settings."""
import datetime as dt
import json
import os
import sys

from flask import (Blueprint, abort, flash, g, redirect, render_template, request,
                   url_for, current_app, send_file)

from .auth import login_required
from .db import get_db, now, audit, setting, set_setting, DEFAULT_SETTINGS
from . import billing, mail

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required("admin")
def queue():
    db = get_db()
    firms = db.execute("SELECT f.*, u.email FROM firms f JOIN users u ON u.id = f.owner_user_id"
                       " WHERE f.status = 'pending' OR f.pending_changes IS NOT NULL ORDER BY f.created_at").fetchall()
    funds = db.execute("SELECT f.*, m.name AS firm_name, m.founding_manager FROM funds f JOIN firms m ON m.id = f.firm_id"
                       " WHERE f.status = 'submitted' ORDER BY f.submitted_at").fetchall()
    mods = db.execute("SELECT md.*, f.name AS fund_name, f.fund_number, m.name AS firm_name FROM fund_mods md"
                      " JOIN funds f ON f.id = md.fund_id JOIN firms m ON m.id = f.firm_id"
                      " WHERE md.status = 'pending' ORDER BY md.submitted_at").fetchall()
    live = db.execute("SELECT COUNT(*) FROM funds WHERE status = 'live'").fetchone()[0]
    investors = db.execute("SELECT COUNT(*) FROM users WHERE role = 'investor' AND email_confirmed = 1").fetchone()[0]
    leads = db.execute("SELECT COUNT(*) FROM calculator_leads").fetchone()[0]
    accredited = db.execute("SELECT COUNT(*) FROM calculator_leads WHERE result = 'accredited'").fetchone()[0]
    open_inv = db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM invoices WHERE status = 'open'").fetchone()
    late = db.execute("SELECT COUNT(*) FROM invoices WHERE status = 'open' AND due_at < ?", (now()[:10],)).fetchone()[0]
    reqs_month = db.execute("SELECT COUNT(*) FROM requests WHERE created_at >= date('now','-30 days')").fetchone()[0]
    line = billing.the_line()
    passed = {f["id"]: billing.passed_506d(f["id"]) for f in line}
    return render_template("admin/queue.html", firms=firms, funds=funds, mods=mods, live=live, investors=investors,
                           leads=leads, accredited=accredited, open_inv=open_inv, late=late, reqs_month=reqs_month,
                           slots_left=billing.founding_slots_left(), json=json, slots=billing.slot_summary(), line=line, passed=passed)


# ---------------------------------------------------------------- firms

@bp.route("/firms/<int:firm_id>", methods=("GET", "POST"))
@login_required("admin")
def firm(firm_id):
    db = get_db()
    f = db.execute("SELECT f.*, u.email FROM firms f JOIN users u ON u.id = f.owner_user_id WHERE f.id = ?", (firm_id,)).fetchone()
    if not f:
        abort(404)
    if request.method == "POST":
        action = request.form["action"]
        if action == "approve":
            new_people = False
            if f["pending_changes"]:
                ch = json.loads(f["pending_changes"])
                new_people = (ch.get("principals") or "").strip() != (f["principals"] or "").strip()
                db.execute("UPDATE firms SET name=?, website=?, phone=?, address=?, state=?, description=?, principals=?, pending_changes=NULL WHERE id = ?",
                           (ch["name"], ch["website"], ch["phone"], ch["address"], ch["state"], ch["description"], ch["principals"], firm_id))
            db.execute("UPDATE firms SET status = 'approved' WHERE id = ?", (firm_id,))
            flash("Firm approved.", "ok")
            if new_people:
                # Rule 4.6: a new covered person needs a new 506(d) check. Each of the firm's approved or
                # listed funds gets an open check (no determination), which closes the publish gate on an
                # approved fund and shows on the fund page until a person records a new determination.
                affected = db.execute("SELECT id, name FROM funds WHERE firm_id = ? AND status IN ('approved','live','paused')", (firm_id,)).fetchall()
                for fund in affected:
                    db.execute("INSERT INTO bad_actor_checks(fund_id, subjects, created_at) VALUES (?, ?, ?)",
                               (fund["id"], (ch.get("principals") or "").strip(), now()))
                if affected:
                    flash("The principals changed. Run the 506(d) check again and record a determination on: %s."
                          % ", ".join(x["name"] for x in affected), "error")
        elif action == "reject":
            db.execute("UPDATE firms SET status = 'rejected', pending_changes = NULL WHERE id = ?", (firm_id,))
            flash("Firm rejected.", "ok")
        audit("firm_" + action, {"firm_id": firm_id}, user_id=g.user["id"])
        db.commit()
        return redirect(url_for("admin.queue"))
    funds = db.execute("SELECT * FROM funds WHERE firm_id = ? ORDER BY created_at", (firm_id,)).fetchall()
    pending = json.loads(f["pending_changes"]) if f["pending_changes"] else None
    return render_template("admin/firm.html", firm=f, funds=funds, pending=pending, invoices=billing.firm_invoices(firm_id))


# ---------------------------------------------------------------- funds

@bp.route("/funds/<int:fund_id>", methods=("GET", "POST"))
@login_required("admin")
def fund(fund_id):
    db = get_db()
    f = db.execute("SELECT f.*, m.name AS firm_name, m.principals, m.state AS firm_state, m.founding_manager, m.id AS firm_id_"
                   " FROM funds f JOIN firms m ON m.id = f.firm_id WHERE f.id = ?", (fund_id,)).fetchone()
    if not f:
        abort(404)
    agreement = db.execute("SELECT * FROM agreements WHERE fund_id = ?", (fund_id,)).fetchone()
    check = db.execute("SELECT * FROM bad_actor_checks WHERE fund_id = ? ORDER BY created_at DESC", (fund_id,)).fetchone()
    owner = db.execute("SELECT u.* FROM users u JOIN firms m ON m.owner_user_id = u.id WHERE m.id = ?", (f["firm_id"],)).fetchone()
    if request.method == "POST":
        action = request.form["action"]
        if action == "approve":
            if f["status"] != "submitted":
                flash("Only a submitted listing can be approved.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            if not agreement:
                flash("No signed listing agreement on file. It cannot go live.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            if not billing.passed_506d(fund_id):
                flash("Record a passing 506(d) determination before approving.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            firm_status = db.execute("SELECT status FROM firms WHERE id = ?", (f["firm_id"],)).fetchone()["status"]
            if firm_status != "approved":
                flash("Approve the firm profile first; investors see the firm's name and description on the listing.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            db.execute("UPDATE agreements SET luminaz_countersigned_at = ?, luminaz_countersigner = ? WHERE id = ?",
                       (now(), g.user["id"], agreement["id"]))
            billing.approve_fund(fund_id, g.user["id"])
            mail.send(owner["email"], "Luminaz approved your listing - one click to publish",
                      "%s has passed Luminaz review. Nothing appears to investors until you publish it.\n\n"
                      "Sign in, open the fund, and click Publish: %s\n\nYour free period and fund number start the day you publish. "
                      "Your promotion kit will be ready on the same page.\n\n%s"
                      % (f["name"], url_for("manager.fund_detail", fund_id=fund_id, _external=True), setting("company_name")))
            flash("Approved. The manager has been emailed to publish.", "ok")
        elif action == "reject":
            # Submitted: declined. Approved but not yet published: withdrawn before it ever went live.
            if f["status"] not in ("submitted", "approved"):
                flash("Only a submitted or approved (not yet published) listing can be rejected.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            note = request.form.get("note", "").strip()
            db.execute("UPDATE funds SET status = 'rejected', rejection_note = ? WHERE id = ?", (note, fund_id))
            mail.send(owner["email"], "About your Luminaz listing",
                      "Thank you for submitting %s. We are not able to list it at this time.\n\n%s\n\n%s" % (f["name"], note, setting("company_name")))
            flash("Fund rejected; the manager has been emailed.", "ok")
        elif action == "suspend":
            # Listing agreement 3.2: Luminaz may suspend a live listing. It stays visible with the
            # paused label, takes no requests, and paused days are not charged. Only Luminaz lifts it.
            note = request.form.get("note", "").strip()
            if not billing.pause_fund(fund_id, g.user["id"], reason="admin"):
                flash("Only a live listing can be suspended.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            mail.send(owner["email"], "Luminaz has suspended your listing: %s" % f["name"],
                      "Luminaz has suspended %s under the listing agreement. Investors see it marked paused and cannot request "
                      "materials; you are not charged for suspended days.\n\n%s\n\nReply to this email or write to %s.\n\n%s"
                      % (f["name"], note or "Please contact us for the reason and what would need to change.", setting("support_email"), setting("company_name")))
            flash("Suspended. The manager has been emailed.", "ok")
        elif action == "resume":
            pause = billing.open_pause(fund_id)
            if not pause or pause["reason"] != "admin" or not billing.resume_fund(fund_id, g.user["id"], by_manager=False):
                flash("Only a listing suspended by Luminaz can be resumed here. A non-payment pause ends when the invoice is paid.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            mail.send(owner["email"], "Your Luminaz listing is live again: %s" % f["name"],
                      "The suspension of %s has been lifted. Investors can request materials again from today.\n\n%s" % (f["name"], setting("company_name")))
            flash("Resumed. The manager has been emailed.", "ok")
        elif action == "remove":
            # Listing agreement 3.2: Luminaz may remove a listing. Same money rules as a manager's
            # close: the days it was live this month are invoiced, nothing after today.
            if f["status"] not in ("live", "paused"):
                flash("Only a live or paused listing can be removed. Use Reject for one that never went live.", "error")
                return redirect(url_for("admin.fund", fund_id=fund_id))
            note = request.form.get("note", "").strip()
            final = billing.close_fund(fund_id, g.user["id"])
            audit("fund_removed_by_luminaz", {"fund_id": fund_id, "final_invoice": final}, user_id=g.user["id"])
            mail.send(owner["email"], "Luminaz has removed your listing: %s" % f["name"],
                      "Luminaz has removed %s from the catalog under the listing agreement. Nothing is charged after today.\n\n%s\n\n"
                      "Reply to this email or write to %s.\n\n%s"
                      % (f["name"], note or "Please contact us for the reason.", setting("support_email"), setting("company_name")))
            flash("Removed from the catalog. The manager has been emailed.", "ok")
        elif action == "disclosure":
            # The "a member of Luminaz has invested" notice on the public fund page. Recorded here by a
            # founder, never derived from anything a manager can set (the manager's pipeline is theirs).
            on = request.form.get("founder_invested") == "1"
            db.execute("UPDATE funds SET founder_invested_at = ? WHERE id = ?", (now() if on else None, fund_id))
            flash("Disclosure recorded: the fund page %s the notice." % ("shows" if on else "no longer shows"), "ok")
        elif action == "determination":
            det = request.form.get("determination", "")
            notes = request.form.get("notes", "")
            subjects = request.form.get("subjects", "")
            if check and not check["determination"]:
                db.execute("UPDATE bad_actor_checks SET determination = ?, notes = ?, reviewer_id = ?, decided_at = ? WHERE id = ?",
                           (det, notes, g.user["id"], now(), check["id"]))
            else:
                db.execute("INSERT INTO bad_actor_checks(fund_id, subjects, determination, reviewer_id, notes, created_at, decided_at)"
                           " VALUES (?, ?, ?, ?, ?, ?, ?)", (fund_id, subjects, det, g.user["id"], notes, now(), now()))
            flash("506(d) determination recorded.", "ok")
            db.commit()
            if billing.fill_slots():        # a fund in line may have been waiting on this pass (change 27)
                flash("A listing in line went live on this determination; the manager has been emailed.", "ok")
        elif action == "run_check":
            path, err = _run_bad_actor_agent(f, request.form.get("subjects", ""))
            if err:
                flash("The 506(d) agent could not run: %s. Use the manual links and record your determination." % err, "error")
            else:
                db.execute("INSERT INTO bad_actor_checks(fund_id, report_path, subjects, created_at) VALUES (?, ?, ?, ?)",
                           (fund_id, path, request.form.get("subjects", ""), now()))
                flash("506(d) report generated. Open it, read it, then record the determination.", "ok")
        audit("fund_" + action, {"fund_id": fund_id}, user_id=g.user["id"])
        db.commit()
        return redirect(url_for("admin.fund", fund_id=fund_id))
    mods = db.execute("SELECT * FROM fund_mods WHERE fund_id = ? ORDER BY mod_number DESC", (fund_id,)).fetchall()
    docs = db.execute("SELECT d.*, u.name AS uploader FROM fund_documents d JOIN users u ON u.id = d.uploaded_by WHERE d.fund_id = ? ORDER BY d.kind", (fund_id,)).fetchall()
    flags = screen_text((f["strategy"] or "") + " " + (f["key_terms"] or "") + " " + (f["name"] or ""))
    default_subjects = "\n".join(x.strip() for x in (f["principals"] or "").replace(";", "\n").splitlines() if x.strip())
    return render_template("admin/fund.html", fund=f, agreement=agreement, check=check, mods=mods, owner=owner,
                           default_subjects=default_subjects, docs=docs, flags=flags, json=json,
                           pause=billing.open_pause(fund_id) if f["status"] == "paused" else None, passed=billing.passed_506d(fund_id),
                           position=billing.line_position(fund_id), slots=billing.slot_summary())


RED_FLAGS = [
    (r"\bguarantee[ds]?\b", "guarantee"), (r"\bsafe\b|\brisk[- ]free\b|\bno risk\b", "safety claim"),
    (r"\b\d{1,3}(\.\d+)?\s?%\s*(irr|return|yield|annual|per year|target)", "projected return"),
    (r"\birr\b|\bmoic\b|\bmultiple\b|\btarget(ed)? return", "performance projection"),
    (r"\bsec[- ]approved\b|\bapproved by the sec\b|\bfinra[- ]approved\b", "regulator approval claim"),
    (r"\bvetted by luminaz\b|\bluminaz[- ]approved\b|\bendorsed\b", "platform endorsement claim"),
    (r"\bbank\b.*\b(cd|deposit|savings)\b|\bfdic\b", "bank product comparison"),
    (r"\bcan.t lose\b|\bnever lost\b|\bzero losses\b", "loss denial"),
]


# Added for Luminaz's own posts and pages (rule 4.10, change 29): claims Luminaz must never make about itself.
POST_FLAGS = [
    (r"\b(we|luminaz)\s+(find|finds|deliver|delivers|introduce|introduces|match|matches|bring|brings|source|sources)\b.{0,30}\binvestors?\b", "claims to find or deliver investors"),
    (r"\bverified (accredited )?investors?\b|\bverified by luminaz\b", "says investors are verified (rule 4.5: self-attested)"),
    (r"\bvetted\b", "\"vetted\" (say what is checked)"),
    (r"\b(approved|endorsed|recommended|safe) funds?\b|\bfunds? (we|luminaz) recommends?\b", "endorses a fund"),
    (r"\btop funds?\b|\bbest funds?\b|\bfeatured funds?\b", "ranks or features a fund (rule 4.1)"),
]


def screen_text(text, extra=()):
    """Marketing-language screen: flags phrases the reviewer must read. Not a decision."""
    import re
    found = []
    for pattern, label in list(RED_FLAGS) + list(extra):
        m = re.search(pattern, text, re.I)
        if m:
            found.append((label, text[max(0, m.start() - 40):m.end() + 40].strip()))
    return found


@bp.route("/documents/<int:doc_id>")
@login_required("admin")
def document(doc_id):
    db = get_db()
    d = db.execute("SELECT * FROM fund_documents WHERE id = ?", (doc_id,)).fetchone()
    if not d:
        abort(404)
    db.execute("UPDATE fund_documents SET reviewed_by = ?, reviewed_at = ? WHERE id = ? AND reviewed_at IS NULL", (g.user["id"], now(), doc_id))
    db.commit()
    return send_file(os.path.join(current_app.instance_path, "documents", d["stored_name"]), download_name=d["filename"], as_attachment=True)


def _run_bad_actor_agent(fund, subjects_text):
    """Import the standalone agent if it is installed beside the app; otherwise say so."""
    people = [s.strip() for s in subjects_text.splitlines() if s.strip()]
    candidates = [
        os.path.join(os.path.dirname(current_app.root_path), "agents", "bad_actor_agent"),
        os.path.join(os.path.dirname(os.path.dirname(current_app.root_path)), "agents", "bad_actor_agent"),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "luminaz_bad_actor_agent.py")):
            sys.path.insert(0, c)
            try:
                import luminaz_bad_actor_agent as agent
                out_dir = current_app.config["REPORTS_DIR"]
                path, _ = agent.check(fund["name"], people, fund["firm_state"] or "", out_dir)
                return path, None
            except Exception as e:  # network blocked, etc.
                return None, str(e)
    return None, "agent not found next to the app (expected agents/bad_actor_agent/)"


@bp.route("/reports/<path:name>")
@login_required("admin")
def report(name):
    path = os.path.join(current_app.config["REPORTS_DIR"], os.path.basename(name))
    if not os.path.exists(path):
        abort(404)
    return send_file(path)


# ---------------------------------------------------------------- mods

@bp.route("/mods/<int:mod_id>", methods=("POST",))
@login_required("admin")
def mod(mod_id):
    db = get_db()
    m = db.execute("SELECT * FROM fund_mods WHERE id = ?", (mod_id,)).fetchone()
    if not m or m["status"] != "pending":
        abort(404)
    action = request.form["action"]
    changes = json.loads(m["changes"])
    if action == "approve":
        db.execute("UPDATE fund_mods SET status = 'approved', decided_at = ?, decided_by = ? WHERE id = ?", (now(), g.user["id"], mod_id))
        owner = db.execute("SELECT u.email FROM users u JOIN firms m ON m.owner_user_id = u.id JOIN funds f ON f.firm_id = m.id WHERE f.id = ?", (m["fund_id"],)).fetchone()
        mail.send(owner["email"], "Luminaz approved your listing change - click to publish",
                  "Mod %d is approved. It appears to investors when you click Publish on the fund page: %s\n\n%s"
                  % (m["mod_number"], url_for("manager.fund_detail", fund_id=m["fund_id"], _external=True), setting("company_name")))
        flash("Mod %d approved; the manager publishes it." % m["mod_number"], "ok")
    else:
        db.execute("UPDATE fund_mods SET status = 'rejected', decided_at = ?, decided_by = ?, note = ? WHERE id = ?",
                   (now(), g.user["id"], request.form.get("note", ""), mod_id))
        flash("Mod %d rejected." % m["mod_number"], "ok")
    audit("mod_" + action, {"mod_id": mod_id}, user_id=g.user["id"])
    db.commit()
    return redirect(url_for("admin.queue"))


# ---------------------------------------------------------------- billing

@bp.route("/billing", methods=("GET", "POST"))
@login_required("admin")
def billing_page():
    db = get_db()
    if request.method == "POST":
        if request.form["action"] == "run":
            r = billing.run_billing(admin_id=g.user["id"])
            flash("Billing run for %s: %d invoices issued, %d funds paused, %d resumed." % (r["month"], r["issued"], r["paused"], r["resumed"]), "ok")
        elif request.form["action"] == "pay":
            billing.record_payment(int(request.form["invoice_id"]), request.form.get("method", "bank transfer"), g.user["id"])
            flash("Payment recorded.", "ok")
        return redirect(url_for("admin.billing_page"))
    invoices = db.execute("SELECT i.*, m.name AS firm_name, f.name AS fund_name, f.fund_number FROM invoices i"
                          " JOIN firms m ON m.id = i.firm_id LEFT JOIN funds f ON f.id = i.fund_id"
                          " ORDER BY i.status = 'paid', i.due_at").fetchall()
    start = billing.billing_start(record=False)
    billing_on = start is not None and start <= dt.date.today()
    live_total = db.execute("SELECT COALESCE(SUM(monthly_rate),0) FROM funds WHERE status = 'live' AND (free_until IS NULL OR free_until <= date('now'))").fetchone()[0]
    still_free = db.execute("SELECT COALESCE(SUM(monthly_rate),0) FROM funds WHERE status = 'live' AND free_until > date('now')").fetchone()[0]
    mrr, upcoming = (live_total, still_free) if billing_on else (0, live_total + still_free)
    return render_template("admin/billing.html", invoices=invoices, mrr=mrr, upcoming=upcoming, today=now()[:10],
                           billing_status=billing.billing_status(), ready=billing.readiness())


# ---------------------------------------------------------------- investors, leads, settings

@bp.route("/investors")
@login_required("admin")
def investors():
    db = get_db()
    # One grouped query per count instead of two subqueries per investor row.
    inv = db.execute("SELECT u.*, COALESCE(r.n, 0) AS requests, COALESCE(i.n, 0) AS marks FROM users u"
                     " LEFT JOIN (SELECT investor_id, COUNT(*) AS n FROM requests GROUP BY investor_id) r ON r.investor_id = u.id"
                     " LEFT JOIN (SELECT investor_id, COUNT(*) AS n FROM interest GROUP BY investor_id) i ON i.investor_id = u.id"
                     " WHERE u.role = 'investor' ORDER BY u.created_at DESC LIMIT 1000").fetchall()
    total = db.execute("SELECT COUNT(*) FROM users WHERE role = 'investor'").fetchone()[0]
    leads = db.execute("SELECT * FROM calculator_leads ORDER BY created_at DESC LIMIT 500").fetchall()
    return render_template("admin/investors.html", investors=inv, leads=leads, total=total)


@bp.route("/settings", methods=("GET", "POST"))
@login_required("admin")
def settings():
    if request.method == "POST":
        if request.form.get("action") == "dates":
            # The two dates that start billing live in their own form (a page opened before the daily
            # job recorded them must not write them back blank). A date must be a real date or blank.
            for k in ("catalog_opened_on", "billing_starts_on"):
                v = request.form.get(k, "").strip()
                if v:
                    try:
                        dt.date.fromisoformat(v)
                    except ValueError:
                        flash("%s must be a date like 2027-03-01, or blank." % k.replace("_", " ").capitalize(), "error")
                        return redirect(url_for("admin.settings"))
                set_setting(k, v)
            audit("billing_dates_changed", {k: request.form.get(k, "").strip() for k in ("catalog_opened_on", "billing_starts_on")}, user_id=g.user["id"])
            get_db().commit()
            flash("Dates saved.", "ok")
            return redirect(url_for("admin.settings"))
        for k in DEFAULT_SETTINGS:
            if k in request.form and k not in ("catalog_opened_on", "billing_starts_on"):
                set_setting(k, request.form[k].strip())
        audit("settings_changed", user_id=g.user["id"])
        get_db().commit()
        flash("Settings saved.", "ok")
        went = billing.fill_slots()         # a higher slot count lets funds in line go live (change 27)
        if went:
            flash("%d listing%s in line went live under the new slot count; the managers have been emailed." % (went, "" if went == 1 else "s"), "ok")
        return redirect(url_for("admin.settings"))
    vals = {k: setting(k, v) for k, v in DEFAULT_SETTINGS.items()}
    from . import clock
    return render_template("admin/settings.html", vals=vals, clock=clock.status())


# ---------------------------------------------------------------- manager outreach

OUTREACH_STATUSES = ["new", "drafted", "sent", "followup_drafted", "followed_up", "yes", "no", "later", "listed", "do_not_contact"]


@bp.route("/outreach", methods=("GET", "POST"))
@login_required("admin")
def outreach():
    """Lead list from the Form D agent. The agent drafts; you approve and send."""
    import csv
    import io
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "import":
            f = request.files.get("csv")
            added = skipped = 0
            if f:
                text = f.read().decode("utf-8-sig", errors="replace")
                for r in csv.DictReader(io.StringIO(text)):
                    name = (r.get("fund_name") or r.get("Fund") or "").strip()
                    if not name:
                        continue
                    if db.execute("SELECT 1 FROM outreach WHERE fund_name = ?", (name,)).fetchone():
                        skipped += 1
                        continue
                    people = (r.get("people") or "").strip()
                    contact = (r.get("signer") or r.get("contact_name") or people.split(";")[0].split(",")[0]).strip()
                    db.execute("INSERT INTO outreach(contact_name, firm_name, fund_name, email, phone, category, target_raise,"
                               " filed, filing_url, source, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                               (contact, (r.get("firm_name") or "").strip(), name, (r.get("email") or "").strip().lower(),
                                (r.get("phone") or "").strip(), (r.get("luminaz_category") or r.get("category") or "").strip(),
                                (r.get("total_offering") or r.get("target_raise") or "").strip(), (r.get("filed") or "").strip(),
                                (r.get("filing_url") or "").strip(), "form_d", (r.get("notes") or "").strip(), now()))
                    added += 1
            audit("outreach_import", {"added": added, "skipped": skipped}, user_id=g.user["id"])
            db.commit()
            flash("Imported %d leads (%d already on the list)." % (added, skipped), "ok")
        elif action == "add":
            db.execute("INSERT INTO outreach(contact_name, firm_name, fund_name, email, phone, category, source, created_at)"
                       " VALUES (?,?,?,?,?,?,?,?)",
                       (request.form.get("contact_name", "").strip(), request.form.get("firm_name", "").strip(),
                        request.form.get("fund_name", "").strip(), request.form.get("email", "").strip().lower(),
                        request.form.get("phone", "").strip(), request.form.get("category", "").strip(), "manual", now()))
            db.commit()
            flash("Lead added.", "ok")
        elif action == "draft_all":
            n = 0
            for o in db.execute("SELECT * FROM outreach WHERE status = 'new' AND email != ''").fetchall():
                _draft_lead(db, dict(o))
                n += 1
            db.commit()
            flash("Drafted %d emails. Open each one to approve and send." % n, "ok")
        return redirect(url_for("admin.outreach"))
    status = request.args.get("status", "")
    q = "SELECT * FROM outreach"
    args = ()
    if status:
        q += " WHERE status = ?"
        args = (status,)
    rows = db.execute(q + " ORDER BY CASE status WHEN 'followup_drafted' THEN 0 WHEN 'drafted' THEN 0 WHEN 'new' THEN 1 ELSE 2 END, updated_at DESC, id DESC", args).fetchall()
    counts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) AS n FROM outreach GROUP BY status")}
    return render_template("admin/outreach.html", rows=rows, counts=counts, statuses=OUTREACH_STATUSES, filter=status, held=mail.marketing_block())


def _draft_lead(db, o):
    from .content import outreach as content
    subject, body = content.draft(o, setting("founder_name"), setting("founder_signature"),
                                  url_for("manager.landing", _external=True), credit=bool(o.get("credit_offered")),
                                  subject_t=setting("outreach_subject", ""), body_t=setting("outreach_body", ""),
                                  rate="${:,.0f}".format(billing.quoted_rate()), founding_cap=setting("founding_manager_cap"),
                                  free_months=setting("founding_free_months"))
    db.execute("UPDATE outreach SET draft_subject = ?, draft_body = ?, status = 'drafted', updated_at = ? WHERE id = ?",
               (subject, body, now(), o["id"]))
    return subject, body


@bp.route("/outreach/<int:lead_id>", methods=("GET", "POST"))
@login_required("admin")
def outreach_lead(lead_id):
    db = get_db()
    o = db.execute("SELECT * FROM outreach WHERE id = ?", (lead_id,)).fetchone()
    if not o:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            db.execute("UPDATE outreach SET contact_name=?, firm_name=?, fund_name=?, email=?, phone=?, category=?, notes=?,"
                       " credit_offered=?, updated_at=? WHERE id=?",
                       (request.form.get("contact_name", "").strip(), request.form.get("firm_name", "").strip(),
                        request.form.get("fund_name", "").strip(), request.form.get("email", "").strip().lower(),
                        request.form.get("phone", "").strip(), request.form.get("category", "").strip(),
                        request.form.get("notes", "").strip(), 1 if request.form.get("credit_offered") else 0, now(), lead_id))
            flash("Saved.", "ok")
        elif action == "draft":
            o2 = db.execute("SELECT * FROM outreach WHERE id = ?", (lead_id,)).fetchone()
            _draft_lead(db, dict(o2))
            flash("Draft written. Edit it if you like, then approve and send.", "ok")
        elif action == "send":
            o2 = db.execute("SELECT * FROM outreach WHERE id = ?", (lead_id,)).fetchone()
            subject = request.form.get("draft_subject", o2["draft_subject"]).strip()
            body = request.form.get("draft_body", o2["draft_body"]).strip()
            if not o2["email"]:
                flash("No email address on this lead. Add one first.", "error")
            elif not subject or not body:
                flash("Nothing to send yet. Draft the email first.", "error")
            elif mail.suppressed(o2["email"]):
                flash("This address asked not to be contacted. It stays on the do-not-contact list.", "error")
            elif mail.marketing_block():
                db.execute("UPDATE outreach SET draft_subject=?, draft_body=?, updated_at=? WHERE id=?", (subject, body, now(), lead_id))
                flash("Not sent: %s. The draft is saved." % mail.marketing_block(), "error")
            else:
                import secrets
                token = o2["unsub_token"] or ("o" + secrets.token_urlsafe(24))
                mail.send(o2["email"], subject, body, kind="marketing",
                          unsubscribe_url=url_for("support.unsubscribe", token=token, _external=True))
                db.execute("UPDATE outreach SET draft_subject=?, draft_body=?, status='sent', sent_at=?, updated_at=?, unsub_token=? WHERE id=?",
                           (subject, body, now(), now(), token, lead_id))
                audit("outreach_sent", {"lead_id": lead_id, "email": o2["email"]}, user_id=g.user["id"])
                flash("Sent to %s. If they don't reply, a follow-up is drafted for your approval in %s days." % (o2["email"], setting("outreach_followup_days")), "ok")
        elif action == "send_followup":
            # Rule 4.7: the daily job drafted it; a founder sends it.
            o2 = db.execute("SELECT * FROM outreach WHERE id = ?", (lead_id,)).fetchone()
            body = request.form.get("followup_body", o2["followup_body"] or "").strip()
            if o2["status"] != "followup_drafted" or not body:
                flash("There is no follow-up waiting on this lead.", "error")
            elif mail.suppressed(o2["email"]):
                flash("This address asked not to be contacted. It stays on the do-not-contact list.", "error")
            elif mail.marketing_block():
                db.execute("UPDATE outreach SET followup_body=?, updated_at=? WHERE id=?", (body, now(), lead_id))
                flash("Not sent: %s. The draft is saved." % mail.marketing_block(), "error")
            else:
                mail.send(o2["email"], "Re: " + (o2["draft_subject"] or "Luminaz"), body, kind="marketing",
                          unsubscribe_url=url_for("support.unsubscribe", token=o2["unsub_token"], _external=True) if o2["unsub_token"] else None)
                db.execute("UPDATE outreach SET followup_body=?, status='followed_up', followup_sent_at=?, updated_at=? WHERE id=?",
                           (body, now(), now(), lead_id))
                audit("outreach_followup_sent", {"lead_id": lead_id, "email": o2["email"]}, user_id=g.user["id"])
                flash("Follow-up sent to %s." % o2["email"], "ok")
        elif action == "status":
            new = request.form.get("status")
            if new in OUTREACH_STATUSES:
                replied = now() if new in ("yes", "no", "later", "listed") else o["replied_at"]
                db.execute("UPDATE outreach SET status=?, replied_at=?, updated_at=? WHERE id=?", (new, replied, now(), lead_id))
                audit("outreach_status", {"lead_id": lead_id, "status": new}, user_id=g.user["id"])
                flash("Marked %s." % new.replace("_", " "), "ok")
        db.commit()
        return redirect(url_for("admin.outreach_lead", lead_id=lead_id))
    return render_template("admin/outreach_lead.html", o=o, statuses=OUTREACH_STATUSES, held=mail.marketing_block())


@bp.route("/support")
@login_required("admin")
def support_tickets():
    db = get_db()
    if request.args.get("answered"):
        db.execute("UPDATE support_tickets SET kind = 'answered' WHERE id = ?", (int(request.args["answered"]),))
        db.commit()
        return redirect(url_for("admin.support_tickets"))
    rows = db.execute("SELECT * FROM support_tickets ORDER BY kind = 'escalated' DESC, id DESC LIMIT 300").fetchall()
    return render_template("admin/support.html", rows=rows)


@bp.route("/marketing", methods=("GET", "POST"))
@login_required("admin")
def marketing():
    """Posts by purpose: to accredited investors, to fund managers, about webinars. The agent drafts; a founder approves; the app sends (change 28)."""
    from . import marketing as mk
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "plan":
            n = mk.plan_posts()
            flash("%d new draft%s ready to review." % (n, "" if n == 1 else "s") if n else "This week and next are already drafted.", "ok")
        else:
            pid = int(request.form["post_id"])
            post = db.execute("SELECT * FROM posts WHERE id = ?", (pid,)).fetchone()
            if not post:
                abort(404)
            if action in ("save", "approve"):
                db.execute("UPDATE posts SET topic = ?, long_body = ?, short_body = ?, tags = ?, hook = ? WHERE id = ?",
                           (request.form.get("topic", post["topic"]).strip(), request.form.get("long_body", "").strip(),
                            request.form.get("short_body", "").strip(), request.form.get("tags", "").strip(),
                            request.form.get("hook", post["hook"] or "").strip(), pid))
            if action == "approve":
                db.execute("UPDATE posts SET status = 'approved', approved_at = ?, approved_by = ? WHERE id = ?", (now(), g.user["id"], pid))
                audit("post_approved", {"post_id": pid}, user_id=g.user["id"])
                flash("Approved. It goes out on %s%s." % (post["scheduled_for"], "" if setting("post_webhook_url") else " (emailed to you to paste, until a webhook is set)"), "ok")
            elif action == "save":
                flash("Saved (still a draft).", "ok")
            elif action == "skip":
                db.execute("UPDATE posts SET status = 'skipped' WHERE id = ?", (pid,))
                flash("Skipped.", "ok")
            elif action == "unapprove":
                db.execute("UPDATE posts SET status = 'draft', approved_at = NULL, approved_by = NULL WHERE id = ?", (pid,))
                flash("Back to draft.", "ok")
            elif action == "send_now":
                if post["status"] != "approved":
                    flash("Approve it first.", "error")
                else:
                    db.execute("UPDATE posts SET scheduled_for = ? WHERE id = ?", (now()[:10], pid))
                    db.commit()
                    mk.publish_posts()
                    flash("Sent.", "ok")
        db.commit()
        return redirect(url_for("admin.marketing"))
    rows = db.execute("SELECT * FROM posts WHERE scheduled_for >= date('now', '-21 days') ORDER BY scheduled_for, id").fetchall()
    rendered = {r["id"]: mk.render(r) for r in rows}
    flags = {r["id"]: screen_text(" ".join(((r["hook"] or ""), r["long_body"], r["short_body"])), extra=POST_FLAGS) for r in rows}   # change 29
    counts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) AS n FROM posts GROUP BY status")}
    schedule = [(purpose, mk.PURPOSE_LABEL[purpose], ", ".join(n for n, _ in mk.days_for(purpose)) or "no day set",
                 ", ".join(mk.PLATFORM_LABEL.get(x, x) for x in mk.platforms_for(purpose))) for purpose in mk.PURPOSES]
    return render_template("admin/marketing.html", rows=rows, rendered=rendered, counts=counts, today=now()[:10],
                           webhook=setting("post_webhook_url", ""), schedule=schedule, labels=mk.PURPOSE_LABEL, flags=flags,
                           attorney=setting("attorney_approved", "0") == "1")


@bp.route("/communications")
@login_required("admin")
def communications():
    """What every post, webinar, email series and outreach email brought (change 33)."""
    from . import metrics
    weeks = request.args.get("weeks", "8")
    weeks = int(weeks) if weeks.isdigit() and 0 < int(weeks) <= 52 else 8
    return render_template("admin/communications.html", c=metrics.communications(weeks=weeks), weeks=weeks)


@bp.route("/metrics", methods=("GET", "POST"))
@login_required("admin")
def metrics_page():
    from . import metrics
    if request.method == "POST" and request.form.get("action") == "delete_spend":
        get_db().execute("DELETE FROM marketing_spend WHERE id = ?", (request.form.get("id", "0"),))
        audit("marketing_spend_deleted", {"id": request.form.get("id")}, user_id=g.user["id"])
        get_db().commit()
        flash("Spend entry deleted.", "ok")
        return redirect(url_for("admin.metrics_page"))
    if request.method == "POST":
        # Marketing spend, typed in by a founder: month, source (the ?src= word), amount, note
        month = request.form.get("month", "").strip()[:7]
        source = request.form.get("source", "").strip().lower()[:40]
        try:
            amount = float(request.form.get("amount", "0").replace(",", "").replace("$", "") or 0)
        except ValueError:
            amount = 0.0
        if len(month) == 7 and source and amount > 0:
            get_db().execute("INSERT INTO marketing_spend(month, source, amount, note, created_at) VALUES (?, ?, ?, ?, ?)",
                             (month, source, amount, request.form.get("note", "").strip()[:200], now()))
            audit("marketing_spend_added", {"month": month, "source": source, "amount": amount}, user_id=g.user["id"])
            get_db().commit()
            flash("Spend recorded.", "ok")
        else:
            flash("A month (YYYY-MM), a source word and an amount are needed.", "error")
        return redirect(url_for("admin.metrics_page"))
    weeks = metrics.weekly(12)
    return render_template("admin/metrics.html", weeks=weeks, totals=metrics.totals(), sources=metrics.sources(),
                           top=metrics.top_funds(), last=weeks[-1], prev=weeks[-2], days=metrics.daily(14), roi=metrics.roi(),
                           this_month=now()[:7],
                           spend_rows=get_db().execute("SELECT * FROM marketing_spend ORDER BY month DESC, id DESC LIMIT 60").fetchall())


@bp.route("/daily", methods=("POST",))
@login_required("admin")
def daily():
    from . import jobs
    r = jobs.run_all(admin_id=g.user["id"])
    b = r["billing"]
    flash("Daily tasks done: %d invoices issued, %d funds paused, %d resumed; %d education emails; %d managers nudged; "
          "%d outreach follow-ups; %d posts drafted, %d posts sent; backup %s." % (b["issued"], b["paused"], b["resumed"], r["education"], r["nudges"],
                                                  r["outreach_followups"], r["posts_drafted"], r["posts_sent"], "saved" if r["backup"] else "skipped"), "ok")
    return redirect(url_for("admin.billing_page"))


@bp.route("/audit")
@login_required("admin")
def audit_log():
    rows = get_db().execute("SELECT a.*, u.email FROM audit a LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT 300").fetchall()
    return render_template("admin/audit.html", rows=rows)
