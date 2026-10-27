"""SQLite storage for Luminaz. One file, no server to run.

Tables mirror the business plan:
  users            investors, fund managers, admins
  firms            a fund manager's firm; Founding Manager status lives here
  funds            one row per listing, numbered fund 1, 2, 3 ...
  fund_mods        every change to a live listing, numbered mod 1, 2, 3 per fund
  agreements       signed listing agreements: who, when, from where, which text
  invoices         monthly listing invoices, net 30
  requests         an investor asking a manager for materials (the only moment
                   the investor's contact reaches the manager)
  interest         shortlist / watch marks, anonymous to managers
  fund_views       catalog views, for the manager's analytics
  calculator_leads accreditation calculator completions (result + email only)
  bad_actor_checks the 506(d) report and determination attached to a fund
  settings         pricing and thresholds, editable by admin
  audit            who did what, when
"""
import datetime as dt
import json
import os
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('investor','manager','admin')),
  name TEXT NOT NULL DEFAULT '',
  email_confirmed INTEGER NOT NULL DEFAULT 0,
  confirm_token TEXT,
  accreditation_basis TEXT,
  accreditation_attested_at TEXT,
  totp_secret TEXT,
  totp_enabled INTEGER NOT NULL DEFAULT 0,
  recovery_codes TEXT,
  created_at TEXT NOT NULL,
  last_login TEXT
);
CREATE TABLE IF NOT EXISTS firms (
  id INTEGER PRIMARY KEY,
  owner_user_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  website TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  address TEXT DEFAULT '',
  state TEXT DEFAULT '',
  description TEXT DEFAULT '',
  principals TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
  founding_manager INTEGER NOT NULL DEFAULT 0,
  locked_rate REAL,
  pending_changes TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS funds (
  id INTEGER PRIMARY KEY,
  fund_number INTEGER UNIQUE,
  firm_id INTEGER NOT NULL REFERENCES firms(id),
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  strategy TEXT NOT NULL DEFAULT '',
  target_raise REAL,
  min_investment REAL,
  term_years REAL,
  key_terms TEXT NOT NULL DEFAULT '',
  exemption TEXT NOT NULL DEFAULT 'Rule 506(c)',
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN ('draft','submitted','approved','rejected','live','paused','closed')),
  submitted_at TEXT,
  live_since TEXT,
  free_until TEXT,
  monthly_rate REAL,
  closed_at TEXT,
  rejection_note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fund_mods (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  mod_number INTEGER NOT NULL,
  changes TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','published','rejected','auto')),
  submitted_at TEXT NOT NULL,
  decided_at TEXT,
  decided_by INTEGER REFERENCES users(id),
  note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS agreements (
  id INTEGER PRIMARY KEY,
  firm_id INTEGER NOT NULL REFERENCES firms(id),
  fund_id INTEGER REFERENCES funds(id),
  signer_user_id INTEGER NOT NULL REFERENCES users(id),
  signer_name TEXT NOT NULL,
  signer_title TEXT NOT NULL,
  signed_at TEXT NOT NULL,
  ip_address TEXT NOT NULL,
  agreement_version TEXT NOT NULL,
  agreement_sha256 TEXT NOT NULL,
  luminaz_countersigned_at TEXT,
  luminaz_countersigner INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS invoices (
  id INTEGER PRIMARY KEY,
  number TEXT UNIQUE NOT NULL,
  firm_id INTEGER NOT NULL REFERENCES firms(id),
  fund_id INTEGER REFERENCES funds(id),
  kind TEXT NOT NULL DEFAULT 'listing' CHECK(kind IN ('listing','onboarding','credit','final','track_record')),
  service_month TEXT,
  amount REAL NOT NULL,
  issued_at TEXT NOT NULL,
  due_at TEXT NOT NULL,
  paid_at TEXT,
  paid_method TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','paid','void')),
  UNIQUE(fund_id, service_month, kind)
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  investor_id INTEGER NOT NULL REFERENCES users(id),
  message TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new'
    CHECK(status IN ('new','contacted','in_diligence','invested','passed')),
  created_at TEXT NOT NULL,
  updated_at TEXT,
  UNIQUE(fund_id, investor_id)
);
CREATE TABLE IF NOT EXISTS interest (
  investor_id INTEGER NOT NULL REFERENCES users(id),
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  kind TEXT NOT NULL CHECK(kind IN ('shortlist','watch')),
  created_at TEXT NOT NULL,
  PRIMARY KEY (investor_id, fund_id, kind)
);
CREATE TABLE IF NOT EXISTS investor_criteria (
  investor_id INTEGER PRIMARY KEY REFERENCES users(id),   -- what the investor said they are looking for (change 34): their own filters, never a ranking
  categories TEXT NOT NULL DEFAULT '',  -- category names separated by a vertical bar, blank = every category
  max_min REAL,                         -- the most they want to put into one fund, compared with the fund's minimum
  max_term REAL,                        -- the longest they will have money tied up, in years, compared with the fund's term
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fund_passes (
  investor_id INTEGER NOT NULL REFERENCES users(id),      -- the investor answered No: the fund is hidden from their catalog. Never shown to a manager.
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (investor_id, fund_id)
);
CREATE TABLE IF NOT EXISTS fund_views (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  investor_id INTEGER REFERENCES users(id),
  viewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS page_views (
  id INTEGER PRIMARY KEY,
  day TEXT NOT NULL,                    -- YYYY-MM-DD
  path TEXT NOT NULL,
  source TEXT DEFAULT '',               -- ?src= or referrer host
  visitor TEXT NOT NULL,                -- daily salted hash of IP + user agent: not reversible, resets every day
  signed_in INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS app_events (
  id INTEGER PRIMARY KEY,
  day TEXT NOT NULL,                    -- YYYY-MM-DD
  kind TEXT NOT NULL CHECK(kind IN ('installed','opened')),   -- added to a home screen / launched from it
  visitor TEXT NOT NULL,                -- the same daily salted hash as page_views, no cookie
  UNIQUE(day, kind, visitor)
);
CREATE TABLE IF NOT EXISTS calculator_leads (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('accredited','not_accredited')),
  basis TEXT,
  source TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  sequence_step INTEGER NOT NULL DEFAULT 0,
  last_sent_at TEXT,
  unsubscribed INTEGER NOT NULL DEFAULT 0,
  unsub_token TEXT
);
CREATE TABLE IF NOT EXISTS fund_documents (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  kind TEXT NOT NULL CHECK(kind IN ('ppm','operating_agreement','subscription_docs','other')),
  filename TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  uploaded_by INTEGER NOT NULL REFERENCES users(id),
  uploaded_at TEXT NOT NULL,
  reviewed_by INTEGER REFERENCES users(id),
  reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS outreach (
  id INTEGER PRIMARY KEY,
  contact_name TEXT NOT NULL DEFAULT '',
  firm_name TEXT NOT NULL DEFAULT '',
  fund_name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  phone TEXT DEFAULT '',
  category TEXT DEFAULT '',
  target_raise TEXT DEFAULT '',
  filed TEXT DEFAULT '',
  filing_url TEXT DEFAULT '',
  source TEXT DEFAULT 'form_d',
  status TEXT NOT NULL DEFAULT 'new'
    CHECK(status IN ('new','drafted','sent','followup_drafted','followed_up','yes','no','later','listed','do_not_contact')),
  draft_subject TEXT DEFAULT '',
  draft_body TEXT DEFAULT '',
  sent_at TEXT,
  followup_sent_at TEXT,
  replied_at TEXT,
  credit_offered INTEGER NOT NULL DEFAULT 0,
  notes TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY,
  scheduled_for TEXT NOT NULL,          -- date the post goes out
  slot TEXT NOT NULL,                   -- Monday / Wednesday / Friday
  bank_index INTEGER NOT NULL,
  topic TEXT NOT NULL,
  long_body TEXT NOT NULL,
  short_body TEXT NOT NULL,
  tags TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','published','skipped')),
  approved_at TEXT,
  approved_by INTEGER REFERENCES users(id),
  published_at TEXT,
  published_via TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(scheduled_for, slot)
);
CREATE TABLE IF NOT EXISTS suppressions (
  email TEXT PRIMARY KEY,               -- never send marketing or educational email here again
  reason TEXT DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resubscribes (
  token TEXT PRIMARY KEY,               -- one-click confirmation that lifts an unsubscribe: only the mailbox owner can click it
  email TEXT NOT NULL,
  created_at TEXT NOT NULL,
  used_at TEXT
);
CREATE TABLE IF NOT EXISTS support_tickets (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  email TEXT DEFAULT '',
  question TEXT NOT NULL,
  answer TEXT DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'auto' CHECK(kind IN ('auto','escalated','answered')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bad_actor_checks (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  report_path TEXT,
  subjects TEXT,
  determination TEXT,
  reviewer_id INTEGER REFERENCES users(id),
  notes TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  decided_at TEXT
);
CREATE TABLE IF NOT EXISTS fund_pauses (
  id INTEGER PRIMARY KEY,
  fund_id INTEGER NOT NULL REFERENCES funds(id),
  reason TEXT NOT NULL CHECK(reason IN ('manager','nonpayment','admin')),   -- admin = suspended by Luminaz (listing agreement 3.2)
  paused_at TEXT NOT NULL,              -- YYYY-MM-DD: the pause covers this day
  resumed_at TEXT                       -- YYYY-MM-DD: the resume day counts as live again. NULL = still paused
                                        -- (no semicolons in these comments: _rebuild_if_check_changed splits the schema on them)
);
CREATE TABLE IF NOT EXISTS webinars (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  audience TEXT NOT NULL DEFAULT 'investors' CHECK(audience IN ('investors','managers')),
  starts_at TEXT NOT NULL,              -- local date and time, YYYY-MM-DDTHH:MM
  zoom_url TEXT DEFAULT '',
  replay_url TEXT DEFAULT '',
  description TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','open','done')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webinar_registrations (
  id INTEGER PRIMARY KEY,
  webinar_id INTEGER NOT NULL REFERENCES webinars(id),
  name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL,
  source TEXT DEFAULT '',               -- the ?src= tag on the link they came from
  consent_at TEXT,
  consent_text TEXT,
  token TEXT UNIQUE NOT NULL,           -- personal join link, also the unsubscribe token
  joined_at TEXT,                       -- first click on the personal join link
  attended INTEGER NOT NULL DEFAULT 0,  -- ticked by a founder after the call
  reminded_at TEXT,
  replay_sent_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(webinar_id, email)
);
CREATE TABLE IF NOT EXISTS marketing_spend (
  id INTEGER PRIMARY KEY,
  month TEXT NOT NULL,                  -- YYYY-MM
  source TEXT NOT NULL,                 -- the same ?src= word used on the links: linkedin, facebook, newsletter, podcast, postcard ...
  amount REAL NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  user_id INTEGER,
  action TEXT NOT NULL,
  detail TEXT DEFAULT ''
);
"""

DEFAULT_SETTINGS = {
    # Pricing. Decided by Diane, 14 October 2026 and raised on 17 October 2026: $850 a month for
    # every fund, billed at the end of each month for the days the listing was live, pause or cancel
    # any time; and every listing is free until the investor catalog opens. The catalog opens when
    # investor_signup_threshold funds are live AND the accredited list is investor_multiple times
    # what the largest listed fund needs to sell out ("fund managers must always have a lot of
    # accredited investors to find"). Billing starts the month after it opens. The first 25 firms
    # (Founding Managers) keep the rate they signed at. Diane, 17 October 2026: the first
    # founding_free_funds funds to go live (by fund number) list free "as we are starting up the
    # business"; founding_fund_free_months = 0 means free for as long as the listing is live, a
    # number means free for that many months after going live, then the firm's rate (her decision
    # still open). Starting values for a new database; after that, the Settings page. No page or
    # email has a price typed into it. Per-firm free months still exist and are 0 unless switched on.
    "founding_manager_cap": "25",
    "founding_rate": "850",
    "founding_free_months": "0",
    "standard_rate": "850",
    "standard_free_months": "0",
    "founding_free_funds": "10",          # the first N funds to go live list free (Diane, 17 October 2026)
    "founding_fund_free_months": "0",     # 0 = free for as long as the listing is live; N = free for N months after going live, then the rate
    "live_listing_slots": "10",           # how many listings can be live (or paused) at once; the rest wait in line in Publish-click order; 0 = no limit (Diane, 17 October 2026)
    "investor_multiple": "5",             # the catalog opens when the accredited list is this many times what the largest listed fund needs (target raise / minimum); 0 = ignore
    "catalog_opened_on": "",              # YYYY-MM-DD; written by the daily job the day the catalog opens (live funds and the accredited list both large enough)
    "billing_starts_on": "",              # YYYY-MM-DD; the first of the month after the catalog opened, written by the daily job. Can be typed in to override.
    "onboarding_fee_enabled": "0",
    "onboarding_fee": "750",
    "closed_tier_enabled": "0",
    "closed_tier_rate": "60",
    "net_days": "30",
    "pause_after_days_past_due": "10",
    # Investor side
    "investor_signup_threshold": "10",     # live funds needed before sign-up opens
    "investor_signup_open": "auto",        # auto | open | closed. open/closed affect sign-up only; billing follows the dates below
    "investor_list_cap": "5000",           # the gate never asks for more than this many accredited leads, whatever a fund's figures say
    # Review rules: fields a manager may change on a live listing without review
    "auto_approve_fields": "min_investment,target_raise",
    # Company
    "company_name": "Luminaz Technology LLC",
    "payment_instructions": "Bank transfer or check. Details are set by the administrator.",
    "support_email": "support@luminaztechnology.com",
    "investor_host": "",          # e.g. luminaztechnology.com ; blank = single host
    "manager_host": "",           # e.g. luminazforfundmanagers.com
    "request_nudge_days": "3",
    "outreach_followup_days": "5",
    "founder_name": "Diane Barney",
    "founder_signature": "Former financial adviser · 18 years DoD contracts management",
    "booking_url": "",            # a Microsoft Bookings or Calendly page; when set, "Book a 15-minute call" appears on the manager landing page and in outreach
    "outreach_subject": "",       # blank = use luminaz/content/outreach.py
    "outreach_body": "",
    # Marketing posts: three a week, drafted by the agent, approved by a founder, sent automatically
    "post_webhook_url": "",       # Zapier / Make / Buffer webhook that posts to LinkedIn, Facebook, X. Blank = email the founder the ready text on the day
    "post_notify_email": "",
    # Posts by purpose (change 28). Weekday names, comma-separated; blank = none. Platforms: linkedin, facebook, x, threads, newsletter.
    "post_days_investors": "Monday,Wednesday,Friday",   # education for accredited investors (POSTS)
    "post_days_managers": "Tuesday",                    # to fund managers raising under 506(c) (MANAGER_POSTS)
    "post_days_webinars": "Thursday",                   # about an open webinar in the next post_webinar_lead_days; only once the attorney switch is 1
    "post_platforms_investors": "linkedin,facebook,x",
    "post_platforms_managers": "linkedin",
    "post_platforms_webinars": "linkedin,facebook",
    "post_webinar_lead_days": "14",
    "daily_summary": "1",         # 1 = email the day's numbers and what is waiting on the founders every evening (to post_notify_email, else support_email); 0 = off
    "attorney_approved": "0",     # 1 once the attorney has approved the terms and privacy policy: opens webinar sign-ups and their emails (AGENTS.md section 5)
    "reset_link_minutes": "60",   # a password-reset link stops working after this many minutes (finding 8)
    "require_admin_2fa": "1",     # 1 = an admin without two-step sign-in is sent to Security to set it up before any admin page opens (finding 12)
    "backup_copy_dir": "",        # a folder the nightly backup is also copied to (a OneDrive, Dropbox or mounted-drive folder); blank = none (finding 12)
    "daily_job_hour": "6",        # the hour, 0 to 23 on the server's clock, at or after which the app's own clock runs the daily job (change 30)
    "daily_summary_hour": "19",   # the hour, 0 to 23 on this computer's clock, at or after which that email goes out; 19 = 7 pm (asked for by Diane, 9 October 2026)
    "postal_address": "Luminaz Technology LLC, Acworth, Georgia, USA",   # printed in every marketing email (CAN-SPAM)      # where "posts waiting for approval" and "post this today" emails go; blank = support_email
}

# The first step for an investor is picking a kind of fund, so the list is the catalog's front door.
# Eight categories as of 14 October 2026 (Diane asked for energy; the rest were proposed with the
# landing pages). Hedge funds, REITs and Reg A offerings stay out. Changing this list changes the
# listing form, the catalog filter and the home page together.
CATEGORIES = [
    "Real estate",
    "Business acquisition / private equity",
    "Private debt",
    "Venture",
    "Energy",
    "Infrastructure",
    "Agriculture and timber",
    "Specialty",
]

CATEGORY_NOTES = {
    "Real estate": "Multifamily, commercial, land, short-term rental",
    "Business acquisition / private equity": "SBA-backed buyouts, search funds, lower middle market",
    "Private debt": "Lending, notes, bridge and asset-backed credit",
    "Venture": "Startups and growth companies",
    "Energy": "Oil and gas, renewables, minerals",
    "Infrastructure": "Utilities, storage, transport, data centers",
    "Agriculture and timber": "Farmland, orchards, forests",
    "Specialty": "Litigation finance, royalties, collectibles",
}


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def today():
    return dt.date.today().isoformat()


def day_bounds(day):
    """Start and end of one calendar day on this computer's clock, as UTC text in the format now()
    writes, so created_at columns can be compared directly. On a host, set TZ to the founders' time
    zone (DEPLOY.md section 5) so "yesterday" means their yesterday."""
    start = dt.datetime.combine(day, dt.time.min).astimezone(dt.timezone.utc)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min).astimezone(dt.timezone.utc)
    return start.replace(microsecond=0).isoformat(), end.replace(microsecond=0).isoformat()


def get_db():
    if "db" not in g:
        path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        g.db = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        # WAL lets readers and the daily job run at the same time; NORMAL sync is safe with WAL
        # and several times faster on writes. Both are one-line pragmas, no schema change.
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA synchronous = NORMAL")
        g.db.execute("PRAGMA temp_store = MEMORY")
        g.db.execute("PRAGMA cache_size = -16000")   # 16 MB page cache
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


MIGRATIONS = [
    ("funds", "approved_at", "TEXT"),
    ("users", "totp_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "recovery_codes", "TEXT"),
    ("calculator_leads", "sequence_step", "INTEGER NOT NULL DEFAULT 0"),
    ("calculator_leads", "last_sent_at", "TEXT"),
    ("calculator_leads", "unsubscribed", "INTEGER NOT NULL DEFAULT 0"),
    ("calculator_leads", "unsub_token", "TEXT"),
    ("calculator_leads", "consent_at", "TEXT"),
    ("calculator_leads", "consent_text", "TEXT"),
    ("users", "marketing_opt_in", "INTEGER NOT NULL DEFAULT 1"),
    ("users", "unsub_token", "TEXT"),
    ("users", "consent_at", "TEXT"),
    ("users", "consent_text", "TEXT"),
    ("outreach", "unsub_token", "TEXT"),
    ("invoices", "live_days", "INTEGER"),          # days of the service month the listing was live (billing in arrears, 14 Oct 2026)
    ("users", "paused_at", "TEXT"),                 # an investor who paused: no emails, shortlist hidden, until they resume
    ("users", "reset_token", "TEXT"),               # password reset link; separate from the email-confirmation token (finding 8)
    ("users", "reset_sent_at", "TEXT"),             # the link is good for reset_link_minutes, then refused
    ("outreach", "followup_body", "TEXT"),          # the follow-up the daily job drafts; a founder approves and sends it (rule 4.7)
    ("funds", "founder_invested_at", "TEXT"),       # the disclosure that a Luminaz founder invested: recorded by Luminaz, never by the manager
    ("calculator_leads", "catalog_notified_at", "TEXT"),   # the one "the catalog is open" email, sent once
    ("funds", "founding_fund", "INTEGER NOT NULL DEFAULT 0"),   # 1 = one of the first founding_free_funds listings to go live: lists free (change 26)
    ("funds", "queued_at", "TEXT"),                 # the manager clicked Publish while every slot was taken: in line from this moment (change 27)
    ("posts", "purpose", "TEXT NOT NULL DEFAULT 'investors'"),   # investors / managers / webinars: who the post is written for (change 28)
    ("posts", "hook", "TEXT DEFAULT ''"),            # the first line a reader sees; editable on the Posts page (change 28)
    ("posts", "webinar_id", "INTEGER"),               # set on webinar posts (change 28)
    ("page_views", "campaign", "TEXT DEFAULT ''"),          # the ?p=<post id> tag a visitor arrived with (change 33)
    ("calculator_leads", "campaign", "TEXT DEFAULT ''"),    # same tag, recorded on the lead (change 33)
    ("webinar_registrations", "campaign", "TEXT DEFAULT ''"),   # same tag, recorded on the registration (change 33)
]


def _rebuild_if_check_changed(db, table, marker):
    """SQLite can't alter a CHECK constraint, so a table whose allowed statuses
    grew is rebuilt from the current schema with its rows copied across."""
    row = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    if not row or marker in row["sql"]:
        return
    create = [stmt for stmt in SCHEMA.split(";") if ("CREATE TABLE IF NOT EXISTS %s " % table) in stmt][0]
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("ALTER TABLE %s RENAME TO %s__old" % (table, table))
    db.execute(create)
    old_cols = [r[1] for r in db.execute("PRAGMA table_info(%s__old)" % table)]
    new_cols = [r[1] for r in db.execute("PRAGMA table_info(%s)" % table)]
    cols = ", ".join(c for c in old_cols if c in new_cols)
    db.execute("INSERT INTO %s (%s) SELECT %s FROM %s__old" % (table, cols, cols, table))
    db.execute("DROP TABLE %s__old" % table)
    db.execute("PRAGMA foreign_keys = ON")


INDEXES = """
CREATE INDEX IF NOT EXISTS ix_users_role ON users(role, email_confirmed);
CREATE INDEX IF NOT EXISTS ix_firms_owner ON firms(owner_user_id);
CREATE INDEX IF NOT EXISTS ix_firms_status ON firms(status);
CREATE INDEX IF NOT EXISTS ix_funds_firm ON funds(firm_id);
CREATE INDEX IF NOT EXISTS ix_funds_status_order ON funds(status, live_since, fund_number);
CREATE INDEX IF NOT EXISTS ix_funds_status_cat ON funds(status, category);
CREATE INDEX IF NOT EXISTS ix_mods_fund_status ON fund_mods(fund_id, status);
CREATE INDEX IF NOT EXISTS ix_mods_status ON fund_mods(status);
CREATE INDEX IF NOT EXISTS ix_agreements_firm ON agreements(firm_id);
CREATE INDEX IF NOT EXISTS ix_invoices_firm_status ON invoices(firm_id, status);
CREATE INDEX IF NOT EXISTS ix_invoices_fund_month ON invoices(fund_id, service_month, kind);
CREATE INDEX IF NOT EXISTS ix_invoices_status_due ON invoices(status, due_at);
CREATE INDEX IF NOT EXISTS ix_requests_investor ON requests(investor_id);
CREATE INDEX IF NOT EXISTS ix_requests_fund_status ON requests(fund_id, status);
CREATE INDEX IF NOT EXISTS ix_requests_created ON requests(created_at);
CREATE INDEX IF NOT EXISTS ix_interest_investor ON interest(investor_id);
CREATE INDEX IF NOT EXISTS ix_interest_fund_kind ON interest(fund_id, kind);
CREATE INDEX IF NOT EXISTS ix_views_fund ON fund_views(fund_id);
CREATE INDEX IF NOT EXISTS ix_leads_email ON calculator_leads(email);
CREATE INDEX IF NOT EXISTS ix_page_views_day ON page_views(day, path);
CREATE INDEX IF NOT EXISTS ix_page_views_visitor ON page_views(day, visitor);
CREATE INDEX IF NOT EXISTS ix_users_created ON users(role, created_at);
CREATE INDEX IF NOT EXISTS ix_funds_live_since ON funds(live_since);
CREATE INDEX IF NOT EXISTS ix_leads_sequence ON calculator_leads(result, unsubscribed, sequence_step, last_sent_at);
CREATE INDEX IF NOT EXISTS ix_leads_created ON calculator_leads(created_at);
CREATE INDEX IF NOT EXISTS ix_bad_actor_fund ON bad_actor_checks(fund_id, created_at);
CREATE INDEX IF NOT EXISTS ix_docs_fund ON fund_documents(fund_id);
CREATE INDEX IF NOT EXISTS ix_outreach_status ON outreach(status, sent_at);
CREATE INDEX IF NOT EXISTS ix_outreach_fund ON outreach(fund_name);
CREATE INDEX IF NOT EXISTS ix_posts_sched ON posts(status, scheduled_for);
CREATE INDEX IF NOT EXISTS ix_tickets_kind ON support_tickets(kind, id);
CREATE INDEX IF NOT EXISTS ix_audit_id ON audit(id);
CREATE INDEX IF NOT EXISTS ix_pauses_fund ON fund_pauses(fund_id, resumed_at);
CREATE INDEX IF NOT EXISTS ix_webreg_webinar ON webinar_registrations(webinar_id, created_at);
"""


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    _rebuild_if_check_changed(db, "funds", "'approved'")
    _rebuild_if_check_changed(db, "fund_mods", "'published'")
    _rebuild_if_check_changed(db, "invoices", "'track_record'")
    _rebuild_if_check_changed(db, "outreach", "'followup_drafted'")
    _rebuild_if_check_changed(db, "fund_pauses", "'admin'")
    for table, col, decl in MIGRATIONS:
        cols = [r[1] for r in db.execute("PRAGMA table_info(%s)" % table)]
        if col not in cols:
            db.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, decl))
    db.executescript(INDEXES)      # after MIGRATIONS so indexed columns exist on old databases
    for k, v in DEFAULT_SETTINGS.items():
        db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    db.commit()
    db.execute("PRAGMA optimize")


def setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    get_db().execute("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    get_db().commit()


def audit(action, detail="", user_id=None):
    get_db().execute("INSERT INTO audit(at, user_id, action, detail) VALUES (?, ?, ?, ?)",
                     (now(), user_id, action, detail if isinstance(detail, str) else json.dumps(detail)))


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
