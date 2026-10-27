"""Pricing and invoicing.

Rules, decided by Diane on 14 October 2026 (they replace the invoice-in-advance rules):
  - One price for every fund: founding_rate / standard_rate in Settings ($850 a month as the
    starting value since 17 October 2026; $750 before). Founding Manager: the first N firms
    (founding_manager_cap) to sign a listing agreement keep the rate they signed at, locked, on
    every fund they ever list.
  - Founding funds (Diane, 17 October 2026): the first founding_free_funds funds to go live, by
    fund number, list free "as we are starting up the business". founding_fund_free_months = 0
    means free for as long as the listing is live (free_until is 9999-12-31); a number means free
    for that many months after going live, then the firm's rate. funds.founding_fund marks them.
  - Free until the catalog opens. The catalog opens when investor_signup_threshold funds are live
    and the accredited list is investor_multiple times what the largest listed fund needs to sell
    out. The daily job records catalog_opened_on that day and billing_starts_on, the first day of
    the following month. Settings can set either date by hand, or force sign-up open or closed.
  - Per-firm free months (founding_free_months / standard_free_months, first fund only) still
    exist and are 0 unless switched on.
  - Billed at the end of the month, in arrears. On every run, each finished month that has no
    invoice gets one for the days the listing was live that month, prorated by the day
    (rate x live days / days in the month). Issued the day the job runs, due net_days later.
  - Pause. A manager can pause a listing: it stays visible with a "paused" label, takes no
    requests for materials, and the paused days are not charged; one click resumes it. A fund with an invoice more than pause_after_days_past_due
    days late is paused for non-payment until it is paid. Both kinds are recorded in fund_pauses.
    A pause covers the day it starts; the day it is resumed counts as live again.
  - Close. The closing month is invoiced at once ('final') for the days through the closing day.
    Nothing is charged after that.
  - Optional (switched off by default): a one-time onboarding fee at signing, and a low
    "track record" rate for closed funds that stay visible.
  - Listing slots and the line (Diane, 17 October 2026): live_listing_slots listings can be live
    or paused at once (10; 0 = no limit). A manager who clicks Publish while every slot is taken
    joins the line (funds.queued_at); the line is in the order of those clicks and nobody can
    reorder it. When a listing closes or is removed, the first fund in line whose gates still pass
    goes live by itself, its manager is emailed, and billing for it starts that day (free if it is
    a founding fund). A manager can leave the line and rejoin later.
"""
import calendar
import datetime as dt

from .db import get_db, setting, set_setting, now, audit


def _f(key):
    return float(setting(key))


def _i(key):
    return int(setting(key))


def _date(text):
    return dt.date.fromisoformat(str(text)[:10])


def _month_after(d):
    return (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)


def founding_slots_left():
    used = get_db().execute("SELECT COUNT(*) FROM firms WHERE founding_manager = 1").fetchone()[0]
    return max(0, _i("founding_manager_cap") - used)


def founding_funds_left():
    """How many of the first founding_free_funds listings (the ones that list free) have not gone
    live yet. Counted by fund number, so a removed founding fund does not hand its place on."""
    db = get_db()
    cap = _int_setting("founding_free_funds", 0)
    used = db.execute("SELECT COUNT(*) FROM funds WHERE fund_number IS NOT NULL AND fund_number <= ?", (cap,)).fetchone()[0]
    return max(0, cap - used)


def founding_free_text():
    """Plain words for the manager pages: what the founding-fund offer is, or '' once it is used up."""
    left = founding_funds_left()
    if left <= 0:
        return ""
    cap = _int_setting("founding_free_funds", 0)
    months = _int_setting("founding_fund_free_months", 0)
    period = ("for their first %d months" % months) if months else "for as long as they are listed"
    return "The first %d funds to go live list free %s; %d of those places are left." % (cap, period, left)


def quoted_rate():
    """The monthly price to quote a firm that has not signed yet: the Founding rate while places
    remain, the standard rate after. Pages and emails read it from here instead of typing a price."""
    return _f("founding_rate") if founding_slots_left() > 0 else _f("standard_rate")


def assign_status_on_first_signature(firm_id):
    """Called when a firm signs its first listing agreement. Locks their rate."""
    db = get_db()
    firm = db.execute("SELECT * FROM firms WHERE id = ?", (firm_id,)).fetchone()
    if firm["locked_rate"] is not None:
        return firm
    if founding_slots_left() > 0:
        db.execute("UPDATE firms SET founding_manager = 1, locked_rate = ? WHERE id = ?", (_f("founding_rate"), firm_id))
        audit("founding_manager_granted", {"firm_id": firm_id})
    else:
        db.execute("UPDATE firms SET founding_manager = 0, locked_rate = ? WHERE id = ?", (_f("standard_rate"), firm_id))
    db.commit()
    return db.execute("SELECT * FROM firms WHERE id = ?", (firm_id,)).fetchone()


def rate_for_firm(firm):
    if firm["locked_rate"] is not None:
        return float(firm["locked_rate"])
    return _f("founding_rate") if founding_slots_left() > 0 else _f("standard_rate")


def free_months_for(firm):
    """Free period applies only to the firm's first fund."""
    db = get_db()
    prior = db.execute("SELECT COUNT(*) FROM funds WHERE firm_id = ? AND live_since IS NOT NULL", (firm["id"],)).fetchone()[0]
    if prior > 0:
        return 0
    return _i("founding_free_months") if firm["founding_manager"] else _i("standard_free_months")


def add_months(d, n):
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return dt.date(y, m, day)


# ---------------------------------------------------------------- free until the catalog opens

def investor_count():
    return get_db().execute("SELECT COUNT(*) FROM users WHERE role = 'investor' AND email_confirmed = 1").fetchone()[0]


def accredited_list_size():
    """People who took the calculator, appear accredited, and have not unsubscribed: the list a
    fund manager would be visible to once the catalog opens."""
    return get_db().execute("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE result = 'accredited' AND unsubscribed = 0"
                            " AND email NOT IN (SELECT email FROM suppressions)").fetchone()[0]


def _int_setting(key, default=0):
    try:
        return max(0, int(setting(key, str(default)) or default))
    except ValueError:
        return default


def readiness():
    """What it takes for the catalog to open, and where it stands. Diane's rule (14 October 2026):
    enough live funds, and an accredited list investor_multiple times what the largest listed
    fund needs to sell out (target raise / minimum investment)."""
    db = get_db()
    live = db.execute("SELECT COUNT(*) FROM funds WHERE status IN ('live','paused')").fetchone()[0]
    largest = db.execute("SELECT name, target_raise, min_investment FROM funds WHERE status IN ('live','paused')"
                         " AND target_raise > 0 AND min_investment > 0 ORDER BY target_raise / min_investment DESC LIMIT 1").fetchone()
    need = int(-(-float(largest["target_raise"]) // float(largest["min_investment"]))) if largest else 0   # ceiling
    multiple = _int_setting("investor_multiple", 5)
    # investor_list_cap: a manager can change a fund's minimum without review (a $1 minimum would ask
    # for millions of leads), so the list the gate demands never exceeds this number. Diane's number.
    cap = _int_setting("investor_list_cap", 5000)
    leads_needed = need * multiple
    if cap and leads_needed > cap:
        leads_needed = cap
    return {"live": live, "live_needed": _int_setting("investor_signup_threshold", 10),
            "leads": accredited_list_size(), "leads_needed": leads_needed, "multiple": multiple, "cap": cap,
            "largest_need": need, "largest_fund": largest["name"] if largest else None}


def catalog_ready():
    r = readiness()
    return r["live"] >= r["live_needed"] and (r["leads_needed"] == 0 or r["leads"] >= r["leads_needed"])


def catalog_opened(as_of=None, record=True):
    """The day the catalog opened, or None: the date in Settings (typed by hand or recorded by the
    daily job the first day the rule was met). The sign-up switch (investor_signup_open) does not
    come into it: "open" lets testers in without starting anyone's billing, and "closed" shuts
    sign-up without pretending the catalog never opened. See investor.signup_open."""
    as_of = as_of or dt.date.today()
    val = (setting("catalog_opened_on", "") or "").strip()
    if val:
        try:
            return _date(val)
        except ValueError:
            pass
    if catalog_ready():
        if record:
            set_setting("catalog_opened_on", as_of.isoformat())
            audit("catalog_opened", {"on": as_of.isoformat(), **readiness()})
        return as_of
    return None


def billing_start(as_of=None, record=True):
    """The first day any listing is billed: the first of the month after the catalog opened, or
    None while it is still closed. billing_starts_on in Settings overrides. Pages pass
    record=False and only read."""
    as_of = as_of or dt.date.today()
    val = (setting("billing_starts_on", "") or "").strip()
    if val:
        try:
            return _date(val)
        except ValueError:
            pass        # a mistyped date in Settings is ignored, not obeyed
    opened = catalog_opened(as_of, record=record)
    if opened is None:
        return None
    start = _month_after(opened)
    if record:
        set_setting("billing_starts_on", start.isoformat())
        audit("billing_starts", {"on": start.isoformat(), "catalog_opened_on": opened.isoformat()})
    return start


def billing_status(as_of=None):
    """Plain words for the founders' and managers' pages."""
    as_of = as_of or dt.date.today()
    start = billing_start(as_of, record=False)
    if start is None:
        r = readiness()
        # "self-reported": the list is people who took the calculator and appear accredited on what they
        # typed; nobody has verified anyone (rule 4.5).
        if r["largest_need"]:
            lst = "%s people on the list who appear accredited (self-reported; %d times what the largest listed fund needs%s; %s so far)" % (
                "{:,}".format(r["leads_needed"]), r["multiple"], ", capped" if r["leads_needed"] == r["cap"] else "", "{:,}".format(r["leads"]))
        else:
            lst = "a list of people who appear accredited (self-reported) %d times what the largest listed fund will need (%s so far)" % (
                r["multiple"], "{:,}".format(r["leads"]))
        return "Free for every fund until the catalog opens: %d live funds (%d so far) and %s." % (r["live_needed"], r["live"], lst)
    if start > as_of:
        opened = catalog_opened(as_of, record=False)
        return "The catalog opened on %s. Billing starts on %s." % (opened.isoformat() if opened else "a date set by hand", start.isoformat())
    return "Billing started on %s." % start.isoformat()


# ---------------------------------------------------------------- live days

def paused_days(fund_id, start, end):
    """The days in [start, end] the fund was paused, either reason. A pause covers the day it began
    through the day before it was resumed; a pause with no resume date runs to the end."""
    days = set()
    for r in get_db().execute("SELECT paused_at, resumed_at FROM fund_pauses WHERE fund_id = ?", (fund_id,)):
        p = _date(r["paused_at"])
        q = _date(r["resumed_at"]) if r["resumed_at"] else end + dt.timedelta(days=1)
        d = max(p, start)
        while d < q and d <= end:
            days.add(d)
            d += dt.timedelta(days=1)
    return days


def billable_days(fund, month_start, as_of=None, through=None):
    """(live days, days in the month) for one service month: days on or after the listing went
    live, after its own free period, and after billing started; up to the closing day (included),
    `through` (included, for the closing month) or the month's end; minus paused days."""
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    start_rule = billing_start(as_of, record=False)
    if start_rule is None or not fund["live_since"]:
        return 0, days_in_month
    month_end = month_start.replace(day=days_in_month)
    start = max(month_start, _date(fund["live_since"]), _date(fund["free_until"] or fund["live_since"]), start_rule)
    end = month_end
    if fund["closed_at"]:
        end = min(end, _date(fund["closed_at"]))
    if through:
        end = min(end, through)
    if start > end:
        return 0, days_in_month
    n = (end - start).days + 1 - len(paused_days(fund["id"], start, end))
    return max(0, n), days_in_month


# ---------------------------------------------------------------- status changes

def approve_fund(fund_id, admin_id):
    """Luminaz approval. The listing goes live only when the manager clicks Publish."""
    db = get_db()
    db.execute("UPDATE funds SET status = 'approved', approved_at = ? WHERE id = ?", (now(), fund_id))
    audit("fund_approved", {"fund_id": fund_id}, user_id=admin_id)
    db.commit()


def go_live(fund_id, admin_id):
    """Approve and publish in one step (used by tests and demo data)."""
    approve_fund(fund_id, admin_id)
    publish_fund(fund_id, admin_id)


def passed_506d(fund_id):
    """True when the newest Rule 506(d) determination on the fund starts with "Passed". A later
    "Failed" or "Referred to counsel" closes the gate again, approval or not (rule 4.6)."""
    row = get_db().execute("SELECT determination FROM bad_actor_checks WHERE fund_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                           (fund_id,)).fetchone()
    return bool(row and (row["determination"] or "").startswith("Passed"))


def publish_fund(fund_id, by_user_id):
    """The manager's final click after Luminaz approval. Sets the live date, the
    free period, the rate, and the fund number, and issues the onboarding fee if enabled.
    Refused unless the newest 506(d) determination is a pass (rule 4.6)."""
    db = get_db()
    fund = db.execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
    if fund["status"] != "approved" or not passed_506d(fund_id):
        return False
    if slots_open() == 0:
        # Every slot is taken: the click puts the fund in line (change 27). fill_slots() publishes it
        # when a slot opens, in the order of the clicks. A second click keeps the first place.
        if not fund["queued_at"]:
            # full precision, so two clicks in the same second still keep their order
            db.execute("UPDATE funds SET queued_at = ? WHERE id = ?", (dt.datetime.now(dt.timezone.utc).isoformat(), fund_id))
            audit("fund_joined_line", {"fund_id": fund_id, "position": len(the_line())}, user_id=by_user_id)
            db.commit()
        return "queued"
    firm = db.execute("SELECT * FROM firms WHERE id = ?", (fund["firm_id"],)).fetchone()
    if firm["locked_rate"] is None:
        firm = assign_status_on_first_signature(firm["id"])
    start = dt.date.today()
    months = free_months_for(firm)
    free_until = add_months(start, months) if months else start
    rate = rate_for_firm(firm)
    number = fund["fund_number"]
    if number is None:
        number = (db.execute("SELECT MAX(fund_number) FROM funds").fetchone()[0] or 0) + 1
        db.execute("UPDATE funds SET fund_number = ? WHERE id = ?", (number, fund_id))
    # Founding funds (Diane, 17 October 2026): the first founding_free_funds listings, by fund
    # number, list free: for as long as they are live, or for founding_fund_free_months months.
    founding_fund = 1 if number <= _int_setting("founding_free_funds", 0) else 0
    if founding_fund:
        ff_months = _int_setting("founding_fund_free_months", 0)
        free_until = max(free_until, add_months(start, ff_months) if ff_months else dt.date(9999, 12, 31))
    db.execute("UPDATE funds SET status = 'live', live_since = ?, free_until = ?, monthly_rate = ?, founding_fund = ?, queued_at = NULL WHERE id = ?",
               (start.isoformat(), free_until.isoformat(), rate, founding_fund, fund_id))
    if setting("onboarding_fee_enabled") == "1" and not firm["founding_manager"] and not founding_fund:
        _issue(firm["id"], fund_id, "onboarding", None, _f("onboarding_fee"))
    audit("fund_published", {"fund_id": fund_id, "fund_number": number, "rate": rate, "free_until": free_until.isoformat(),
                             "founding_fund": founding_fund}, user_id=by_user_id)
    db.commit()
    return True


def open_pause(fund_id):
    return get_db().execute("SELECT * FROM fund_pauses WHERE fund_id = ? AND resumed_at IS NULL ORDER BY id DESC LIMIT 1", (fund_id,)).fetchone()


PAUSE_AUDIT = {"manager": "fund_paused_by_manager", "nonpayment": "fund_paused_nonpayment", "admin": "fund_suspended_by_luminaz"}


def pause_fund(fund_id, by_user_id, as_of=None, reason="manager"):
    """Pause a live listing: still visible, no requests, paused days not charged. reason is
    'manager' (their own pause), 'nonpayment' (the billing job) or 'admin' (Luminaz suspends it
    under the listing agreement; only Luminaz can lift that one)."""
    db = get_db()
    as_of = as_of or dt.date.today()
    fund = db.execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
    if not fund or fund["status"] != "live":
        return False
    db.execute("UPDATE funds SET status = 'paused' WHERE id = ?", (fund_id,))
    db.execute("INSERT INTO fund_pauses(fund_id, reason, paused_at) VALUES (?, ?, ?)", (fund_id, reason, as_of.isoformat()))
    audit(PAUSE_AUDIT.get(reason, "fund_paused"), {"fund_id": fund_id, "on": as_of.isoformat()}, user_id=by_user_id)
    db.commit()
    return True


def resume_fund(fund_id, by_user_id, as_of=None, by_manager=True):
    """Take a listing off pause. A manager cannot resume a non-payment pause (that one ends by
    itself when the invoice is paid) or a Luminaz suspension."""
    db = get_db()
    as_of = as_of or dt.date.today()
    fund = db.execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
    if not fund or fund["status"] != "paused":
        return False
    pause = open_pause(fund_id)
    if by_manager and pause and pause["reason"] in ("nonpayment", "admin"):
        return False
    db.execute("UPDATE funds SET status = 'live' WHERE id = ?", (fund_id,))
    db.execute("UPDATE fund_pauses SET resumed_at = ? WHERE fund_id = ? AND resumed_at IS NULL", (as_of.isoformat(), fund_id))
    audit("fund_resumed", {"fund_id": fund_id, "on": as_of.isoformat()}, user_id=by_user_id)
    db.commit()
    return True


def close_fund(fund_id, by_user_id, as_of=None):
    """Close a listing (fully subscribed, or the manager stops). The closing month is invoiced at
    once for the days through today; nothing is charged after. Returns the final amount."""
    db = get_db()
    as_of = as_of or dt.date.today()
    db.execute("UPDATE funds SET status = 'closed', closed_at = ? WHERE id = ?", (as_of.isoformat(), fund_id))
    # A listing closed while paused stays paused through its closing day, so that day is not billed.
    db.execute("UPDATE fund_pauses SET resumed_at = ? WHERE fund_id = ? AND resumed_at IS NULL",
               ((as_of + dt.timedelta(days=1)).isoformat(), fund_id))
    fund = db.execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
    issued, final_amount = _issue_missing(fund, through=as_of, as_of=as_of, closing=True)
    audit("fund_closed", {"fund_id": fund_id, "closed_on": as_of.isoformat(), "final_invoice": final_amount}, user_id=by_user_id)
    db.commit()
    fill_slots()            # the slot this listing held goes to the first fund in line (change 27)
    return final_amount


# ---------------------------------------------------------------- listing slots and the line (change 27)

def slot_count():
    """live_listing_slots: how many listings may be live or paused at once. 0 = no limit."""
    return _int_setting("live_listing_slots", 0)


def slots_used():
    """A paused listing stays visible and keeps its slot (Diane's pause rule of 14 October 2026;
    whether a pause should free the slot instead is her open decision)."""
    return get_db().execute("SELECT COUNT(*) FROM funds WHERE status IN ('live','paused')").fetchone()[0]


def slots_open():
    """Open slots, or None when there is no limit."""
    cap = slot_count()
    return None if cap == 0 else max(0, cap - slots_used())


def the_line():
    """Approved funds whose manager clicked Publish while every slot was taken, first click first.
    This is the only order there is: no field, page or setting moves a fund up the line (rule 4.1)."""
    return get_db().execute("SELECT f.*, m.name AS firm_name FROM funds f JOIN firms m ON m.id = f.firm_id"
                            " WHERE f.status = 'approved' AND f.queued_at IS NOT NULL ORDER BY f.queued_at, f.id").fetchall()


def line_position(fund_id):
    """1-based place in the line, or None when the fund is not in it."""
    for i, f in enumerate(the_line()):
        if f["id"] == fund_id:
            return i + 1
    return None


def slot_summary():
    cap, used, line = slot_count(), slots_used(), len(the_line())
    return {"cap": cap, "used": used, "open": (max(0, cap - used) if cap else None), "line": line}


def leave_line(fund_id, by_user_id):
    """The manager takes the fund out of the line. It stays approved; another Publish click rejoins at the back."""
    db = get_db()
    fund = db.execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
    if not fund or fund["status"] != "approved" or not fund["queued_at"]:
        return False
    db.execute("UPDATE funds SET queued_at = NULL WHERE id = ?", (fund_id,))
    audit("fund_left_line", {"fund_id": fund_id}, user_id=by_user_id)
    db.commit()
    return True


def fill_slots():
    """Publish funds from the line into open slots, first click first, while their gates still pass
    (status approved, newest 506(d) a pass; approval and the manager's click were the other two).
    A fund whose gate closed since is skipped and keeps its place. The manager is emailed. Called
    when a listing closes or is removed, after a 506(d) determination, after Settings are saved,
    and by the daily job. Returns how many went live."""
    from . import mail
    db = get_db()
    went = 0
    for f in the_line():
        if slots_open() == 0:
            break
        if not passed_506d(f["id"]):
            continue
        if publish_fund(f["id"], None) is not True:
            continue
        went += 1
        owner = db.execute("SELECT u.email FROM users u JOIN firms m ON m.owner_user_id = u.id WHERE m.id = ?", (f["firm_id"],)).fetchone()
        f2 = db.execute("SELECT * FROM funds WHERE id = ?", (f["id"],)).fetchone()
        if owner:
            mail.send(owner["email"], "Your Luminaz listing is live: %s" % f2["name"],
                      "A listing slot opened and %s is now live as fund %s, in the order managers clicked Publish.\n\n"
                      "Investors can see it from today%s. Your promotion kit is on the fund page: %s\n\n%s"
                      % (f2["name"], f2["fund_number"],
                         " and it lists free as a founding fund" if f2["founding_fund"] else ", and live days count from today",
                         _fund_link(f2["id"]), setting("company_name")))
    return went


def _fund_link(fund_id):
    """The manager's fund page, with the host when a request is being served, a bare path otherwise
    (the daily job runs with a request context; tests may not)."""
    from flask import has_request_context, url_for
    if has_request_context():
        return url_for("manager.fund_detail", fund_id=fund_id, _external=True)
    return "/managers/funds/%d" % fund_id


# ---------------------------------------------------------------- invoices

def _next_number():
    db = get_db()
    n = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] + 1
    return "LMZ-%s-%04d" % (dt.date.today().strftime("%Y"), n)


def _issue(firm_id, fund_id, kind, service_month, amount, issued=None, live_days=None):
    db = get_db()
    issued = issued or dt.date.today()
    due = issued + dt.timedelta(days=_i("net_days"))
    db.execute("INSERT OR IGNORE INTO invoices(number, firm_id, fund_id, kind, service_month, amount, issued_at, due_at, live_days)"
               " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (_next_number(), firm_id, fund_id, kind, service_month, amount, issued.isoformat(), due.isoformat(), live_days))


def _issue_missing(fund, through, as_of, closing=False):
    """Issue an invoice for every month from the fund's first live month to the month of `through`
    that has none. The month of `through` is cut at that day and, when closing, marked 'final'.
    Returns (invoices issued, amount of the last one)."""
    db = get_db()
    if not fund["live_since"] or not fund["monthly_rate"]:
        return 0, 0.0
    issued = 0
    last_amount = 0.0
    m = _date(fund["live_since"]).replace(day=1)
    last_month = through.replace(day=1)
    while m <= last_month:
        key = m.strftime("%Y-%m")
        exists = db.execute("SELECT 1 FROM invoices WHERE fund_id = ? AND service_month = ? AND kind IN ('listing','final')", (fund["id"], key)).fetchone()
        if not exists:
            n, dim = billable_days(fund, m, as_of=as_of, through=through if m == last_month else None)
            if n > 0:
                amount = round(float(fund["monthly_rate"]) * n / dim, 2)
                kind = "final" if (closing and m == last_month) else "listing"
                _issue(fund["firm_id"], fund["id"], kind, key, amount, issued=as_of, live_days=n)
                issued += 1
                last_amount = amount
        m = _month_after(m)
    return issued, last_amount


def run_billing(as_of=None, admin_id=None):
    """
    Idempotent. Run daily (or whenever the admin clicks the button).
      1. Record the day billing starts, once the investor number is reached.
      2. For every listing, invoice each finished month that has none, for the days it was live.
      3. Pause any live fund with an invoice past due by more than the grace days.
      4. Resume funds paused for non-payment once their invoices are settled.
    Returns a summary dict. 'month' is the month just invoiced (the previous one).
    """
    db = get_db()
    as_of = as_of or dt.date.today()
    prev_month_end = as_of.replace(day=1) - dt.timedelta(days=1)
    month_key = prev_month_end.strftime("%Y-%m")
    issued = paused = resumed = 0

    start = billing_start(as_of)          # records billing_starts_on the first time the number is reached
    funds = db.execute("SELECT f.*, m.founding_manager FROM funds f JOIN firms m ON m.id = f.firm_id"
                       " WHERE f.status IN ('live','paused','closed') AND f.live_since IS NOT NULL").fetchall()
    if start is not None:
        for f in funds:
            n, _ = _issue_missing(f, through=prev_month_end, as_of=as_of)
            issued += n

    if setting("closed_tier_enabled") == "1":
        first_of_month = as_of.replace(day=1)
        this_key = as_of.strftime("%Y-%m")
        closed = db.execute("SELECT * FROM funds WHERE status = 'closed' AND closed_at IS NOT NULL AND closed_at < ?", (first_of_month.isoformat(),)).fetchall()
        for f in closed:
            exists = db.execute("SELECT 1 FROM invoices WHERE fund_id = ? AND service_month = ? AND kind = 'track_record'", (f["id"], this_key)).fetchone()
            if not exists:
                _issue(f["firm_id"], f["id"], "track_record", this_key, _f("closed_tier_rate"), issued=first_of_month)
                issued += 1

    grace = _i("pause_after_days_past_due")
    cutoff = (as_of - dt.timedelta(days=grace)).isoformat()
    late = db.execute("SELECT DISTINCT fund_id FROM invoices WHERE status = 'open' AND due_at < ? AND fund_id IS NOT NULL", (cutoff,)).fetchall()
    late_ids = {r["fund_id"] for r in late}
    for f in funds:
        if f["status"] == "live" and f["id"] in late_ids:
            if pause_fund(f["id"], admin_id, as_of=as_of, reason="nonpayment"):
                paused += 1
        elif f["status"] == "paused" and f["id"] not in late_ids:
            pause = open_pause(f["id"])
            if pause and pause["reason"] == "nonpayment":
                if resume_fund(f["id"], admin_id, as_of=as_of, by_manager=False):
                    resumed += 1
    db.commit()
    return {"issued": issued, "paused": paused, "resumed": resumed, "month": month_key}


def record_payment(invoice_id, method, admin_id):
    """Mark an invoice paid and email the manager a receipt."""
    from flask import url_for
    from . import mail
    db = get_db()
    db.execute("UPDATE invoices SET status = 'paid', paid_at = ?, paid_method = ? WHERE id = ?", (now(), method, invoice_id))
    audit("invoice_paid", {"invoice_id": invoice_id, "method": method}, user_id=admin_id)
    db.commit()
    inv = db.execute("SELECT i.*, m.name AS firm_name, u.email AS owner_email, f.name AS fund_name FROM invoices i"
                     " JOIN firms m ON m.id = i.firm_id JOIN users u ON u.id = m.owner_user_id LEFT JOIN funds f ON f.id = i.fund_id"
                     " WHERE i.id = ?", (invoice_id,)).fetchone()
    if inv and inv["owner_email"]:
        mail.send(inv["owner_email"], "Receipt: invoice %s paid" % inv["number"],
                  "Thank you. We received ${:,.2f} by {} for invoice {} ({}{}).\n\nThis is your receipt. The invoice itself is in your "
                  "dashboard under Invoices: {}\n\n{}".format(float(inv["amount"]), method, inv["number"], inv["fund_name"] or inv["kind"],
                                                             (", " + inv["service_month"]) if inv["service_month"] else "",
                                                             url_for("manager.invoice", invoice_id=invoice_id, _external=True), setting("company_name")))


def firm_invoices(firm_id):
    return get_db().execute("SELECT i.*, f.name AS fund_name, f.fund_number FROM invoices i LEFT JOIN funds f ON f.id = i.fund_id"
                            " WHERE i.firm_id = ? ORDER BY i.issued_at DESC, i.id DESC", (firm_id,)).fetchall()
