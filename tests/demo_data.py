"""Sample accounts and funds so the portals have something to show."""
import datetime as dt
from werkzeug.security import generate_password_hash
from luminaz.db import get_db, now
from luminaz import billing

PW = "luminaz-demo-2026"

def _user(db, email, role, name, basis=None):
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO users(email, password_hash, role, name, email_confirmed, accreditation_basis, accreditation_attested_at, created_at)"
                     " VALUES (?, ?, ?, ?, 1, ?, ?, ?)", (email, generate_password_hash(PW), role, name, basis, now() if basis else None, now()))
    return cur.lastrowid

def load():
    db = get_db()
    admin = _user(db, "admin@luminaz.test", "admin", "Diane")
    mgr = _user(db, "manager@luminaz.test", "manager", "Marcus Reyes")
    mgr2 = _user(db, "manager2@luminaz.test", "manager", "Priya Natarajan")
    inv = _user(db, "investor@luminaz.test", "investor", "Alex Investor", "net_worth")
    inv2 = _user(db, "investor2@luminaz.test", "investor", "Jordan Lee", "income")
    if db.execute("SELECT COUNT(*) FROM firms").fetchone()[0]:
        db.commit(); return
    f1 = db.execute("INSERT INTO firms(owner_user_id, name, website, phone, address, state, description, principals, status, created_at)"
                    " VALUES (?, 'Ridgeline Capital', 'https://ridgeline.example', '770-555-0101', '100 Peachtree St, Atlanta', 'GA',"
                    " 'Ridgeline acquires and operates lower-middle-market service businesses in the Southeast. Two prior funds, both fully returned.',"
                    " 'Marcus Reyes, Managing Member of the GP\nRidgeline Capital GP LLC, General Partner', 'approved', ?)", (mgr, now())).lastrowid
    f2 = db.execute("INSERT INTO firms(owner_user_id, name, phone, state, description, principals, status, created_at)"
                    " VALUES (?, 'Blue Heron Partners', '615-555-0104', 'TN', 'Workforce multifamily in Nashville and Chattanooga.',"
                    " 'Priya Natarajan, Manager\nTom Okafor, Manager', 'pending', ?)", (mgr2, now())).lastrowid
    fund1 = db.execute("INSERT INTO funds(firm_id, name, category, strategy, target_raise, min_investment, term_years, key_terms, status, submitted_at, created_at)"
                       " VALUES (?, 'Ridgeline Acquisition Fund I, LP', 'Business acquisition / private equity',"
                       " 'Acquire 6 to 8 founder-owned HVAC, plumbing, and electrical service companies in Georgia, Tennessee, and the Carolinas with $1M to $4M of EBITDA, professionalize operations, and exit to a strategic or sponsor buyer in years 5 to 7.',"
                       " 25000000, 100000, 7, '2% management fee on committed capital; 20% carried interest over an 8% preferred return; GP commitment 2%; quarterly reporting; annual audited financials.',"
                       " 'submitted', ?, ?)", (f1, now(), now())).lastrowid
    db.execute("INSERT INTO agreements(firm_id, fund_id, signer_user_id, signer_name, signer_title, signed_at, ip_address, agreement_version, agreement_sha256)"
               " VALUES (?, ?, ?, 'Marcus Reyes', 'Managing Member of the GP', ?, '203.0.113.7', 'Luminaz Listing Agreement v0.9 (DRAFT)', 'demo')", (f1, fund1, mgr, now()))
    db.commit()
    billing.assign_status_on_first_signature(f1)
    db.execute("INSERT INTO bad_actor_checks(fund_id, subjects, determination, reviewer_id, notes, created_at, decided_at)"
               " VALUES (?, 'Marcus Reyes\nRidgeline Capital GP LLC', 'Passed - no disqualifying events found', ?, 'BrokerCheck, IAPD, OFAC, SEC Action Lookup, GA SoS checked', ?, ?)", (fund1, admin, now(), now()))
    db.commit()
    billing.go_live(fund1, admin)
    # Backdate so that exactly one invoice is due: billing started on the first day of last month,
    # the fund was live all of it, and this month is not finished yet (billed in arrears).
    from luminaz.db import set_setting
    prev_first = (dt.date.today().replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    live = (prev_first - dt.timedelta(days=60)).isoformat()
    db.execute("UPDATE funds SET live_since = ?, free_until = ? WHERE id = ?", (live, live, fund1))
    set_setting("billing_starts_on", prev_first.isoformat())
    fund2 = db.execute("INSERT INTO funds(firm_id, name, category, strategy, target_raise, min_investment, term_years, key_terms, status, submitted_at, created_at)"
                       " VALUES (?, 'Blue Heron Multifamily Fund II', 'Real estate', 'Value-add workforce housing, 150 to 300 units per asset, Nashville MSA. Hold 5 years.',"
                       " 15000000, 50000, 5, '1.5% asset management fee; 70/30 split over 7% pref.', 'submitted', ?, ?)", (f2, now(), now())).lastrowid
    db.execute("INSERT INTO agreements(firm_id, fund_id, signer_user_id, signer_name, signer_title, signed_at, ip_address, agreement_version, agreement_sha256)"
               " VALUES (?, ?, ?, 'Priya Natarajan', 'Manager', ?, '203.0.113.9', 'Luminaz Listing Agreement v0.9 (DRAFT)', 'demo')", (f2, fund2, mgr2, now()))
    for i in (inv, inv2):
        db.execute("INSERT INTO fund_views(fund_id, investor_id, viewed_at) VALUES (?, ?, ?)", (fund1, i, now()))
    db.execute("INSERT INTO interest(investor_id, fund_id, kind, created_at) VALUES (?, ?, 'shortlist', ?)", (inv, fund1, now()))
    db.execute("INSERT INTO interest(investor_id, fund_id, kind, created_at) VALUES (?, ?, 'watch', ?)", (inv2, fund1, now()))
    db.execute("INSERT INTO requests(fund_id, investor_id, message, status, created_at) VALUES (?, ?, 'Interested in the HVAC roll-up thesis. Please send the PPM.', 'new', ?)", (fund1, inv, now()))
    for e, r in (("lead1@example.com", "accredited"), ("lead2@example.com", "not_accredited"), ("lead3@example.com", "accredited")):
        db.execute("INSERT INTO calculator_leads(email, result, basis, source, created_at) VALUES (?, ?, ?, 'demo', ?)", (e, r, "income" if r == "accredited" else None, now()))
    db.commit()
    billing.run_billing(admin_id=admin)
