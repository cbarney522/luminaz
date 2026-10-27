"""python3 -m unittest discover tests"""
import datetime as dt, hashlib, os, tempfile, unittest, shutil
from luminaz import create_app
from luminaz.db import get_db, set_setting
from luminaz import billing
from tests import demo_data

def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"TESTING": True, "INSTANCE_PATH": self.tmp, "DATABASE": os.path.join(self.tmp, "t.sqlite"),
                               "MAIL_OUTBOX": os.path.join(self.tmp, "outbox"), "REPORTS_DIR": os.path.join(self.tmp, "reports"),
                               "SECRET_KEY": "test", "SERVER_NAME": "localhost"})
        self.c = self.app.test_client()
        with self.app.app_context():
            set_setting("require_admin_2fa", "0")       # on by default for real use; the dedicated test turns it on
            set_setting("attorney_approved", "1")       # 0 for real use until the attorney approves; the lock has its own tests
            set_setting("postal_address", "100 Test Street, Acworth, GA 30101")   # a street address, as CAN-SPAM needs
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
    def login(self, email):
        return self.c.post("/login", data={"email": email, "password": demo_data.PW}, follow_redirects=True)

class Flows(Base):
    def test_tests_never_write_into_the_real_instance_folder(self):
        # Uploads, backups and the secret key made during a test run must land in the temp folder,
        # never in app/instance where real investors' and managers' data will live.
        from luminaz import jobs
        real = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance")
        before = sorted(os.listdir(real)) if os.path.isdir(real) else None
        self.assertEqual(os.path.realpath(self.app.instance_path), os.path.realpath(self.tmp))
        with self.app.app_context():
            backup_file = jobs.backup()
        self.assertTrue(os.path.realpath(backup_file).startswith(os.path.realpath(self.tmp)))
        after = sorted(os.listdir(real)) if os.path.isdir(real) else None
        self.assertEqual(before, after)

    def test_daily_numbers_table_and_evening_report(self):
        from luminaz import metrics, jobs
        ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120"}
        self.c.get("/", headers=ua)
        self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                         "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "d1@x.com", "consent": "on"}, headers=ua)
        today = dt.date.today()
        at = lambda hour, minute=0, days=0: dt.datetime.combine(today + dt.timedelta(days=days), dt.time(hour, minute))
        with self.app.app_context():
            rows = metrics.daily(3)
            self.assertEqual([r["day"] for r in rows], [(today - dt.timedelta(days=k)).isoformat() for k in range(3)])   # newest first
            self.assertEqual((rows[0]["visitors"], rows[0]["leads"], rows[0]["accredited_leads"]), (1, 1, 1))
            self.assertEqual((rows[1]["visitors"], rows[1]["leads"]), (0, 0))                # nothing happened yesterday
            with self.app.test_request_context():
                outbox = self.app.config["MAIL_OUTBOX"]

                def reports():
                    found = []
                    for name in sorted(os.listdir(outbox)):
                        with open(os.path.join(outbox, name), encoding="utf-8") as fh:
                            text = fh.read()
                        if "Subject: Luminaz today:" in text:
                            found.append(text)
                    return found

                # Diane asked for the report at 7 pm, every day
                self.assertEqual(jobs.daily_summary(at=at(18, 59)), 0)                  # a minute early: nothing
                self.assertEqual(reports(), [])
                self.assertEqual(jobs.daily_summary(at=at(19, 0)), 1)                   # 7 pm: sent
                self.assertEqual(jobs.daily_summary(at=at(21, 30)), 0)                  # once per day
                self.assertEqual(jobs.daily_summary(at=at(21, 30), force=True), 0)      # ... also for "manage.py report now"
                self.assertEqual(len(reports()), 1)
                body = reports()[0]
                self.assertIn("as of 7:00 pm", body)
                self.assertIn("TODAY SO FAR", body)
                self.assertRegex(body, r"Email sign-ups \(calculator\)\s+1\s+\(yesterday, whole day: 0\)")
                self.assertRegex(body, r"of which appear accredited\s+1\s")
                self.assertIn("Nothing is waiting on you tonight.", body)
                # the daily job is the fallback: silent in the morning, sends when it runs in the evening
                self.assertEqual(jobs.run_all(at=at(6, 15, days=1))["daily_summary"], 0)
                self.assertEqual(len(reports()), 1)
                self.assertEqual(jobs.run_all(at=at(19, 5, days=1))["daily_summary"], 1)
                self.assertEqual(len(reports()), 2)
                self.assertRegex(reports()[1], r"\n  \d marketing posts to approve\n")   # the job drafted them a moment ago
                # "manage.py report now" does not wait for the hour
                self.assertEqual(jobs.daily_summary(at=at(9, 0, days=2), force=True), 1)
                # the hour is a setting; nonsense typed into it means 7 pm, never a crash
                set_setting("daily_summary_hour", "8")
                self.assertEqual(jobs.daily_summary(at=at(7, 59, days=3)), 0)
                self.assertEqual(jobs.daily_summary(at=at(8, 0, days=3)), 1)
                for nonsense in ("seven", "24", "-1", ""):
                    set_setting("daily_summary_hour", nonsense)
                    self.assertEqual(jobs.report_hour(), 19, nonsense)
                set_setting("daily_summary", "0")
                self.assertEqual(jobs.daily_summary(at=at(20, 0, days=4), force=True), 0)   # switched off in Settings
                self.assertEqual(len(reports()), 4)
            demo_data.load()
        self.login("admin@luminaz.test")
        self.assertIn(b"Day by day", self.c.get("/admin/metrics").data)
        page = self.c.get("/admin/settings").data
        self.assertIn(b'name="daily_summary"', page)
        self.assertIn(b'name="daily_summary_hour"', page)

    def test_home_screen_installs_and_opens_are_counted_without_cookies(self):
        import json
        from luminaz import metrics
        ua = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile"}
        r = self.c.post("/app-event", data={"kind": "installed"}, headers=ua)
        self.assertEqual(r.status_code, 204); self.assertNotIn("Set-Cookie", r.headers)
        self.c.post("/app-event", data={"kind": "installed"}, headers=ua)                                    # same person, same day: counted once
        self.c.post("/app-event", data={"kind": "opened"}, headers=ua)
        self.c.post("/app-event", data={"kind": "opened"}, headers={"User-Agent": "Mozilla/5.0 (iPhone) Safari/604"})   # a second person
        self.c.post("/app-event", data={"kind": "installed"}, headers={"User-Agent": "Googlebot/2.1"})          # bots are not counted
        self.assertEqual(self.c.post("/app-event", data={"kind": "bought"}, headers=ua).status_code, 400)
        with self.app.app_context():
            today = metrics.daily(1)[0]
            self.assertEqual((today["app_installs"], today["app_opens"]), (1, 2))
            self.assertFalse(get_db().execute("SELECT 1 FROM app_events WHERE visitor LIKE '%.%'").fetchone())   # no raw addresses stored
            set_setting("investor_host", "investors.test"); set_setting("manager_host", "managers.test")
        r = self.c.post("/app-event", data={"kind": "opened"}, headers=dict(ua, Host="managers.test"))
        self.assertEqual(r.status_code, 204)                                                                   # counted on either domain, never redirected
        # what a phone needs before it offers "Add to home screen"
        m = json.loads(self.c.get("/static/manifest.webmanifest").data)
        self.assertEqual(m["display"], "standalone")
        self.assertTrue({"192x192", "512x512"} <= {i["sizes"] for i in m["icons"]})
        for src in [i["src"] for i in m["icons"]] + ["/static/icon-180.png", "/static/app.js"]:
            r = self.c.get(src)
            self.assertEqual(r.status_code, 200, src)
            r.close()
        self.assertIn(b"/static/app.js", self.c.get("/login").data)

    def test_a_day_means_the_day_on_this_computers_clock(self):
        import time
        from luminaz.db import day_bounds
        if not hasattr(time, "tzset"):
            self.skipTest("the clock's time zone cannot be switched inside a test on Windows")
        old = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/New_York"; time.tzset()
            start, end = day_bounds(dt.date(2026, 10, 8))
            self.assertEqual((start, end), ("2026-10-08T04:00:00+00:00", "2026-10-09T04:00:00+00:00"))
            self.assertTrue(start <= "2026-10-09T02:30:00+00:00" < end)      # 10:30 pm Eastern on the 8th counts as the 8th
            self.assertEqual(day_bounds(dt.date(2026, 1, 15))[0], "2026-01-15T05:00:00+00:00")   # winter time
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()

    def test_manager_signup_creates_firm_and_sends_confirmation(self):
        r = self.c.post("/managers/signup", data={"name": "A", "firm_name": "Acme Capital", "email": "a@x.com", "password": "longpassword1", "state": "ga", "consent": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Check your email", r.data)
        with self.app.app_context():
            firm = get_db().execute("SELECT * FROM firms").fetchone()
            self.assertEqual(firm["state"], "GA")
            outbox = os.listdir(self.app.config["MAIL_OUTBOX"])
            self.assertEqual(len(outbox), 1)
            body = open(os.path.join(self.app.config["MAIL_OUTBOX"], outbox[0])).read()
            self.assertIn("/confirm/", body)

    def test_unconfirmed_cannot_login(self):
        self.c.post("/managers/signup", data={"name": "A", "firm_name": "Acme", "email": "a@x.com", "password": "longpassword1", "consent": "on"})
        r = self.c.post("/login", data={"email": "a@x.com", "password": "longpassword1"})
        self.assertIn(b"confirm your email", r.data)

    def test_investor_signup_gated_until_threshold(self):
        r = self.c.get("/signup")
        self.assertIn(b"Not open yet", r.data)
        with self.app.app_context():
            set_setting("investor_signup_open", "open")
        r = self.c.get("/signup")
        self.assertIn(b"Create your free account", r.data)

    def test_calculator_keeps_only_result_and_email(self):
        r = self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                             "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "lead@x.com", "consent": "on"})
        self.assertIn(b"appear to qualify", r.data)
        with self.app.app_context():
            lead = get_db().execute("SELECT * FROM calculator_leads").fetchone()
            self.assertEqual(lead["result"], "accredited"); self.assertEqual(lead["basis"], "income")
            self.assertFalse({"income", "assets", "net_worth", "figures"} & set(lead.keys()))  # no figure columns exist to store into

    def test_calculator_net_worth_excludes_home(self):
        r = self.c.post("/calculator", data={"joint": "no", "income_last": "0", "income_prior": "0", "income_expect": "no",
                                             "assets": "2000000", "home_value": "900000", "liabilities": "600000", "mortgage": "600000", "license": "no", "email": "l@x.com", "consent": "on"})
        self.assertIn(b"You appear to qualify", r.data)   # 2.0M - 0.9M home - (0.6M - 0.6M mortgage) = 1.1M
    def test_calculator_net_worth_fail(self):
        r = self.c.post("/calculator", data={"joint": "no", "income_last": "0", "income_prior": "0", "income_expect": "no",
                                             "assets": "1500000", "home_value": "900000", "liabilities": "100000", "mortgage": "0", "license": "no", "email": "l@x.com", "consent": "on"})
        self.assertIn(b"currently appear to meet", r.data)   # 1.5M - 0.9M - 0.1M = 500k

class DemoFlows(Base):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def test_admin_queue_and_approve_requires_agreement_and_506d(self):
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/")
        self.assertIn(b"Blue Heron Multifamily Fund II", r.data)
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Blue Heron%'").fetchone()["id"]
        r = self.c.post("/admin/funds/%d" % fid, data={"action": "approve"}, follow_redirects=True)
        self.assertIn(b"Record a passing 506(d) determination", r.data)
        self.c.post("/admin/funds/%d" % fid, data={"action": "determination", "determination": "Passed - no disqualifying events found", "notes": "ok", "subjects": "Priya"})
        r = self.c.post("/admin/funds/%d" % fid, data={"action": "approve"}, follow_redirects=True)
        self.assertIn(b"Approve the firm profile first", r.data)          # Blue Heron's profile is still pending
        with self.app.app_context():
            firm_id = get_db().execute("SELECT firm_id FROM funds WHERE id = ?", (fid,)).fetchone()["firm_id"]
        self.c.post("/admin/firms/%d" % firm_id, data={"action": "approve"})
        r = self.c.post("/admin/funds/%d" % fid, data={"action": "approve"}, follow_redirects=True)
        self.assertIn(b"emailed to publish", r.data)
        with self.app.app_context():
            f = get_db().execute("SELECT * FROM funds WHERE id = ?", (fid,)).fetchone()
            self.assertEqual(f["status"], "approved")           # not live until the manager clicks Publish
            self.assertIsNone(f["fund_number"])
        # Manager's final click
        self.c.get("/logout"); self.login("manager2@luminaz.test")
        r = self.c.get("/managers/funds/%d" % fid)
        self.assertIn(b"Publish", r.data)
        r = self.c.post("/managers/funds/%d/publish" % fid, follow_redirects=True)
        self.assertIn(b"is live as fund", r.data)
        with self.app.app_context():
            f = get_db().execute("SELECT * FROM funds WHERE id = ?", (fid,)).fetchone()
            self.assertEqual(f["status"], "live"); self.assertEqual(f["fund_number"], 2)
            self.assertEqual(f["monthly_rate"], 850.0)          # founding slots still open; $850 since 17 October 2026 ($750 from 14 October)
            firm = get_db().execute("SELECT * FROM firms WHERE id = ?", (f["firm_id"],)).fetchone()
            self.assertEqual(firm["founding_manager"], 1)

    def test_price_is_850_a_month_billed_at_month_end_and_free_until_enough_investors(self):
        # Decided by Diane, 14 October 2026 ($750) and raised to $850 on 17 October 2026. Replaces the $350 / three-free-months test of 9 October.
        from luminaz import support
        from luminaz.db import DEFAULT_SETTINGS
        self.assertEqual((DEFAULT_SETTINGS["founding_rate"], DEFAULT_SETTINGS["standard_rate"]), ("850", "850"))
        self.assertEqual((DEFAULT_SETTINGS["founding_manager_cap"], DEFAULT_SETTINGS["founding_free_months"], DEFAULT_SETTINGS["standard_free_months"]), ("25", "0", "0"))
        self.assertEqual((DEFAULT_SETTINGS["investor_multiple"], DEFAULT_SETTINGS["investor_signup_threshold"]), ("5", "10"))
        page = self.c.get("/managers/").data
        self.assertIn(b"$850", page)
        self.assertNotIn(b"$350", page); self.assertNotIn(b"$400", page); self.assertNotIn(b"$750", page)
        with self.app.app_context():
            a, kind = support.answer("How much does a listing cost?")
            self.assertIn("$850", a); self.assertIn("end of each month", a); self.assertIn("free until the investor catalog opens", a)
            set_setting("founding_rate", "775")                                           # prices are read from Settings, never typed in
            self.assertIn("$775", support.answer("What is the fee?")[0])
            set_setting("founding_rate", "850")
            self.assertIn("paused days aren't charged", support.answer("Can I pause my listing?")[0])
        self.login("admin@luminaz.test")
        self.c.post("/admin/outreach", data={"action": "add", "contact_name": "Pat Lee", "email": "pat@fund.test", "fund_name": "Lee Fund I"})
        with self.app.app_context():
            lead = get_db().execute("SELECT id FROM outreach WHERE fund_name = 'Lee Fund I'").fetchone()["id"]
        r = self.c.post("/admin/outreach/%d" % lead, data={"action": "draft"}, follow_redirects=True)
        self.assertIn(b"flat $850 a month", r.data); self.assertIn(b"end of each month", r.data); self.assertIn(b"free until the catalog has enough", r.data)
        self.assertNotIn(b"$400", r.data); self.assertNotIn(b"months free", r.data)

    def test_evening_report_lists_what_is_waiting_on_the_founders(self):
        from luminaz import metrics, marketing
        with self.app.app_context(), self.app.test_request_context():
            db = get_db()
            self.assertEqual(metrics.waiting(), [(1, "fund to review"), (1, "firm profile to review")])   # the sample data's review queue
            monday = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
            self.assertEqual(marketing.plan_posts(today=monday), 8)                     # three investor drafts a week plus a manager Tuesday, two weeks (change 28)
            db.execute("INSERT INTO support_tickets(email, question, kind, created_at) VALUES ('a@x.com', 'Please call me.', 'escalated', '2026-10-09T12:00:00+00:00')")
            db.commit()
            self.assertEqual(metrics.waiting(today=monday), [(1, "fund to review"), (1, "firm profile to review"),
                                                             (8, "marketing posts to approve"), (1, "support question that needs a person")])
            due = dt.date.fromisoformat(db.execute("SELECT due_at FROM invoices WHERE status = 'open'").fetchone()[0][:10])
            self.assertNotIn((1, "invoice past due"), metrics.waiting(today=due))       # the due day itself is not late
            self.assertIn((1, "invoice past due"), metrics.waiting(today=due + dt.timedelta(days=1)))
            subject, body = metrics.daily_text(at=dt.datetime.combine(monday, dt.time(19, 0)))
            self.assertTrue(subject.endswith("; 11 waiting on you"), subject)
            for line in ("WAITING ON YOU", "  1 fund to review", "  1 firm profile to review", "  8 marketing posts to approve",
                         "  1 support question that needs a person"):
                self.assertIn(line + "\n", body)
            self.assertNotIn("Nothing is waiting on you", body)
            self.assertLess(max(len(line) for line in body.splitlines()), 76)           # stays plain text in instance/outbox

    def test_billing_issues_and_pauses(self):
        import calendar
        with self.app.app_context():
            db = get_db()
            inv = db.execute("SELECT * FROM invoices WHERE kind = 'listing'").fetchall()
            self.assertEqual(len(inv), 1)                          # demo run issued last month's invoice, in arrears
            prev = (dt.date.today().replace(day=1) - dt.timedelta(days=1))
            self.assertEqual(inv[0]["service_month"], prev.strftime("%Y-%m"))
            self.assertEqual(inv[0]["live_days"], calendar.monthrange(prev.year, prev.month)[1])   # live all month
            self.assertEqual(inv[0]["amount"], 850.0)
            self.assertEqual(inv[0]["issued_at"], dt.date.today().isoformat())                     # issued the day the job ran
            # Make it 11 days late and run again
            late_due = (dt.date.today() - dt.timedelta(days=11)).isoformat()
            db.execute("UPDATE invoices SET due_at = ? WHERE id = ?", (late_due, inv[0]["id"])); db.commit()
            r = billing.run_billing()
            self.assertEqual(r["paused"], 1)
            self.assertEqual(db.execute("SELECT status FROM funds WHERE id = ?", (inv[0]["fund_id"],)).fetchone()["status"], "paused")
            billing.record_payment(inv[0]["id"], "bank transfer", 1)
            r = billing.run_billing()
            self.assertEqual(r["resumed"], 1)
            self.assertEqual(r["issued"], 0)                       # idempotent

    def test_manager_live_edit_auto_vs_reviewed(self):
        self.login("manager@luminaz.test")
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Ridgeline%'").fetchone()["id"]
        base = {"name": "Ridgeline Acquisition Fund I, LP", "category": "Business acquisition / private equity",
                "strategy": "Acquire 6 to 8 founder-owned HVAC, plumbing, and electrical service companies in Georgia, Tennessee, and the Carolinas with $1M to $4M of EBITDA, professionalize operations, and exit to a strategic or sponsor buyer in years 5 to 7.",
                "target_raise": "25000000", "min_investment": "150000", "term_years": "7",
                "key_terms": "2% management fee on committed capital; 20% carried interest over an 8% preferred return; GP commitment 2%; quarterly reporting; annual audited financials.",
                "confirm_506c": "on", "confirm_closed_end": "on"}
        r = self.c.post("/managers/funds/%d/edit" % fid, data=base, follow_redirects=True)
        self.assertIn(b"mod 1 applied", r.data)
        base["strategy"] = "New strategy text"
        r = self.c.post("/managers/funds/%d/edit" % fid, data=base, follow_redirects=True)
        self.assertIn(b"mod 2 sent to Luminaz for review", r.data)
        with self.app.app_context():
            f = get_db().execute("SELECT * FROM funds WHERE id = ?", (fid,)).fetchone()
            self.assertEqual(f["min_investment"], 150000.0)
            self.assertNotEqual(f["strategy"], "New strategy text")

    def test_investor_catalog_and_request(self):
        self.login("investor2@luminaz.test")
        r = self.c.get("/funds")
        self.assertIn(b"Ridgeline Acquisition Fund I", r.data)
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Ridgeline%'").fetchone()["id"]
        r = self.c.post("/funds/%d/request" % fid, data={"message": "Send PPM"}, follow_redirects=True)
        self.assertIn(b"The manager will contact you directly", r.data)
        # Manager sees the investor now
        self.c.get("/logout"); self.login("manager@luminaz.test")
        r = self.c.get("/managers/funds/%d" % fid)
        self.assertIn(b"investor2@luminaz.test", r.data)

    def test_role_guard(self):
        self.login("investor@luminaz.test")
        self.assertEqual(self.c.get("/admin/").status_code, 403)
        self.assertEqual(self.c.get("/managers/dashboard").status_code, 403)

    def test_pages_render(self):
        for path in ("/", "/calculator", "/managers/", "/login", "/legal/terms", "/legal/privacy", "/legal/listing-agreement"):
            self.assertEqual(self.c.get(path).status_code, 200, path)
        self.login("admin@luminaz.test")
        for path in ("/admin/", "/admin/billing", "/admin/investors", "/admin/settings", "/admin/audit"):
            self.assertEqual(self.c.get(path).status_code, 200, path)
        self.c.get("/logout"); self.login("manager@luminaz.test")
        for path in ("/managers/dashboard", "/managers/firm", "/managers/funds/new", "/managers/invoices"):
            self.assertEqual(self.c.get(path).status_code, 200, path)


class LaunchFeatures(Base):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def test_close_issues_a_final_invoice_for_the_days_through_the_closing_day(self):
        # Billing in arrears (14 October 2026): closing invoices the current month at once, for the
        # days the listing was live, and nothing is charged after the closing day.
        import calendar
        with self.app.app_context():
            db = get_db()
            inv = db.execute("SELECT * FROM invoices WHERE kind = 'listing'").fetchone()
            fid = inv["fund_id"]
            day10 = dt.date.today().replace(day=10)
            final = billing.close_fund(fid, 1, as_of=day10)
            dim = calendar.monthrange(day10.year, day10.month)[1]
            self.assertEqual(final, round(850.0 * 10 / dim, 2))
            f = db.execute("SELECT * FROM invoices WHERE fund_id = ? AND kind = 'final'", (fid,)).fetchone()
            self.assertEqual((f["live_days"], f["amount"], f["service_month"]), (10, final, day10.strftime("%Y-%m")))
            self.assertEqual(db.execute("SELECT status FROM funds WHERE id = ?", (fid,)).fetchone()["status"], "closed")
            # Running billing later changes nothing: the month is settled and later months have no live days.
            later = (day10.replace(day=1) + dt.timedelta(days=64)).replace(day=1)
            self.assertEqual(billing.run_billing(as_of=later)["issued"], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM invoices WHERE fund_id = ?", (fid,)).fetchone()[0], 2)

    def test_manager_pause_stops_billing_for_paused_days(self):
        import calendar
        with self.app.app_context():
            db = get_db()
            fid = db.execute("SELECT fund_id FROM invoices WHERE kind = 'listing'").fetchone()["fund_id"]
            month = dt.date.today().replace(day=1)
            self.assertTrue(billing.pause_fund(fid, 1, as_of=month.replace(day=5)))
            self.assertEqual(db.execute("SELECT status FROM funds WHERE id = ?", (fid,)).fetchone()["status"], "paused")
            self.assertFalse(billing.pause_fund(fid, 1))                                   # already paused
            self.assertTrue(billing.resume_fund(fid, 1, as_of=month.replace(day=8)))     # paused the 5th, 6th, 7th
            final = billing.close_fund(fid, 1, as_of=month.replace(day=10))
            dim = calendar.monthrange(month.year, month.month)[1]
            self.assertEqual(final, round(850.0 * 7 / dim, 2))                            # 10 days minus 3 paused
            self.assertEqual(db.execute("SELECT live_days FROM invoices WHERE fund_id = ? AND kind = 'final'", (fid,)).fetchone()[0], 7)
        # The buttons: a manager pauses from the fund page, investors stop seeing it, and resumes.
        self.login("manager@luminaz.test")
        r = self.c.get("/managers/dashboard")
        self.assertIn(b"billed at the end of each month", r.data)
        with self.app.app_context():
            fid2 = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Ridgeline%'").fetchone()["id"]
            get_db().execute("UPDATE funds SET status = 'live', closed_at = NULL WHERE id = ?", (fid2,)); get_db().commit()
        r = self.c.post("/managers/funds/%d/pause" % fid2, follow_redirects=True)
        self.assertIn(b"Paused. Your listing stays visible", r.data); self.assertIn(b"Resume listing", r.data)
        # Diane, 14 October: a paused fund stays visible, just stops taking requests
        self.c.get("/logout"); self.login("investor2@luminaz.test")
        cat = self.c.get("/funds").data
        self.assertIn(b"Ridgeline Acquisition Fund I", cat); self.assertIn(b"Paused, not taking requests", cat)
        page = self.c.get("/funds/%d" % fid2).data
        self.assertIn(b"not taking requests for materials right now", page); self.assertNotIn(b"Send my request", page)
        self.assertEqual(self.c.post("/funds/%d/request" % fid2, data={"message": "x"}).status_code, 404)
        self.c.post("/funds/%d/mark/shortlist" % fid2)                                   # shortlist and watch still work
        self.assertIn(b'<span class="tag live">Yes</span>', self.c.get("/funds").data)   # "Shortlisted" reads "Yes" since change 34
        self.c.get("/logout"); self.login("manager@luminaz.test")
        r = self.c.post("/managers/funds/%d/resume" % fid2, follow_redirects=True)
        self.assertIn(b"Resumed.", r.data)
        self.c.get("/logout"); self.login("investor2@luminaz.test")
        page = self.c.get("/funds/%d" % fid2).data
        self.assertIn(b"Send my request", page); self.assertNotIn(b"Paused, not taking requests", self.c.get("/funds").data)

    def test_a_nonpayment_pause_cannot_be_resumed_by_the_manager(self):
        with self.app.app_context():
            db = get_db()
            inv = db.execute("SELECT * FROM invoices WHERE kind = 'listing'").fetchone()
            db.execute("UPDATE invoices SET due_at = ? WHERE id = ?", ((dt.date.today() - dt.timedelta(days=11)).isoformat(), inv["id"])); db.commit()
            self.assertEqual(billing.run_billing()["paused"], 1)
            self.assertFalse(billing.resume_fund(inv["fund_id"], 2))                     # the manager's click does nothing
            self.assertEqual(db.execute("SELECT status FROM funds WHERE id = ?", (inv["fund_id"],)).fetchone()["status"], "paused")
            billing.record_payment(inv["id"], "ACH", 1)
            self.assertEqual(billing.run_billing()["resumed"], 1)                        # paying ends it

    def test_catalog_opens_on_live_funds_and_a_5x_accredited_list_then_billing_starts_the_month_after(self):
        # Diane, 14 October 2026: fund managers must always have a lot of accredited investors to find.
        # The catalog opens when enough funds are live AND the accredited list is investor_multiple
        # times what the largest listed fund needs to sell out; billing starts the month after.
        import calendar
        with self.app.app_context(), self.app.test_request_context():
            from luminaz.db import setting
            db = get_db()
            db.execute("DELETE FROM invoices"); db.commit()
            set_setting("billing_starts_on", ""); set_setting("catalog_opened_on", ""); set_setting("investor_signup_threshold", "1")
            r = billing.readiness()
            # The sample fund: $25M target at $100,000 minimum = 250 investors to sell out; 5x = 1,250
            self.assertEqual((r["live"], r["live_needed"], r["largest_need"], r["leads_needed"], r["leads"]), (1, 1, 250, 1250, 2))
            self.assertFalse(billing.catalog_ready())
            self.assertEqual(billing.run_billing()["issued"], 0)
            self.assertEqual((setting("catalog_opened_on"), setting("billing_starts_on")), ("", ""))
            self.assertIn("1 live funds (1 so far) and 1,250 people on the list who appear accredited (self-reported; 5 times what the largest listed fund needs; 2 so far)", billing.billing_status())
            self.assertIn(b"Not open yet", self.c.get("/signup").data)
            # 1,248 more accredited leads arrive (an unsubscribed one and a not-accredited one don't count)
            for i in range(1248):
                db.execute("INSERT INTO calculator_leads(email, result, basis, source, created_at) VALUES (?, 'accredited', 'income', 'webinar', ?)", ("lead%d@x.com" % i, "2026-10-01T00:00:00+00:00"))
            db.execute("INSERT INTO calculator_leads(email, result, basis, source, created_at, unsubscribed) VALUES ('gone@x.com', 'accredited', 'income', '', '2026-10-01T00:00:00+00:00', 1)")
            db.execute("INSERT INTO calculator_leads(email, result, source, created_at) VALUES ('no@x.com', 'not_accredited', '', '2026-10-01T00:00:00+00:00')")
            db.commit()
            self.assertEqual(billing.readiness()["leads"], 1250)
            self.assertTrue(billing.catalog_ready())
            today = dt.date.today()
            self.assertEqual(billing.run_billing(as_of=today)["issued"], 0)              # opened today: recorded, nothing billed yet
            start = (today.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
            self.assertEqual((setting("catalog_opened_on"), setting("billing_starts_on")), (today.isoformat(), start.isoformat()))
            self.assertIn("The catalog opened on %s. Billing starts on %s." % (today.isoformat(), start.isoformat()), billing.billing_status())
            self.assertIn(b"Create your free account", self.c.get("/signup").data)       # sign-up opened with the catalog
            after = (start + dt.timedelta(days=32)).replace(day=1)
            r = billing.run_billing(as_of=after)                                         # first run of the month after billing began
            self.assertEqual((r["issued"], r["month"]), (1, start.strftime("%Y-%m")))
            inv = db.execute("SELECT * FROM invoices").fetchone()
            self.assertEqual((inv["amount"], inv["live_days"]), (850.0, calendar.monthrange(start.year, start.month)[1]))
            # The sign-up switch is for sign-up only (review finding 8, 16 October): "open" lets testers
            # in without opening the catalog or starting anyone's billing; "closed" shuts sign-up even
            # after the catalog opened. Billing follows the two dates.
            set_setting("catalog_opened_on", ""); set_setting("billing_starts_on", ""); db.execute("DELETE FROM calculator_leads"); db.commit()
            self.assertFalse(billing.catalog_ready())
            set_setting("investor_signup_open", "open")
            self.assertIsNone(billing.catalog_opened(as_of=today))
            self.assertIn(b"Create your free account", self.c.get("/signup").data)
            self.assertEqual(billing.run_billing(as_of=after)["issued"], 0)
            set_setting("investor_signup_open", "closed"); set_setting("catalog_opened_on", today.isoformat())
            self.assertEqual(billing.catalog_opened(as_of=today), today)
            self.assertIn(b"Not open yet", self.c.get("/signup").data)
            set_setting("investor_signup_open", "auto"); set_setting("catalog_opened_on", "")
            # The list the gate asks for is capped (a manager can change a minimum without review)
            db.execute("UPDATE funds SET min_investment = 1 WHERE status = 'live'"); db.commit()
            self.assertEqual(billing.readiness()["leads_needed"], 5000)
            self.assertIn("capped", billing.billing_status())
            set_setting("investor_list_cap", "0")
            self.assertEqual(billing.readiness()["leads_needed"], 125000000)

    def test_receipt_email_when_a_payment_is_recorded(self):
        with self.app.app_context(), self.app.test_request_context():
            inv = get_db().execute("SELECT * FROM invoices WHERE kind = 'listing'").fetchone()
            billing.record_payment(inv["id"], "bank transfer", 1)
        outbox = self.app.config["MAIL_OUTBOX"]
        texts = [open(os.path.join(outbox, n), encoding="utf-8").read() for n in os.listdir(outbox)]
        receipts = [t for t in texts if "Subject: Receipt: invoice " in t]
        self.assertEqual(len(receipts), 1)
        self.assertIn("To: manager@luminaz.test", receipts[0]); self.assertIn("$850.00 by bank transfer", receipts[0])

    def test_landing_pages_carry_header_footer_disclosure_about_and_categories(self):
        # 14 October 2026: two front doors with the platform disclosure in every footer, an About
        # page, eight categories, no "vetted" anywhere, and the 18-year signature.
        from luminaz.db import DEFAULT_SETTINGS, CATEGORIES
        self.assertEqual(len(CATEGORIES), 8); self.assertIn("Energy", CATEGORIES)
        self.assertIn("18 years", DEFAULT_SETTINGS["founder_signature"])
        inv = self.c.get("/").data; mgr = self.c.get("/managers/").data; about = self.c.get("/about").data
        for page in (inv, mgr, about):
            self.assertIn(b"not a broker-dealer, investment adviser or finder", page)            # footer disclosure
            self.assertIn(b"does not verify or certify anyone", page)
            self.assertIn(b"solely responsible for verifying accredited status under Rule 506(c)", page)
            self.assertIn(b"We do not sell your data", page)
            self.assertIn(b'href="/about"', page)
            self.assertNotIn(b"vetted", page.lower()); self.assertNotIn(b"Vetted", page)
        self.assertIn(b"Start with the kind of fund you want", inv)
        for c in CATEGORIES:
            self.assertIn(c.encode(), inv); self.assertIn(c.encode(), mgr)
        self.assertIn(b"Luminaz <span class=\"brand-sub\">for Fund Managers</span>", mgr)       # manager-side header
        self.assertNotIn(b"brand-sub", inv)
        self.assertIn(b"$850", mgr); self.assertIn(b"end of each month", mgr); self.assertIn(b"Free until the investor catalog opens", mgr)
        self.assertNotIn(b"Book a 15-minute call", mgr)
        with self.app.app_context():
            set_setting("booking_url", "https://outlook.office.com/book/luminaz")
        self.assertIn(b"Book a 15-minute call", self.c.get("/managers/").data)
        self.assertIn(b"Diane and her husband Cliff", about); self.assertIn(b"eighteen years", about)
        self.assertNotIn(b"Series", about)                                                    # no licensing claims on the public pages
        self.assertIn(b"/about", self.c.get("/sitemap.xml").data)

    def test_catalog_tiles_keep_posting_order_and_the_new_categories_filter(self):
        self.login("manager@luminaz.test")
        with self.app.app_context():
            db = get_db()
            firm = db.execute("SELECT id FROM firms WHERE name = 'Ridgeline Capital'").fetchone()["id"]
            for i, (name, cat, day) in enumerate((("Zeta Energy Fund I", "Energy", 30), ("Alpha Timber Fund", "Agriculture and timber", 20))):
                db.execute("INSERT INTO funds(firm_id, name, category, strategy, target_raise, min_investment, term_years, status, live_since, free_until, monthly_rate, fund_number, created_at)"
                           " VALUES (?, ?, ?, 'Sample strategy', 1000000, 25000, 5, 'live', ?, ?, 750, ?, ?)",
                           (firm, name, cat, (dt.date.today() - dt.timedelta(days=day)).isoformat(), (dt.date.today() - dt.timedelta(days=day)).isoformat(), 10 + i, dt.date.today().isoformat()))
            db.commit()
        self.c.get("/logout"); self.login("investor2@luminaz.test")
        page = self.c.get("/funds").data
        self.assertIn(b'class="tiles"', page); self.assertIn(b'<main class="wide">', page)
        self.assertLess(page.index(b"Ridgeline Acquisition Fund I"), page.index(b"Zeta Energy Fund I"))      # oldest listing first
        self.assertLess(page.index(b"Zeta Energy Fund I"), page.index(b"Alpha Timber Fund"))                # then by date, never by name
        self.assertNotIn(b"Acquire 6 to 8 founder-owned", page)                                            # strategy stays on the fund page
        only = self.c.get("/funds?category=Energy").data
        self.assertIn(b"Zeta Energy Fund I", only); self.assertNotIn(b"Ridgeline Acquisition Fund I", only)

    def test_investor_can_pause_and_resume(self):
        self.login("investor@luminaz.test")
        self.assertIn(b"Pause my account", self.c.get("/notifications").data)
        r = self.c.post("/notifications", data={"action": "pause"}, follow_redirects=True)
        self.assertIn(b"Paused.", r.data); self.assertIn(b"Resume my account", r.data)
        me = self.c.get("/me").data
        self.assertIn(b"Your account is paused", me); self.assertNotIn(b"Ridgeline Acquisition Fund I", me)   # shortlist hidden
        with self.app.app_context():
            u = get_db().execute("SELECT paused_at, marketing_opt_in FROM users WHERE email = 'investor@luminaz.test'").fetchone()
            self.assertTrue(u["paused_at"]); self.assertEqual(u["marketing_opt_in"], 1)      # their choice is kept, the pause is what stops emails
            self.assertTrue(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'investor@luminaz.test'").fetchone())
        self.assertEqual(self.c.get("/funds").status_code, 200)                                           # the account still works
        r = self.c.post("/notifications", data={"action": "resume"}, follow_redirects=True)
        self.assertIn(b"Welcome back", r.data)
        self.assertIn(b"Ridgeline Acquisition Fund I", self.c.get("/me").data)
        with self.app.app_context():
            u = get_db().execute("SELECT paused_at, marketing_opt_in FROM users WHERE email = 'investor@luminaz.test'").fetchone()
            self.assertIsNone(u["paused_at"]); self.assertEqual(u["marketing_opt_in"], 1)

    def test_verification_article_and_the_box_before_requesting_materials(self):
        a = self.c.get("/learn/how-accredited-status-is-verified")
        self.assertEqual(a.status_code, 200)
        self.assertIn(b"The fund manager verifies, not Luminaz", a.data); self.assertIn(b"within three months", a.data)
        self.assertIn(b"does not endorse, select or vouch", a.data); self.assertIn(b"receives nothing from them", a.data)
        self.assertNotIn(b"recommend", a.data[:a.data.index(b"Luminaz describes funds")])                   # no recommending any service
        self.assertIn(b"how-accredited-status-is-verified", self.c.get("/learn").data)
        self.assertIn(b"how-accredited-status-is-verified", self.c.get("/sitemap.xml").data)
        self.login("investor2@luminaz.test")
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Ridgeline%'").fetchone()["id"]
        page = self.c.get("/funds/%d" % fid).data
        self.assertIn(b"Before you request materials", page); self.assertIn(b"/learn/how-accredited-status-is-verified", page)

    def test_sign_in_cannot_bounce_to_another_website(self):
        # HANDOFF finding 7. A correct password must land on this site whatever ?next= says.
        for bad in ("//example.com", "https://example.com/x", "/\\example.com", "funds"):
            r = self.c.post("/login?next=" + bad, data={"email": "investor@luminaz.test", "password": demo_data.PW})
            self.assertEqual(r.status_code, 302)
            self.assertNotIn("example.com", r.headers["Location"], bad)
            self.assertTrue(r.headers["Location"].startswith(("/", "http://localhost/")), r.headers["Location"])
            self.c.get("/logout")
        r = self.c.post("/login?next=/funds", data={"email": "investor@luminaz.test", "password": demo_data.PW})
        self.assertTrue(r.headers["Location"].endswith("/funds"))

    def test_admins_must_set_up_two_step_sign_in_before_any_admin_page(self):
        # Finding 12. The privacy policy promises it; the code now enforces it (Settings: require_admin_2fa).
        from luminaz import twofactor
        with self.app.app_context():
            set_setting("require_admin_2fa", "1")
        self.login("admin@luminaz.test")
        for path in ("/admin/", "/admin/billing", "/admin/settings"):
            r = self.c.get(path)
            self.assertEqual(r.status_code, 302, path); self.assertTrue(r.headers["Location"].endswith("/security"))
        r = self.c.get("/admin/", follow_redirects=True)
        self.assertIn(b"Set up two-step sign-in before using the review desk", r.data)
        r = self.c.post("/security", data={"action": "start"})
        with self.c.session_transaction() as sess:
            secret = sess["setup_secret"]
        self.c.post("/security", data={"action": "confirm", "code": twofactor.totp(secret)})
        self.assertEqual(self.c.get("/admin/").status_code, 200)                        # now allowed
        self.c.get("/logout"); self.login("manager@luminaz.test")
        self.assertEqual(self.c.get("/managers/dashboard").status_code, 200)            # managers are not affected

    def test_password_reset_links_expire_and_work_once(self):
        # Finding 8.
        from luminaz import auth
        self.c.post("/forgot", data={"email": "investor@luminaz.test"})
        outbox = self.app.config["MAIL_OUTBOX"]
        mails = [open(os.path.join(outbox, n), encoding="utf-8").read() for n in os.listdir(outbox)]
        text = [m for m in mails if "Reset your Luminaz password" in m][0]
        self.assertIn("works for 60 minutes and once only", text)
        import re
        token = re.search(r"/reset/([A-Za-z0-9_\-]+)", text).group(1)
        with self.app.app_context():
            u = get_db().execute("SELECT * FROM users WHERE email = 'investor@luminaz.test'").fetchone()
            self.assertEqual(u["reset_token"], token); self.assertIsNone(u["confirm_token"])       # the confirmation token is untouched
            self.assertTrue(auth.reset_link_valid(u))
            self.assertFalse(auth.reset_link_valid(u, at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=61)))
        self.assertEqual(self.c.get("/reset/" + token).status_code, 200)
        r = self.c.post("/reset/" + token, data={"password": "a-brand-new-password"}, follow_redirects=True)
        self.assertIn(b"Password updated", r.data)
        r = self.c.get("/reset/" + token, follow_redirects=True)
        self.assertIn(b"expired or was already used", r.data)                            # once only
        # An old link: sent 61 minutes ago
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET reset_token = 'old-token', reset_sent_at = ? WHERE email = 'investor@luminaz.test'",
                       ((dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=61)).replace(microsecond=0).isoformat(),)); db.commit()
        r = self.c.get("/reset/old-token", follow_redirects=True)
        self.assertIn(b"expired or was already used", r.data)
        r = self.c.post("/login", data={"email": "investor@luminaz.test", "password": "a-brand-new-password"})
        self.assertEqual(r.status_code, 302)                                             # the new password works

    def test_backup_is_copied_to_the_off_server_folder_when_set(self):
        from luminaz import jobs
        copy_dir = os.path.join(self.tmp, "offsite")
        os.makedirs(copy_dir)
        with self.app.app_context():
            set_setting("backup_copy_dir", copy_dir)
            dest = jobs.backup()
        self.assertTrue(os.path.exists(os.path.join(copy_dir, os.path.basename(dest))))
        with self.app.app_context():
            set_setting("backup_copy_dir", os.path.join(self.tmp, "does-not-exist"))
            self.assertTrue(jobs.backup())                                               # a missing folder never breaks the backup itself

    def test_webinar_signup_locked_until_attorney_approves_then_the_whole_flow(self):
        # Diane chose webinars to collect investor contacts (9 October). Launch Tasks: Luminaz runs
        # sign-ups, reminders and follow-up; Zoom only hosts the call; nothing goes out until the
        # attorney approves (AGENTS.md section 5).
        from luminaz import webinars
        tomorrow = (dt.datetime.now() + dt.timedelta(days=1)).strftime("%Y-%m-%dT10:00")
        with self.app.app_context():
            set_setting("attorney_approved", "0")
        self.login("admin@luminaz.test")
        r = self.c.post("/admin/webinars", data={"title": "How Private Funds Work", "audience": "investors", "starts_at": tomorrow,
                                                 "zoom_url": "https://zoom.us/j/123", "description": "Fifteen minutes, no selling."}, follow_redirects=True)
        self.assertIn(b"created as a draft", r.data)
        with self.app.app_context():
            wid = get_db().execute("SELECT id FROM webinars").fetchone()["id"]
        self.c.post("/admin/webinars/%d" % wid, data={"action": "save", "title": "How Private Funds Work", "audience": "investors", "starts_at": tomorrow,
                                                      "zoom_url": "https://zoom.us/j/123", "replay_url": "", "description": "Fifteen minutes, no selling.", "status": "open"})
        self.assertIn(b"Locked until the attorney approves", self.c.get("/admin/webinars/%d" % wid).data)
        self.assertIn(b"Preview: sign-ups are locked", self.c.get("/webinars/%d" % wid).data)     # an admin can preview
        self.c.get("/logout")
        # Locked for the public: coming soon, and no sign-up accepted
        self.assertIn(b"Coming soon", self.c.get("/webinars").data)
        self.assertIn(b"Coming soon", self.c.get("/webinars/%d" % wid).data)
        self.c.post("/webinars/%d?src=linkedin" % wid, data={"name": "Pat Early", "email": "pat@x.com", "consent": "on"})
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM webinar_registrations").fetchone()[0], 0)
            self.assertEqual(webinars.send_reminders(), 0)
            set_setting("attorney_approved", "1")
        # Approved: the public list, the sign-up, consent recorded, the source kept, the email with the join link
        self.assertIn(b"Save my seat", self.c.get("/webinars").data)
        r = self.c.post("/webinars/%d?src=linkedin" % wid, data={"name": "Pat Early", "email": "Pat@X.com"})
        self.assertIn(b"tick the box", r.data)
        r = self.c.post("/webinars/%d?src=linkedin" % wid, data={"name": "Pat Early", "email": "Pat@X.com", "consent": "on"})
        self.assertIn(b"You're registered", r.data)
        with self.app.app_context():
            reg = get_db().execute("SELECT * FROM webinar_registrations").fetchone()
            self.assertEqual((reg["email"], reg["source"], reg["consent_text"][:30]), ("pat@x.com", "linkedin", webinars.CONSENT_WEBINAR[:30]))
            self.assertTrue(reg["consent_at"]); self.assertIsNone(reg["joined_at"])
        outbox = self.app.config["MAIL_OUTBOX"]
        import quopri
        def mails(subject):
            texts = [quopri.decodestring(open(os.path.join(outbox, n), "rb").read()).decode("utf-8") for n in os.listdir(outbox)]
            return [t for t in texts if subject in t]
        conf = mails("Subject: You're registered: How Private Funds Work")
        self.assertEqual(len(conf), 1); self.assertIn("/webinars/%d/join/%s" % (wid, reg["token"]), conf[0]); self.assertIn("/unsubscribe/" + reg["token"], conf[0])
        r = self.c.post("/webinars/%d" % wid, data={"name": "Pat Early", "email": "pat@x.com", "consent": "on"})
        self.assertIn(b"already registered", r.data)                                       # no duplicate, no second email
        self.assertEqual(len(mails("Subject: You're registered: How Private Funds Work")), 1)
        # The personal join link records the click and sends them to Zoom
        r = self.c.get("/webinars/%d/join/%s" % (wid, reg["token"]))
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "https://zoom.us/j/123"))
        with self.app.app_context():
            self.assertTrue(get_db().execute("SELECT joined_at FROM webinar_registrations").fetchone()[0])
        self.assertEqual(self.c.get("/webinars/%d/join/not-a-token" % wid).status_code, 404)
        # The reminder goes once, the day before, through the daily job
        with self.app.app_context(), self.app.test_request_context():
            self.assertEqual(webinars.send_reminders(), 1)
            self.assertEqual(webinars.send_reminders(), 0)
            self.assertEqual(len(mails("Subject: Tomorrow: How Private Funds Work")), 1)
            self.assertIn("100 Test Street, Acworth", mails("Subject: Tomorrow:")[0])               # marketing footer and unsubscribe
        # Attendance, then the replay once it is done
        self.login("admin@luminaz.test")
        self.c.post("/admin/webinars/%d" % wid, data={"action": "attended", "attended": [str(reg["id"])]})
        page = self.c.get("/admin/webinars/%d" % wid).data
        self.assertIn(b"linkedin 1", page); self.assertIn(b"pat@x.com", page)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT attended FROM webinar_registrations").fetchone()[0], 1)
        self.c.post("/admin/webinars/%d" % wid, data={"action": "save", "title": "How Private Funds Work", "audience": "investors", "starts_at": tomorrow,
                                                      "zoom_url": "https://zoom.us/j/123", "replay_url": "https://youtu.be/replay", "description": "", "status": "done"})
        with self.app.app_context(), self.app.test_request_context():
            self.assertEqual(webinars.send_replays(), 1); self.assertEqual(webinars.send_replays(), 0)
            self.assertIn("https://youtu.be/replay", mails("Subject: Replay: How Private Funds Work")[0])
        self.assertEqual(self.c.get("/webinars/%d" % wid).status_code, 200)                 # admins can still open a done webinar
        self.c.get("/logout")
        self.assertEqual(self.c.get("/webinars/%d" % wid).status_code, 404)                 # the public cannot
        # The unsubscribe link in any webinar email stops the rest
        self.c.get("/unsubscribe/" + reg["token"])
        with self.app.app_context():
            self.assertTrue(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'pat@x.com'").fetchone())

    def test_marketing_spend_and_cost_per_accredited_lead(self):
        # Diane, 14 October 2026: track ROI for marketing. Spend is typed in; nothing is tied to an investment.
        from luminaz import metrics
        month = dt.date.today().strftime("%Y-%m")
        self.login("admin@luminaz.test")
        r = self.c.post("/admin/metrics", data={"month": month, "source": "LinkedIn", "amount": "$1,200", "note": "one newsletter ad"}, follow_redirects=True)
        self.assertIn(b"Spend recorded", r.data)
        r = self.c.post("/admin/metrics", data={"month": "bad", "source": "", "amount": "x"}, follow_redirects=True)
        self.assertIn(b"are needed", r.data)
        with self.app.app_context():
            db = get_db()
            for i, res in enumerate(("accredited", "accredited", "not_accredited")):
                db.execute("INSERT INTO calculator_leads(email, result, basis, source, created_at) VALUES (?, ?, 'income', 'linkedin', ?)", ("r%d@x.com" % i, res, now_iso()))
            db.commit()
            rows = {(r["month"], r["source"]): r for r in metrics.roi()}
            row = rows[(month, "linkedin")]
            self.assertEqual((row["spend"], row["leads"], row["accredited"], row["cost_per_accredited"]), (1200.0, 3, 2, 600.0))
            self.assertIn((month, "demo"), rows)                                             # the sample leads, no spend: "free"
        page = self.c.get("/admin/metrics").data
        self.assertIn(b"$600", page); self.assertIn(b"linkedin", page)

    def test_manager_uploads_document_admin_sees_it(self):
        import io
        self.login("manager@luminaz.test")
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Ridgeline%'").fetchone()["id"]
        r = self.c.post("/managers/funds/%d/documents" % fid, data={"kind": "ppm", "file": (io.BytesIO(b"%PDF-1.4 test"), "ppm.pdf")},
                        content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        with self.app.app_context():
            d = get_db().execute("SELECT * FROM fund_documents").fetchone()
            self.assertEqual(d["kind"], "ppm")
        # Investors never see it; admin can download it
        self.c.get("/logout"); self.login("investor@luminaz.test")
        self.assertEqual(self.c.get("/admin/documents/%d" % d["id"]).status_code, 403)
        self.c.get("/logout"); self.login("admin@luminaz.test")
        r = self.c.get("/admin/documents/%d" % d["id"])
        self.assertEqual(r.status_code, 200); self.assertIn(b"%PDF", r.data)

    def test_two_factor_round_trip(self):
        from luminaz import twofactor
        self.login("admin@luminaz.test")
        r = self.c.post("/security", data={"action": "start"})
        self.assertIn(b"otpauth://", r.data)
        with self.c.session_transaction() as sess:
            secret = sess["setup_secret"]
        r = self.c.post("/security", data={"action": "confirm", "code": twofactor.totp(secret)})
        self.assertIn(b"recovery", r.data.lower())
        # Next login needs the code
        self.c.get("/logout")
        r = self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW}, follow_redirects=True)
        self.assertIn(b"authenticator", r.data.lower())
        self.assertEqual(self.c.get("/admin/").status_code, 302)   # not signed in yet
        r = self.c.post("/login/verify", data={"code": "000000"}, follow_redirects=True)
        self.assertIn(b"t match", r.data)
        r = self.c.post("/login/verify", data={"code": twofactor.totp(secret)}, follow_redirects=True)
        self.assertEqual(self.c.get("/admin/").status_code, 200)

    def test_education_sequence_sends_weekly_and_honors_unsubscribe(self):
        from luminaz import jobs
        self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                         "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "lead@x.com", "consent": "on"})
        with self.app.app_context():
            before = len(os.listdir(self.app.config["MAIL_OUTBOX"]))
            n = get_db().execute("SELECT COUNT(DISTINCT email) FROM calculator_leads WHERE result = 'accredited'").fetchone()[0]
            with self.app.test_request_context():
                self.assertEqual(jobs.send_education(), n)
                self.assertEqual(jobs.send_education(), 0)          # not twice in a week
                later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
                self.assertEqual(jobs.send_education(as_of=later), n)
            lead = get_db().execute("SELECT * FROM calculator_leads WHERE email = 'lead@x.com'").fetchone()
            self.assertEqual(lead["sequence_step"], 2)
            token = lead["unsub_token"]
            files = sorted(os.listdir(self.app.config["MAIL_OUTBOX"]))
            self.assertEqual(len(files), before + 2 * n)
            mine = [f for f in files if "lead_x_com" in f]
            self.assertIn("/unsubscribe/" + token, open(os.path.join(self.app.config["MAIL_OUTBOX"], mine[-1])).read())
        r = self.c.get("/unsubscribe/" + token)
        self.assertIn(b"unsubscribed", r.data)
        with self.app.app_context(), self.app.test_request_context():
            later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
            self.assertEqual(jobs.send_education(as_of=later), n - 1)   # everyone but the unsubscribed lead
            lead = get_db().execute("SELECT * FROM calculator_leads WHERE email = 'lead@x.com'").fetchone()
            self.assertEqual(lead["sequence_step"], 2); self.assertEqual(lead["unsubscribed"], 1)

    def test_request_nudge_after_three_days(self):
        from luminaz import jobs
        self.login("investor2@luminaz.test")
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Ridgeline%'").fetchone()["id"]
        self.c.post("/funds/%d/request" % fid, data={"message": "Send PPM"}, follow_redirects=True)
        with self.app.app_context(), self.app.test_request_context():
            self.assertEqual(jobs.nudge_managers(), 0)
            later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=4)
            self.assertEqual(jobs.nudge_managers(as_of=later), 1)
            self.assertEqual(jobs.nudge_managers(as_of=later), 0)   # touched now, no repeat

    def test_support_agent_refuses_fund_merit_and_answers_howto(self):
        from luminaz import support
        a, kind = support.answer("Is Ridgeline a good investment? Should I invest?")
        self.assertEqual(kind, "auto"); self.assertIn("doesn't evaluate", a)
        a, kind = support.answer("How do I reset my password?")
        self.assertEqual(kind, "auto"); self.assertIn("Forgot password", a)
        a, kind = support.answer("Does the moon affect fund closings?")
        self.assertEqual(kind, "escalated")
        r = self.c.post("/support", data={"email": "q@x.com", "question": "Does the moon affect fund closings?"})
        self.assertIn(b"passed it to a person", r.data)
        with self.app.app_context():
            t = get_db().execute("SELECT * FROM support_tickets").fetchone()
            self.assertEqual(t["kind"], "escalated")

    def test_outreach_import_draft_send_followup(self):
        import io
        from luminaz import jobs
        self.login("admin@luminaz.test")
        csv = ("priority,fund_name,luminaz_category,state,signer,total_offering,filed,filing_url,email\n"
               "9,Peachtree Debt Fund I,Private debt,GA,Sam Ortiz,20000000,2026-09-01,https://sec.gov/x,sam@peachtree.test\n")
        r = self.c.post("/admin/outreach", data={"action": "import", "csv": (io.BytesIO(csv.encode()), "leads.csv")},
                        content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"Imported 1 leads", r.data)
        with self.app.app_context():
            o = get_db().execute("SELECT * FROM outreach").fetchone()
        r = self.c.post("/admin/outreach/%d" % o["id"], data={"action": "draft"}, follow_redirects=True)
        self.assertIn(b"Hi Sam,", r.data); self.assertIn(b"Peachtree Debt Fund I", r.data)
        self.assertIn(b"no success fee", r.data); self.assertNotIn(b"every dollar", r.data)
        with self.app.app_context():
            o = get_db().execute("SELECT * FROM outreach").fetchone()
            self.assertEqual(o["status"], "drafted")
            before = len(os.listdir(self.app.config["MAIL_OUTBOX"]))
        r = self.c.post("/admin/outreach/%d" % o["id"], data={"action": "send", "draft_subject": o["draft_subject"], "draft_body": o["draft_body"]}, follow_redirects=True)
        self.assertIn(b"Sent to sam@peachtree.test", r.data)
        with self.app.app_context():
            self.assertEqual(len(os.listdir(self.app.config["MAIL_OUTBOX"])), before + 1)
            with self.app.test_request_context():
                self.assertEqual(jobs.outreach_followups(), 0)
                later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=6)
                self.assertEqual(jobs.outreach_followups(as_of=later), 1)
            # Rule 4.7: the job drafted the follow-up; nothing was sent until a founder approves it
            row = get_db().execute("SELECT * FROM outreach").fetchone()
            self.assertEqual(row["status"], "followup_drafted"); self.assertIn("Bumping this once", row["followup_body"])
            self.assertEqual(len(os.listdir(self.app.config["MAIL_OUTBOX"])), before + 1)
        self.assertIn(b"Approve and send the follow-up", self.c.get("/admin/outreach/%d" % o["id"]).data)
        r = self.c.post("/admin/outreach/%d" % o["id"], data={"action": "send_followup", "followup_body": row["followup_body"]}, follow_redirects=True)
        self.assertIn(b"Follow-up sent to sam@peachtree.test", r.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT status FROM outreach").fetchone()["status"], "followed_up")
            self.assertEqual(len(os.listdir(self.app.config["MAIL_OUTBOX"])), before + 2)
        r = self.c.post("/admin/outreach/%d" % o["id"], data={"action": "status", "status": "yes"}, follow_redirects=True)
        self.assertIn(b"Marked yes", r.data)

    def test_marketing_posts_draft_approve_send(self):
        from luminaz import marketing
        from luminaz.content.posts import POSTS
        self.assertEqual(len(POSTS), 40)        # 36 + four family-office posts (change 32)
        for p in POSTS:
            self.assertLessEqual(len(p["short"].replace("{calculator_url}", "https://luminaztechnology.com/calculator")), 280, p["topic"])
            for bad in ("guarantee", "% return", "outperform", "IRR"):
                self.assertNotIn(bad.lower(), (p["long"] + p["short"]).lower(), p["topic"])
        monday = dt.date(2026, 10, 5)
        with self.app.app_context(), self.app.test_request_context():
            before = len(os.listdir(self.app.config["MAIL_OUTBOX"]))
            self.assertEqual(marketing.plan_posts(today=monday), 8)       # this week + next: 6 investor posts + 2 manager Tuesdays (change 28)
            self.assertEqual(marketing.plan_posts(today=monday), 0)       # idempotent
            self.assertEqual(len(os.listdir(self.app.config["MAIL_OUTBOX"])), before + 1)   # one "waiting for approval" email
            self.assertEqual(marketing.publish_posts(today=monday), 0)    # nothing approved -> nothing sent
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/marketing")
        self.assertIn(b"waiting for approval", r.data)
        with self.app.app_context():
            first = get_db().execute("SELECT * FROM posts ORDER BY scheduled_for, id").fetchone()
        r = self.c.post("/admin/marketing", data={"action": "approve", "post_id": first["id"], "topic": first["topic"],
                                                 "long_body": first["long_body"], "short_body": first["short_body"], "tags": first["tags"]}, follow_redirects=True)
        self.assertIn(b"Approved", r.data)
        with self.app.app_context(), self.app.test_request_context():
            before = len(os.listdir(self.app.config["MAIL_OUTBOX"]))
            self.assertEqual(marketing.publish_posts(today=monday - dt.timedelta(days=1)), 0)   # not its day yet
            self.assertEqual(marketing.publish_posts(today=monday), 1)
            self.assertEqual(marketing.publish_posts(today=monday), 0)
            files = sorted(os.listdir(self.app.config["MAIL_OUTBOX"]))
            self.assertEqual(len(files), before + 1)
            body = open(os.path.join(self.app.config["MAIL_OUTBOX"], files[-1])).read()
            self.assertIn("/calculator", body); self.assertIn("never recommends", body)
            p = get_db().execute("SELECT * FROM posts WHERE id = ?", (first["id"],)).fetchone()
            self.assertEqual(p["status"], "published"); self.assertEqual(p["published_via"], "email")
            # Drafts that pass their date are never sent
            self.assertEqual(marketing.publish_posts(today=monday + dt.timedelta(days=30)), 0)

    def test_seo_pages(self):
        r = self.c.get("/learn"); self.assertEqual(r.status_code, 200); self.assertIn(b"accredited investor guide", r.data.lower())
        r = self.c.get("/learn/you-may-already-qualify"); self.assertEqual(r.status_code, 200)
        self.assertIn(b'"@type":"Article"', r.data); self.assertIn(b'rel="canonical"', r.data); self.assertNotIn(b"noindex", r.data)
        self.assertEqual(self.c.get("/learn/nope").status_code, 404)
        r = self.c.get("/sitemap.xml"); self.assertEqual(r.status_code, 200); self.assertIn(b"/learn/you-may-already-qualify", r.data)
        self.assertEqual(r.data.count(b"<url>"), 8 + 40 + 2)        # + /about and the verification article (14 Oct 2026); 40 Learn articles since change 32
        r = self.c.get("/robots.txt"); self.assertIn(b"Disallow: /admin/", r.data); self.assertIn(b"Sitemap:", r.data)
        self.assertIn(b'"@type":"FAQPage"', self.c.get("/calculator").data)
        self.assertIn(b'meta name="description"', self.c.get("/").data)
        self.login("admin@luminaz.test")
        self.assertIn(b"noindex", self.c.get("/admin/").data)

    def test_tracking_and_metrics(self):
        from luminaz import metrics, jobs
        ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120"}
        self.c.get("/?src=linkedin", headers=ua); self.c.get("/calculator", headers=ua); self.c.get("/learn", headers=ua)
        self.c.get("/", headers={"User-Agent": "Googlebot/2.1"})                    # bots not counted
        self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                         "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "t@x.com", "consent": "on"}, headers=ua)
        with self.app.app_context():
            db = get_db()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM page_views").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(DISTINCT visitor) FROM page_views").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT source FROM page_views WHERE path = '/learn'").fetchone()[0], "linkedin")
            self.assertEqual(db.execute("SELECT source FROM calculator_leads WHERE email = 't@x.com'").fetchone()[0], "linkedin")
            self.assertFalse(db.execute("SELECT 1 FROM page_views WHERE visitor LIKE '%.%'").fetchone())   # no raw IPs stored
            w = metrics.weekly(2)
            self.assertEqual(len(w), 2); self.assertEqual(w[-1]["visitors"], 1); self.assertEqual(w[-1]["calculator_views"], 1)
            src = metrics.sources()
            self.assertEqual(src["visits"][0]["source"], "linkedin")
            subject, body = metrics.summary()
            self.assertIn("Calculator leads", body); self.assertIn("MONEY", body)
            with self.app.test_request_context():
                monday = dt.date(2026, 10, 5)
                before = len(os.listdir(self.app.config["MAIL_OUTBOX"]))
                self.assertEqual(jobs.weekly_summary(today=monday), 1)
                self.assertEqual(jobs.weekly_summary(today=monday), 0)                    # once per Monday
                self.assertEqual(jobs.weekly_summary(today=monday + dt.timedelta(days=1)), 0)   # not on Tuesday
                self.assertEqual(len(os.listdir(self.app.config["MAIL_OUTBOX"])), before + 1)
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/metrics"); self.assertEqual(r.status_code, 200); self.assertIn(b"The funnel", r.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM page_views WHERE path LIKE '/admin%'").fetchone()[0], 0)

    def test_consent_and_unsubscribe_everywhere(self):
        from luminaz import jobs, mail
        ua = {}
        # Calculator without consent is refused; with consent the consent text and time are recorded
        r = self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                             "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "c@x.com"}, follow_redirects=True)
        self.assertIn(b"tick the box", r.data)
        self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                         "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "c@x.com", "consent": "on"})
        with self.app.app_context():
            lead = get_db().execute("SELECT * FROM calculator_leads WHERE email = 'c@x.com'").fetchone()
            self.assertEqual(lead["consent_text"], mail.CONSENT_CALCULATOR); self.assertTrue(lead["consent_at"])
        # Manager sign-up without consent is refused
        r = self.c.post("/managers/signup", data={"name": "B", "firm_name": "B Cap", "email": "b@x.com", "password": "longpassword1"})
        self.assertIn(b"agree to receive account notices", r.data)
        # Education email carries postal address, unsubscribe line and one-click headers
        with self.app.app_context(), self.app.test_request_context():
            jobs.send_education()
            files = sorted(os.listdir(self.app.config["MAIL_OUTBOX"]))
            body = open(os.path.join(self.app.config["MAIL_OUTBOX"], [f for f in files if "c_x_com" in f][-1])).read()
            self.assertIn("List-Unsubscribe-Post: List-Unsubscribe=One-Click", body)
            self.assertIn("Acworth", body)
            token = get_db().execute("SELECT unsub_token FROM calculator_leads WHERE email = 'c@x.com'").fetchone()[0]
        # One-click POST unsubscribe (what mail clients send), then nothing marketing goes to that address
        self.assertEqual(self.c.post("/unsubscribe/" + token).status_code, 200)
        with self.app.app_context(), self.app.test_request_context():
            self.assertTrue(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'c@x.com'").fetchone())
            later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
            jobs.send_education(as_of=later)
            self.assertEqual(mail.send("c@x.com", "x", "y", kind="marketing"), "suppressed")
            self.assertNotEqual(mail.send("c@x.com", "x", "y"), "suppressed")           # account notices still go
        # Account holder: notifications page turns marketing off and on; account notices unaffected
        self.login("investor@luminaz.test")
        r = self.c.get("/notifications"); self.assertEqual(r.status_code, 200); self.assertIn(b"Account notices", r.data)
        self.c.post("/notifications", data={})
        with self.app.app_context():
            u = get_db().execute("SELECT * FROM users WHERE email = 'investor@luminaz.test'").fetchone()
            self.assertEqual(u["marketing_opt_in"], 0)
            self.assertTrue(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'investor@luminaz.test'").fetchone())
        self.c.post("/notifications", data={"marketing": "on"})
        with self.app.app_context():
            self.assertFalse(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'investor@luminaz.test'").fetchone())
        # Outreach contact who unsubscribes becomes do-not-contact and can't be emailed again
        self.c.get("/logout"); self.login("admin@luminaz.test")
        self.c.post("/admin/outreach", data={"action": "add", "fund_name": "Z Fund", "email": "z@x.com", "contact_name": "Zed"}, follow_redirects=True)
        with self.app.app_context():
            o = get_db().execute("SELECT * FROM outreach WHERE email = 'z@x.com'").fetchone()
        self.c.post("/admin/outreach/%d" % o["id"], data={"action": "draft"}, follow_redirects=True)
        with self.app.app_context():
            o = get_db().execute("SELECT * FROM outreach WHERE email = 'z@x.com'").fetchone()
        self.c.post("/admin/outreach/%d" % o["id"], data={"action": "send", "draft_subject": o["draft_subject"], "draft_body": o["draft_body"]}, follow_redirects=True)
        with self.app.app_context():
            o = get_db().execute("SELECT * FROM outreach WHERE email = 'z@x.com'").fetchone()
            self.assertTrue(o["unsub_token"])
        self.c.get("/unsubscribe/" + o["unsub_token"])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT status FROM outreach WHERE email = 'z@x.com'").fetchone()[0], "do_not_contact")
        r = self.c.post("/admin/outreach/%d" % o["id"], data={"action": "status", "status": "new"}, follow_redirects=True)
        r = self.c.post("/admin/outreach/%d" % o["id"], data={"action": "send", "draft_subject": "s", "draft_body": "b"}, follow_redirects=True)
        self.assertIn(b"asked not to be contacted", r.data)

    def test_login_throttle_and_csrf_guard(self):
        r = self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status_code, 403)
        r = self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        r = self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW}, headers={"Sec-Fetch-Site": "same-origin"})
        self.assertEqual(r.status_code, 302)
        self.c.get("/logout")
        for _ in range(8):
            self.c.post("/login", data={"email": "investor@luminaz.test", "password": "wrong-password-1"})
        r = self.c.post("/login", data={"email": "investor@luminaz.test", "password": demo_data.PW})
        self.assertEqual(r.status_code, 429)          # right password, still paused: that's the point
        r = self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW}, headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(r.status_code, 302)          # a different address and account is unaffected

    def test_error_pages(self):
        r = self.c.get("/no-such-page"); self.assertEqual(r.status_code, 404); self.assertIn(b"Am I accredited?", r.data)
        self.login("investor@luminaz.test")
        r = self.c.get("/admin/"); self.assertEqual(r.status_code, 403); self.assertIn(b"access", r.data)

    def test_gzip_and_cache_headers(self):
        r = self.c.get("/", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(r.headers.get("Content-Encoding"), "gzip")
        import gzip as gz
        self.assertIn(b"accredited investors", gz.decompress(r.data))
        self.assertEqual(self.c.get("/").headers.get("Content-Encoding"), None)
        self.assertIn("max-age", self.c.get("/static/style.css").headers["Cache-Control"])
        self.assertEqual(self.c.get("/").headers["Cache-Control"], "no-store")

    def test_daily_button_and_backup(self):
        self.login("admin@luminaz.test")
        r = self.c.post("/admin/daily", follow_redirects=True)
        self.assertIn(b"Daily tasks done", r.data)
        backups = os.listdir(os.path.join(self.app.instance_path, "backups"))
        self.assertTrue(any(b.endswith(".sqlite") for b in backups))

    def test_two_domain_routing(self):
        with self.app.app_context():
            set_setting("investor_host", "investors.test"); set_setting("manager_host", "managers.test")
        r = self.c.get("/managers/", headers={"Host": "investors.test"})
        self.assertEqual(r.status_code, 302); self.assertIn("managers.test/managers/", r.headers["Location"])
        r = self.c.get("/funds", headers={"Host": "managers.test"})
        self.assertEqual(r.status_code, 302); self.assertIn("investors.test/funds", r.headers["Location"])
        r = self.c.get("/", headers={"Host": "managers.test"})
        self.assertEqual(r.status_code, 302); self.assertIn("/managers/", r.headers["Location"])
        self.assertEqual(self.c.get("/login", headers={"Host": "managers.test"}).status_code, 200)

    def test_new_pages_render(self):
        for path in ("/support",):
            self.assertEqual(self.c.get(path).status_code, 200, path)
        self.login("admin@luminaz.test")
        for path in ("/admin/outreach", "/admin/support", "/admin/marketing", "/security"):
            self.assertEqual(self.c.get(path).status_code, 200, path)


class ReviewOf16October(Base):
    """One test per fix from the second Claude's review of 16 October 2026 (HANDOFF.md, changes 13 to 25)."""
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def _live_fund(self):
        with self.app.app_context():
            return get_db().execute("SELECT * FROM funds WHERE status = 'live'").fetchone()

    def _outbox(self, contains=None):
        import quopri
        folder = self.app.config["MAIL_OUTBOX"]
        texts = []
        for n in sorted(os.listdir(folder)):
            with open(os.path.join(folder, n), "rb") as fh:
                texts.append(quopri.decodestring(fh.read()).decode("utf-8"))
        return [t for t in texts if contains is None or contains in t]

    def test_13_failed_506d_blocks_publish_and_luminaz_can_suspend_and_remove(self):
        # Rule 4.6 and listing agreement 3.2 (review finding 1).
        self.login("admin@luminaz.test")
        with self.app.app_context():
            fid = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Blue Heron%'").fetchone()["id"]
            firm_id = get_db().execute("SELECT firm_id FROM funds WHERE id = ?", (fid,)).fetchone()["firm_id"]
        self.c.post("/admin/firms/%d" % firm_id, data={"action": "approve"})
        self.c.post("/admin/funds/%d" % fid, data={"action": "determination", "determination": "Passed - no disqualifying events found", "notes": "ok", "subjects": "Priya"})
        self.c.post("/admin/funds/%d" % fid, data={"action": "approve"})
        # A later failed determination closes the gate again, approval or not
        self.c.post("/admin/funds/%d" % fid, data={"action": "determination", "determination": "Failed - disqualifying event", "notes": "found", "subjects": "Priya"})
        self.assertIn(b"newest 506(d) determination is not a pass", self.c.get("/admin/funds/%d" % fid).data)
        self.c.get("/logout"); self.login("manager2@luminaz.test")
        r = self.c.post("/managers/funds/%d/publish" % fid, follow_redirects=True)
        self.assertIn(b"be published right now", r.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT status FROM funds WHERE id = ?", (fid,)).fetchone()["status"], "approved")
        # Luminaz can withdraw an approval that never went live
        self.c.get("/logout"); self.login("admin@luminaz.test")
        r = self.c.post("/admin/funds/%d" % fid, data={"action": "reject", "note": "Failed check"}, follow_redirects=True)
        self.assertIn(b"Fund rejected", r.data)
        # And suspend, then remove, a live one; the manager cannot lift a suspension
        live = self._live_fund()
        r = self.c.post("/admin/funds/%d" % live["id"], data={"action": "suspend", "note": "Pending a question"}, follow_redirects=True)
        self.assertIn(b"Suspended. The manager has been emailed", r.data)
        self.assertTrue(self._outbox("has suspended your listing"))
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT status FROM funds WHERE id = ?", (live["id"],)).fetchone()["status"], "paused")
            self.assertEqual(billing.open_pause(live["id"])["reason"], "admin")
        self.c.get("/logout"); self.login("manager@luminaz.test")
        r = self.c.post("/managers/funds/%d/resume" % live["id"], follow_redirects=True)
        self.assertIn(b"suspended by Luminaz", r.data)
        self.assertIn(b"Suspended by Luminaz on", self.c.get("/managers/funds/%d" % live["id"]).data)
        self.c.get("/logout"); self.login("investor@luminaz.test")
        self.assertIn(b"Paused, not taking requests", self.c.get("/funds").data)
        self.assertEqual(self.c.post("/funds/%d/request" % live["id"], data={"message": "x"}).status_code, 404)
        self.c.get("/logout"); self.login("admin@luminaz.test")
        r = self.c.post("/admin/funds/%d" % live["id"], data={"action": "resume"}, follow_redirects=True)
        self.assertIn(b"Resumed. The manager has been emailed", r.data)
        r = self.c.post("/admin/funds/%d" % live["id"], data={"action": "remove", "note": "Bye"}, follow_redirects=True)
        self.assertIn(b"Removed from the catalog", r.data)
        with self.app.app_context():
            f = get_db().execute("SELECT * FROM funds WHERE id = ?", (live["id"],)).fetchone()
            self.assertEqual(f["status"], "closed"); self.assertEqual(f["closed_at"], dt.date.today().isoformat())
            self.assertTrue(get_db().execute("SELECT 1 FROM audit WHERE action = 'fund_removed_by_luminaz'").fetchone())

    def test_14_attorney_lock_and_postal_address_hold_every_marketing_email(self):
        # Section 5 and rule 4.8 (review findings 2 and 13): education emails, outreach, the
        # catalog-open note and webinar emails all wait; account notices still go.
        from luminaz import jobs, mail
        with self.app.app_context(), self.app.test_request_context():
            db = get_db()
            db.execute("INSERT INTO calculator_leads(email, result, basis, created_at) VALUES ('held@x.com', 'accredited', 'income', ?)", (now_iso(),)); db.commit()
            set_setting("attorney_approved", "0")
            self.assertIn("attorney", mail.marketing_block())
            self.assertEqual(jobs.send_education(), 0)
            self.assertEqual(db.execute("SELECT sequence_step FROM calculator_leads WHERE email = 'held@x.com'").fetchone()[0], 0)   # the sequence waits
            self.assertEqual(mail.send("held@x.com", "s", "b", kind="marketing"), "held")
            self.assertTrue(mail.send("held@x.com", "s", "b").endswith(".txt"))                       # transactional still goes
            set_setting("attorney_approved", "1"); set_setting("postal_address", "Luminaz Technology LLC, Acworth, Georgia, USA")
            self.assertIn("postal address", mail.marketing_block())
            self.assertEqual(jobs.send_education(), 0)
            set_setting("postal_address", "PO Box 12, Acworth, GA 30101")
            self.assertIsNone(mail.marketing_block())
            self.assertEqual(jobs.send_education(), 3)
        # Outreach: the Send button is refused while held, and the draft keeps
        with self.app.app_context():
            set_setting("attorney_approved", "0")
            get_db().execute("INSERT INTO outreach(contact_name, fund_name, email, status, draft_subject, draft_body, created_at)"
                             " VALUES ('Sam', 'Peachtree', 'sam@x.com', 'drafted', 'Hi', 'Body', ?)", (now_iso(),)); get_db().commit()
            lead = get_db().execute("SELECT id FROM outreach").fetchone()["id"]
        self.login("admin@luminaz.test")
        r = self.c.post("/admin/outreach/%d" % lead, data={"action": "send", "draft_subject": "Hi", "draft_body": "Body"}, follow_redirects=True)
        self.assertIn(b"Not sent: held until the attorney approves", r.data)
        self.assertIn(b"Sending is held until the attorney approves", self.c.get("/admin/outreach").data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT status FROM outreach").fetchone()["status"], "drafted")
        self.assertFalse(self._outbox("Subject: Hi"))

    def test_16_the_founder_invested_notice_is_recorded_by_luminaz_not_the_manager(self):
        # Review finding 3: a manager marking a founder's request "invested" must not switch the notice on.
        live = self._live_fund()
        with self.app.app_context():
            db = get_db()
            admin = db.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()["id"]
            db.execute("INSERT INTO requests(fund_id, investor_id, message, status, created_at) VALUES (?, ?, '', 'new', ?)", (live["id"], admin, now_iso()))
            db.commit()
            rid = db.execute("SELECT id FROM requests WHERE investor_id = ?", (admin,)).fetchone()["id"]
        self.login("manager@luminaz.test")
        self.c.post("/managers/requests/%d/status" % rid, data={"status": "invested"})
        self.c.get("/logout"); self.login("investor@luminaz.test")
        self.assertNotIn(b"a member of Luminaz Technology has invested", self.c.get("/funds/%d" % live["id"]).data)
        self.c.get("/logout"); self.login("admin@luminaz.test")
        r = self.c.post("/admin/funds/%d" % live["id"], data={"action": "disclosure", "founder_invested": "1"}, follow_redirects=True)
        self.assertIn(b"the fund page shows the notice", r.data)
        self.c.get("/logout"); self.login("investor@luminaz.test")
        self.assertIn(b"a member of Luminaz Technology has invested", self.c.get("/funds/%d" % live["id"]).data)
        self.c.get("/logout"); self.login("admin@luminaz.test")
        self.c.post("/admin/funds/%d" % live["id"], data={"action": "disclosure", "founder_invested": "0"})
        self.c.get("/logout"); self.login("investor@luminaz.test")
        self.assertNotIn(b"a member of Luminaz Technology has invested", self.c.get("/funds/%d" % live["id"]).data)

    def test_17_a_stranger_cannot_undo_an_unsubscribe_and_a_pause_keeps_the_email_choice(self):
        # Rule 4.8 (review finding 4). Only a link sent to the mailbox lifts the do-not-email entry.
        from luminaz import jobs
        calc = {"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes", "assets": "0",
                "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "lee@x.com", "consent": "on"}
        self.c.post("/calculator", data=calc)
        with self.app.app_context():
            get_db().execute("INSERT INTO suppressions(email, reason, created_at) VALUES ('lee@x.com', 'unsubscribe link', ?)", (now_iso(),))
            get_db().execute("UPDATE calculator_leads SET unsubscribed = 1 WHERE email = 'lee@x.com'"); get_db().commit()
        before = len(self._outbox())
        self.c.post("/calculator", data=calc)                      # anyone could type this address in
        self.assertEqual(len(self._outbox()), before + 2)          # the result email and the confirmation, nothing else
        confirm = self._outbox("Confirm: start Luminaz emails again?")
        self.assertEqual(len(confirm), 1)
        with self.app.app_context(), self.app.test_request_context():
            self.assertTrue(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'lee@x.com'").fetchone())   # still off
            later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
            self.assertEqual(jobs.send_education(as_of=later), 2)                                             # the two accredited sample leads, not Lee
        import re
        link = re.search(r"http://localhost/resubscribe/\S+", confirm[0]).group(0)
        r = self.c.get(link)
        self.assertIn(b"back on the list", r.data)
        with self.app.app_context():
            self.assertFalse(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'lee@x.com'").fetchone())
            self.assertEqual(get_db().execute("SELECT unsubscribed FROM calculator_leads WHERE email = 'lee@x.com'").fetchone()[0], 0)
        self.assertIn(b"already used", self.c.get(link).data)      # once only
        # A paused investor who had emails off keeps them off when resuming
        self.login("investor@luminaz.test")
        self.c.post("/notifications", data={})                     # marketing unticked
        self.c.post("/notifications", data={"action": "pause"})
        r = self.c.post("/notifications", data={"action": "resume"}, follow_redirects=True)
        self.assertIn(b"educational emails stay off", r.data)
        with self.app.app_context():
            u = get_db().execute("SELECT marketing_opt_in, paused_at FROM users WHERE email = 'investor@luminaz.test'").fetchone()
            self.assertEqual((u["marketing_opt_in"], u["paused_at"]), (0, None))
            self.assertTrue(get_db().execute("SELECT 1 FROM suppressions WHERE email = 'investor@luminaz.test' AND reason = 'notifications page'").fetchone())

    def test_18_the_shortlist_only_takes_funds_investors_can_see(self):
        # Review finding 9: a draft or submitted fund's name must not leak through My shortlist.
        with self.app.app_context():
            hidden = get_db().execute("SELECT id FROM funds WHERE status = 'submitted'").fetchone()["id"]
        self.login("investor@luminaz.test")
        self.assertEqual(self.c.post("/funds/%d/mark/shortlist" % hidden).status_code, 404)
        self.assertNotIn(b"Blue Heron", self.c.get("/me").data)
        with self.app.app_context():
            self.assertFalse(get_db().execute("SELECT 1 FROM interest WHERE fund_id = ?", (hidden,)).fetchone())

    def test_19_five_wrong_codes_or_ten_minutes_end_the_second_step(self):
        # Review finding 10.
        from luminaz import twofactor
        self.login("admin@luminaz.test")
        self.c.post("/security", data={"action": "start"})
        with self.c.session_transaction() as sess:
            secret = sess["setup_secret"]
        self.c.post("/security", data={"action": "confirm", "code": twofactor.totp(secret)})
        self.c.get("/logout")
        self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW})
        for _ in range(4):
            self.assertIn(b"t match", self.c.post("/login/verify", data={"code": "000000"}, follow_redirects=True).data)
        r = self.c.post("/login/verify", data={"code": "000000"}, follow_redirects=True)
        self.assertIn(b"Too many wrong codes", r.data)
        r = self.c.post("/login/verify", data={"code": twofactor.totp(secret)}, follow_redirects=True)     # the right code no longer helps
        self.assertEqual(self.c.get("/admin/").status_code, 302)
        self.c.post("/login", data={"email": "admin@luminaz.test", "password": demo_data.PW})
        with self.c.session_transaction() as sess:
            sess["pending_2fa_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=11)).isoformat()
        r = self.c.post("/login/verify", data={"code": twofactor.totp(secret)}, follow_redirects=True)
        self.assertIn(b"took too long", r.data)
        self.assertEqual(self.c.get("/admin/").status_code, 302)

    def test_20_the_main_settings_form_cannot_blank_the_billing_dates(self):
        # Review finding 8: a Settings page opened before the daily job recorded the dates must not
        # write them back blank; the dates have their own form and must be real dates.
        self.login("admin@luminaz.test")
        with self.app.app_context():
            from luminaz.db import setting
            set_setting("catalog_opened_on", "2026-11-01"); set_setting("billing_starts_on", "2026-12-01")
        self.c.post("/admin/settings", data={"net_days": "15", "catalog_opened_on": "", "billing_starts_on": ""})
        with self.app.app_context():
            self.assertEqual((setting("catalog_opened_on"), setting("billing_starts_on"), setting("net_days")), ("2026-11-01", "2026-12-01", "15"))
        r = self.c.post("/admin/settings", data={"action": "dates", "catalog_opened_on": "soon", "billing_starts_on": ""}, follow_redirects=True)
        self.assertIn(b"must be a date like", r.data)
        r = self.c.post("/admin/settings", data={"action": "dates", "catalog_opened_on": "", "billing_starts_on": ""}, follow_redirects=True)
        self.assertIn(b"Dates saved", r.data)
        with self.app.app_context():
            self.assertEqual((setting("catalog_opened_on"), setting("billing_starts_on")), ("", ""))

    def test_21_closing_a_paused_listing_does_not_bill_the_closing_day(self):
        # Review finding 14 (the builder's part).
        live = self._live_fund()
        with self.app.app_context():
            first = dt.date.today().replace(day=1)
            self.assertTrue(billing.pause_fund(live["id"], 2, as_of=first))
            final = billing.close_fund(live["id"], 2, as_of=first + dt.timedelta(days=9))
            self.assertEqual(final, 0)
            self.assertFalse(get_db().execute("SELECT 1 FROM invoices WHERE fund_id = ? AND kind = 'final' AND amount > 0", (live["id"],)).fetchone())

    def test_22_reminder_day_source_case_and_recurring_revenue(self):
        # Review finding 15.
        from luminaz import webinars, metrics
        with self.app.app_context(), self.app.test_request_context():
            db = get_db()
            day = dt.date.today() + dt.timedelta(days=1)
            db.execute("INSERT INTO webinars(title, audience, starts_at, zoom_url, description, status, created_at) VALUES ('W', 'investors', ?, 'https://z', '', 'open', ?)",
                       (day.strftime("%Y-%m-%dT09:00"), now_iso()))
            wid = db.execute("SELECT id FROM webinars").fetchone()["id"]
            db.execute("INSERT INTO webinar_registrations(webinar_id, name, email, source, consent_at, consent_text, token, created_at)"
                       " VALUES (?, 'Pat', 'pat@x.com', 'LinkedIn', ?, 'c', 'wtok', ?)", (wid, now_iso(), now_iso()))
            db.commit()
            # The job runs at 6:15 am the day before a 9:00 am webinar: more than 26 hours ahead, still "tomorrow"
            self.assertEqual(webinars.send_reminders(as_of=dt.datetime.combine(dt.date.today(), dt.time(6, 15))), 1)
            self.assertEqual(webinars.send_reminders(as_of=dt.datetime.combine(dt.date.today(), dt.time(6, 15))), 0)
        self.assertTrue(self._outbox("Subject: Tomorrow: W"))
        # ?src=LinkedIn on a link and "LinkedIn" typed as spend land on one row
        self.c.get("/?src=LinkedIn")
        self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes", "assets": "0",
                                         "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no", "email": "li@x.com", "consent": "on"})
        self.login("admin@luminaz.test")
        self.c.post("/admin/metrics", data={"month": dt.date.today().strftime("%Y-%m"), "source": "LinkedIn", "amount": "100"})
        with self.app.app_context():
            rows = [r for r in metrics.roi() if r["source"] == "linkedin"]
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["spend"], rows[0]["accredited"], rows[0]["webinar"], rows[0]["cost_per_accredited"]), (100.0, 1, 1, 100.0))
            self.assertFalse(any(r["source"] == "LinkedIn" for r in metrics.roi()))
            # Monthly recurring is $0 until billing has started
            set_setting("billing_starts_on", (dt.date.today() + dt.timedelta(days=40)).isoformat())
            self.assertEqual(metrics.weekly(1)[-1]["mrr"], 0)
            set_setting("billing_starts_on", (dt.date.today() - dt.timedelta(days=40)).isoformat())
            self.assertEqual(metrics.weekly(1)[-1]["mrr"], 850)       # the sample fund's rate ($850 since 17 October 2026)
        r = self.c.get("/admin/metrics")
        self.assertIn(b"delete_spend", r.data)
        with self.app.app_context():
            sid = get_db().execute("SELECT id FROM marketing_spend").fetchone()["id"]
        self.c.post("/admin/metrics", data={"action": "delete_spend", "id": str(sid)})
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM marketing_spend").fetchone()[0], 0)

    def test_24_the_catalog_open_note_goes_once_after_the_catalog_opens(self):
        # Review finding 12: the pages promise one email the day the catalog opens; now it exists.
        from luminaz import jobs
        with self.app.app_context(), self.app.test_request_context():
            set_setting("catalog_opened_on", "")
            self.assertEqual(jobs.send_catalog_open_notices(), 0)                      # not open: nothing
            set_setting("catalog_opened_on", dt.date.today().isoformat())
            get_db().execute("INSERT INTO suppressions(email, reason, created_at) VALUES ('lead3@example.com', 'unsubscribe link', ?)", (now_iso(),)); get_db().commit()
            self.assertEqual(jobs.send_catalog_open_notices(), 1)                      # lead1 only: lead2 not accredited, lead3 unsubscribed
            self.assertEqual(jobs.send_catalog_open_notices(), 0)                      # once
        notes = self._outbox("Subject: The Luminaz catalog is open")
        self.assertEqual(len(notes), 1)
        self.assertIn("To: lead1@example.com", notes[0]); self.assertIn("/signup", notes[0]); self.assertIn("Unsubscribe:", notes[0])

    def test_25_a_principal_change_reopens_the_506d_check(self):
        # Review finding 7: a new covered person on an approved firm needs a new determination.
        self.login("manager@luminaz.test")
        self.c.post("/managers/firm", data={"name": "Ridgeline Capital", "website": "", "phone": "", "address": "", "state": "GA",
                                            "description": "Same", "principals": "Marcus Reyes\nNew Person"})
        self.c.get("/logout"); self.login("admin@luminaz.test")
        with self.app.app_context():
            firm_id = get_db().execute("SELECT id FROM firms WHERE name = 'Ridgeline Capital'").fetchone()["id"]
        r = self.c.post("/admin/firms/%d" % firm_id, data={"action": "approve"}, follow_redirects=True)
        self.assertIn(b"The principals changed. Run the 506(d) check again", r.data)
        live = self._live_fund()
        with self.app.app_context():
            self.assertFalse(billing.passed_506d(live["id"]))
        self.assertIn(b"newest 506(d) determination is not a pass", self.c.get("/admin/funds/%d" % live["id"]).data)
        self.c.post("/admin/funds/%d" % live["id"], data={"action": "determination", "determination": "Passed - no disqualifying events found", "notes": "rechecked", "subjects": "Marcus Reyes\nNew Person"})
        with self.app.app_context():
            self.assertTrue(billing.passed_506d(live["id"]))




class ChangesOf18October(Base):
    """One test per change of 18 October 2026 (HANDOFF.md, changes 26 and 27)."""
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def _fund(self, fid):
        with self.app.app_context():
            return get_db().execute("SELECT * FROM funds WHERE id = ?", (fid,)).fetchone()

    def _approved_fund(self, firm_id, name, target=5000000, minimum=50000):
        """A fund that has passed every gate but the manager's Publish click: agreement signed,
        506(d) passed, approved by Luminaz."""
        with self.app.app_context():
            db = get_db()
            owner = db.execute("SELECT owner_user_id FROM firms WHERE id = ?", (firm_id,)).fetchone()["owner_user_id"]
            fid = db.execute("INSERT INTO funds(firm_id, name, category, strategy, target_raise, min_investment, term_years, key_terms, status, submitted_at, approved_at, created_at)"
                             " VALUES (?, ?, 'Real estate', 'Test strategy.', ?, ?, 5, 'Test terms.', 'approved', ?, ?, ?)",
                             (firm_id, name, target, minimum, now_iso(), now_iso(), now_iso())).lastrowid
            db.execute("INSERT INTO agreements(firm_id, fund_id, signer_user_id, signer_name, signer_title, signed_at, ip_address, agreement_version, agreement_sha256)"
                       " VALUES (?, ?, ?, 'Signer', 'Manager', ?, '203.0.113.1', 'test', 'test')", (firm_id, fid, owner, now_iso()))
            db.execute("INSERT INTO bad_actor_checks(fund_id, subjects, determination, reviewer_id, notes, created_at, decided_at)"
                       " VALUES (?, 'Signer', 'Passed - no disqualifying events found', 1, 'test', ?, ?)", (fid, now_iso(), now_iso()))
            db.commit()
            return fid, owner

    def _firm_ids(self):
        with self.app.app_context():
            rows = get_db().execute("SELECT id, name FROM firms ORDER BY id").fetchall()
            return {r["name"]: r["id"] for r in rows}

    def test_26_850_a_month_and_the_first_founding_funds_list_free(self):
        # Diane, 17 October 2026: $850 a month; the first ten funds list free while the business
        # starts up. Listing 11 is the first that pays.
        from luminaz.db import setting
        firms = self._firm_ids()
        with self.app.app_context():
            self.assertEqual((setting("standard_rate"), setting("founding_rate"), setting("founding_free_funds"), setting("founding_fund_free_months")),
                             ("850", "850", "10", "0"))
            self.assertEqual(self._fund(1)["founding_fund"], 1)       # fund 1 of the sample data is a founding fund
        page = self.c.get("/managers/").data
        self.assertIn(b"The first 10 funds to go live list free for as long as they are listed; 9 of those places are left.", page)
        # Fund 2 goes live: founding, free for as long as it is listed, at the new rate
        fid, owner = self._approved_fund(firms["Ridgeline Capital"], "Ridgeline Fund II")
        with self.app.app_context():
            self.assertTrue(billing.publish_fund(fid, owner))
        f = self._fund(fid)
        self.assertEqual((f["fund_number"], f["founding_fund"], f["free_until"], f["monthly_rate"]), (2, 1, "9999-12-31", 850.0))
        self.login("manager@luminaz.test")
        self.assertIn(b"founding fund: free for as long as it is listed", self.c.get("/managers/funds/%d" % fid).data)
        # A finished month issues no invoice for it (the sample data started billing last month)
        with self.app.app_context():
            first_of_next = (dt.date.today().replace(day=1) + dt.timedelta(days=32)).replace(day=1)
            billing.run_billing(as_of=first_of_next + dt.timedelta(days=31))
            self.assertIsNone(get_db().execute("SELECT 1 FROM invoices WHERE fund_id = ?", (fid,)).fetchone())
        # With a time limit on the free period: free through N months after going live, then the rate
        with self.app.app_context():
            set_setting("founding_free_funds", "3"); set_setting("founding_fund_free_months", "6")
        fid3, owner = self._approved_fund(firms["Ridgeline Capital"], "Ridgeline Fund III")
        with self.app.app_context():
            self.assertTrue(billing.publish_fund(fid3, owner))
        f = self._fund(fid3)
        self.assertEqual((f["fund_number"], f["founding_fund"], f["free_until"]), (3, 1, billing.add_months(dt.date.today(), 6).isoformat()))
        self.assertIn(b"founding fund: free through %s, then $850" % f["free_until"].encode(), self.c.get("/managers/funds/%d" % fid3).data)
        # The places are used up: the next fund pays from the day it goes live, and the offer leaves the pages
        self.assertNotIn(b"funds to go live list free", self.c.get("/managers/").data)
        fid4, owner = self._approved_fund(firms["Ridgeline Capital"], "Ridgeline Fund IV")
        with self.app.app_context():
            self.assertTrue(billing.publish_fund(fid4, owner))
        f = self._fund(fid4)
        self.assertEqual((f["fund_number"], f["founding_fund"], f["free_until"], f["monthly_rate"]), (4, 0, dt.date.today().isoformat(), 850.0))
        self.assertIn(b"$850/month, billed at month end for live days", self.c.get("/managers/funds/%d" % fid4).data)
        # Settings shows both fields
        self.c.get("/logout"); self.login("admin@luminaz.test")
        page = self.c.get("/admin/settings").data
        self.assertIn(b'name="founding_free_funds"', page); self.assertIn(b'name="founding_fund_free_months"', page)

    def _outbox(self, contains=None):
        import quopri
        folder = self.app.config["MAIL_OUTBOX"]
        texts = []
        for n in sorted(os.listdir(folder)):
            with open(os.path.join(folder, n), "rb") as fh:
                texts.append(quopri.decodestring(fh.read()).decode("utf-8"))
        return [t for t in texts if contains is None or contains in t]

    def test_27_ten_listing_slots_and_the_line(self):
        # Diane, 17 October 2026: ten funds showing at a time, and fund managers line up to be next.
        from luminaz.db import setting
        from luminaz import jobs
        firms = self._firm_ids()
        with self.app.app_context():
            self.assertEqual(setting("live_listing_slots"), "10")
            self.assertEqual(billing.slot_summary(), {"cap": 10, "used": 1, "open": 9, "line": 0})
            set_setting("live_listing_slots", "1")                     # the sample fund fills the only slot
            self.assertEqual(billing.slots_open(), 0)
        # Blue Heron passes every gate; the manager's Publish click puts it in line instead of live
        self.login("admin@luminaz.test")
        with self.app.app_context():
            heron = get_db().execute("SELECT id FROM funds WHERE name LIKE 'Blue Heron%'").fetchone()["id"]
        self.c.post("/admin/firms/%d" % firms["Blue Heron Partners"], data={"action": "approve"})
        self.c.post("/admin/funds/%d" % heron, data={"action": "determination", "determination": "Passed - no disqualifying events found", "notes": "ok", "subjects": "Priya"})
        self.c.post("/admin/funds/%d" % heron, data={"action": "approve"})
        self.c.get("/logout"); self.login("manager2@luminaz.test")
        page = self.c.get("/managers/funds/%d" % heron).data
        self.assertIn(b"Every one of the 1 listing slots is taken right now", page); self.assertIn(b"Publish: join the line", page)
        r = self.c.post("/managers/funds/%d/publish" % heron, follow_redirects=True)
        self.assertIn(b"is in line at position 1 of 1", r.data)
        f = self._fund(heron)
        self.assertEqual(f["status"], "approved"); self.assertTrue(f["queued_at"]); self.assertIsNone(f["fund_number"])
        self.assertIn(b"In line, position 1 of 1", self.c.get("/managers/funds/%d" % heron).data)
        self.assertIn(b"in line, position 1 of 1", self.c.get("/managers/dashboard").data)
        self.assertIn(b"1 of 1 listing slots are taken, 1 in line", self.c.get("/managers/dashboard").data)
        self.assertIn(b"Right now: 0 open, 1 in line.", self.c.get("/managers/").data)
        self.c.post("/managers/funds/%d/publish" % heron, follow_redirects=True)          # a second click keeps the first place
        self.assertEqual(self._fund(heron)["queued_at"], f["queued_at"])
        # A second fund joins behind it
        second, owner1 = self._approved_fund(firms["Ridgeline Capital"], "Ridgeline Fund II")
        with self.app.app_context():
            self.assertEqual(billing.publish_fund(second, owner1), "queued")
            self.assertEqual([x["id"] for x in billing.the_line()], [heron, second])
            self.assertEqual(billing.line_position(second), 2)
        self.c.get("/logout"); self.login("admin@luminaz.test")
        page = self.c.get("/admin/").data
        self.assertIn(b"In line to go live (2)", page); self.assertIn(b"1 / 1", page)
        self.assertIn(b"position 1 of 2", self.c.get("/admin/funds/%d" % heron).data)
        # Blue Heron's gate closes (a failed determination); it keeps its place but is skipped when a slot opens
        self.c.post("/admin/funds/%d" % heron, data={"action": "determination", "determination": "Failed - disqualifying event", "notes": "found", "subjects": "Priya"})
        self.assertIn(b"skipped until one is recorded", self.c.get("/admin/").data)
        self.c.get("/logout"); self.login("manager@luminaz.test")
        self.c.post("/managers/funds/1/close", follow_redirects=True)                     # the sample fund is fully subscribed: a slot opens
        f = self._fund(second)
        self.assertEqual((f["status"], f["fund_number"], f["queued_at"], f["live_since"]), ("live", 2, None, dt.date.today().isoformat()))
        self.assertEqual(self._fund(heron)["status"], "approved"); self.assertTrue(self._fund(heron)["queued_at"])
        mails = self._outbox("Your Luminaz listing is live: Ridgeline Fund II")
        self.assertEqual(len(mails), 1); self.assertIn("To: manager@luminaz.test", mails[0]); self.assertIn("now live as fund 2", mails[0])
        self.assertIn("lists free as a founding fund", mails[0])                            # fund 2 of the first ten (change 26)
        with self.app.app_context():
            self.assertEqual(billing.slot_summary(), {"cap": 1, "used": 1, "open": 0, "line": 1})
        # A passing determination does not help while the slot is taken; a bigger slot count does
        self.c.get("/logout"); self.login("admin@luminaz.test")
        self.c.post("/admin/funds/%d" % heron, data={"action": "determination", "determination": "Passed - no disqualifying events found", "notes": "ok", "subjects": "Priya"})
        self.assertEqual(self._fund(heron)["status"], "approved")
        r = self.c.post("/admin/settings", data={"live_listing_slots": "2"}, follow_redirects=True)
        self.assertIn(b"1 listing in line went live under the new slot count", r.data)
        f = self._fund(heron)
        self.assertEqual((f["status"], f["fund_number"], f["queued_at"]), ("live", 3, None))
        self.assertEqual(len(self._outbox("Your Luminaz listing is live: Blue Heron Multifamily Fund II")), 1)
        with self.app.app_context():
            self.assertEqual(billing.slot_summary(), {"cap": 2, "used": 2, "open": 0, "line": 0})
        # Leaving the line, and rejoining at the back
        third, owner1 = self._approved_fund(firms["Ridgeline Capital"], "Ridgeline Fund III")
        fourth, owner1 = self._approved_fund(firms["Ridgeline Capital"], "Ridgeline Fund IV")
        self.c.get("/logout"); self.login("manager@luminaz.test")
        self.c.post("/managers/funds/%d/publish" % third); self.c.post("/managers/funds/%d/publish" % fourth)
        r = self.c.post("/managers/funds/%d/leave-line" % third, follow_redirects=True)
        self.assertIn(b"Taken out of the line", r.data)
        with self.app.app_context():
            self.assertEqual([x["id"] for x in billing.the_line()], [fourth])
        self.c.post("/managers/funds/%d/publish" % third)
        with self.app.app_context():
            self.assertEqual([x["id"] for x in billing.the_line()], [fourth, third])      # back of the line, not the front
        # The daily job is the safety net, and the evening report carries the numbers
        with self.app.app_context(), self.app.test_request_context():
            set_setting("live_listing_slots", "3")
            out = jobs.run_all(at=dt.datetime.combine(dt.date.today(), dt.time(19, 30)))
            self.assertEqual(out["line_filled"], 1)
            self.assertEqual((self._fund(fourth)["status"], self._fund(third)["status"]), ("live", "approved"))
        report = self._outbox("Subject: Luminaz today:")[-1]
        self.assertRegex(report, r"Listing slots taken\s+3   of 3 slots")
        self.assertRegex(report, r"Listing slots open\s+0")
        self.assertRegex(report, r"Funds in line to go live\s+1")
        # No limit at all: 0 slots means Publish goes live at once, and the line empties on the next check
        with self.app.app_context():
            set_setting("live_listing_slots", "0")
            self.assertIsNone(billing.slots_open())
            self.assertEqual(billing.fill_slots(), 1)
            self.assertEqual(self._fund(third)["status"], "live")
        # The catalog shows live funds in posting order only (rule 4.1): the line never reorders it
        self.login("investor@luminaz.test")
        page = self.c.get("/funds").data
        self.assertIn(b"Ridgeline Fund IV", page)
        self.assertLess(page.find(b"Ridgeline Fund II"), page.find(b"Blue Heron Multifamily Fund II"))
        self.assertLess(page.find(b"Blue Heron Multifamily Fund II"), page.find(b"Ridgeline Fund IV"))


class ChangesOf21October(Base):
    """One test per change of 21 October 2026 (HANDOFF.md, change 28)."""
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def test_28_posts_by_purpose_with_hooks_and_tagged_links_per_platform(self):
        from luminaz import marketing
        from luminaz.content.posts import MANAGER_POSTS, MANAGER_DISCLAIMER, DISCLAIMER
        # The manager bank keeps rules 4.2, 4.5 and 4.10: flat fee, self-attested, never "we find investors"
        self.assertEqual(len(MANAGER_POSTS), 13)      # + family offices and placement agents (change 32)
        link = "https://luminazforfundmanagers.com/managers/?src=linkedin"
        for p in MANAGER_POSTS:
            self.assertTrue(p["hook"] and len(p["hook"]) <= 120, p["topic"])
            self.assertLessEqual(len(p["short"].replace("{manager_url}", link)), 280, p["topic"])
            text = (p["hook"] + p["long"] + p["short"]).lower()
            for bad in ("guarantee", "% return", "outperform", "irr", "vetted", "verified investor", "find investors", "finds investors",
                        "deliver", "introduc", "match", "approved by", "success fee of", "per investor fee"):
                self.assertNotIn(bad, text, p["topic"])
        monday = dt.date(2026, 10, 5)
        with self.app.app_context(), self.app.test_request_context():
            set_setting("attorney_approved", "0")
            # Defaults: investors Mon/Wed/Fri, managers Tue, webinars Thu (none open) -> 8 drafts for two weeks
            self.assertEqual(marketing.plan_posts(today=monday), 8)
            rows = get_db().execute("SELECT purpose, slot, scheduled_for, hook, webinar_id FROM posts ORDER BY scheduled_for").fetchall()
            self.assertEqual([r["purpose"] for r in rows if r["slot"] == "Tuesday"], ["managers", "managers"])
            self.assertEqual(sum(1 for r in rows if r["purpose"] == "investors"), 6)
            self.assertTrue(all(r["hook"] for r in rows))                      # every draft opens with a hook
            self.assertFalse(any(r["purpose"] == "webinars" for r in rows))   # no open webinar, and the attorney switch is 0
            # A manager post renders for LinkedIn only (Settings), links to the manager page with a ?src= tag, opens with its hook
            mp = get_db().execute("SELECT * FROM posts WHERE purpose = 'managers' ORDER BY scheduled_for").fetchone()
            r = marketing.render(mp)
            self.assertEqual(list(r["platforms"]), ["linkedin"])
            self.assertIn("/managers/?src=linkedin&p=%d" % mp["id"], r["platforms"]["linkedin"]["link"])   # &p= names the post since change 33
            self.assertTrue(r["platforms"]["linkedin"]["text"].startswith(mp["hook"]))
            self.assertIn(MANAGER_DISCLAIMER, r["platforms"]["linkedin"]["text"]); self.assertNotIn(DISCLAIMER, r["platforms"]["linkedin"]["text"])
            self.assertIn("?src=social", r["long"])                           # the untagged copy keeps a generic tag
            # An investor post renders for LinkedIn, Facebook and X, each with its own tag; the X copy stays under 280
            ip = get_db().execute("SELECT * FROM posts WHERE purpose = 'investors' ORDER BY scheduled_for").fetchone()
            r = marketing.render(ip)
            self.assertEqual(list(r["platforms"]), ["linkedin", "facebook", "x"])
            self.assertIn("/calculator?src=facebook", r["platforms"]["facebook"]["text"])
            self.assertIn("/calculator?src=x", r["platforms"]["x"]["text"]); self.assertLessEqual(len(r["platforms"]["x"]["text"]), 280)
            self.assertIn(DISCLAIMER, r["platforms"]["linkedin"]["text"])
            # The webhook payload carries purpose, hook and the per-platform texts beside the old keys
            pl = marketing.payload(ip)
            for k in ("purpose", "hook", "platforms", "long", "short", "hashtags"):
                self.assertIn(k, pl)
            self.assertEqual(pl["purpose"], "investors"); self.assertEqual(set(pl["platforms"]), {"linkedin", "facebook", "x"})
            # Webinar posts: only once the attorney switch is on and an open webinar is within the lead days;
            # "announce" a week out, "last call" inside three days, one of each per webinar
            set_setting("attorney_approved", "1")
            get_db().execute("INSERT INTO webinars(title, audience, starts_at, status, created_at) VALUES (?, 'investors', ?, 'open', ?)",
                             ("How Private Funds Work", "2026-10-15T19:00", now_iso()))
            get_db().commit()
            self.assertEqual(marketing.plan_posts(today=monday), 2)
            wp = get_db().execute("SELECT * FROM posts WHERE purpose = 'webinars' ORDER BY scheduled_for").fetchall()
            self.assertEqual([(w["scheduled_for"], w["bank_index"]) for w in wp], [("2026-10-08", 0), ("2026-10-15", 1)])
            self.assertIn("How Private Funds Work", wp[0]["topic"]); self.assertTrue(wp[1]["topic"].startswith("Last call"))
            self.assertIn("Thursday 15 October 2026", wp[0]["long_body"])
            r = marketing.render(wp[0])
            self.assertEqual(list(r["platforms"]), ["linkedin", "facebook"])
            self.assertIn("/webinars/%d?src=linkedin" % wp[0]["webinar_id"], r["platforms"]["linkedin"]["text"])
            self.assertEqual(marketing.plan_posts(today=monday), 0)              # idempotent: no second announce, no second last call
            # Blank the manager days and the Tuesday drafts stop; investor days carry on
            set_setting("post_days_managers", "")
            later = dt.date(2026, 10, 19)
            self.assertEqual(marketing.plan_posts(today=later), 6)
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM posts WHERE purpose = 'managers' AND scheduled_for >= '2026-10-19'").fetchone()[0], 0)
        # The Posts page shows the purpose, the hook field, and saves an edited hook on approve
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/marketing")
        self.assertIn(b"to fund managers", r.data); self.assertIn(b'name="hook"', r.data); self.assertIn(b"?src=linkedin", r.data)
        r = self.c.post("/admin/marketing", data={"action": "approve", "post_id": mp["id"], "topic": mp["topic"], "hook": "A new first line.",
                                                 "long_body": mp["long_body"], "short_body": mp["short_body"], "tags": mp["tags"]}, follow_redirects=True)
        self.assertIn(b"Approved", r.data)
        with self.app.app_context(), self.app.test_request_context():
            p2 = get_db().execute("SELECT * FROM posts WHERE id = ?", (mp["id"],)).fetchone()
            self.assertEqual(p2["hook"], "A new first line."); self.assertEqual(p2["status"], "approved")
            self.assertTrue(marketing.render(p2)["platforms"]["linkedin"]["text"].startswith("A new first line.\n\n"))
            # The post-day email carries one block per platform
            before = len(os.listdir(self.app.config["MAIL_OUTBOX"]))
            self.assertEqual(marketing.publish_posts(today=dt.date(2026, 10, 6)), 1)
            files = sorted(os.listdir(self.app.config["MAIL_OUTBOX"]))
            self.assertEqual(len(files), before + 1)
            body = open(os.path.join(self.app.config["MAIL_OUTBOX"], files[-1])).read()
            self.assertIn("--- LinkedIn ---", body); self.assertIn("/managers/?src=3Dlinkedin", body); self.assertIn("to fund managers", body)   # quoted-printable: "=" is "=3D"

    def test_29_screen_reads_every_post_and_the_evening_report_counts_social(self):
        from luminaz import marketing, metrics
        from luminaz.admin import screen_text, POST_FLAGS
        # The screen knows the claims Luminaz must never make about itself (rule 4.10), on top of the listing flags
        self.assertEqual([l for l, _ in screen_text("Luminaz finds accredited investors for you.", extra=POST_FLAGS)], ["claims to find or deliver investors"])
        self.assertEqual([l for l, _ in screen_text("Our verified investors are waiting.", extra=POST_FLAGS)], ["says investors are verified (rule 4.5: self-attested)"])
        self.assertEqual(screen_text("Luminaz describes funds and never recommends them.", extra=POST_FLAGS), [])
        # No post in either bank trips it
        from luminaz.content.posts import POSTS, MANAGER_POSTS, WEBINAR_TEMPLATES
        for p in POSTS + MANAGER_POSTS + [t for aud in WEBINAR_TEMPLATES.values() for t in aud.values()]:
            self.assertEqual(screen_text(p.get("hook", "") + " " + p["long"] + " " + p["short"], extra=POST_FLAGS), [], p["topic"])
        monday = dt.date(2026, 10, 5)
        with self.app.app_context(), self.app.test_request_context():
            marketing.plan_posts(today=monday)
            pid = get_db().execute("SELECT id FROM posts WHERE purpose = 'managers' ORDER BY scheduled_for").fetchone()["id"]
            get_db().execute("UPDATE posts SET long_body = 'Luminaz delivers investors to your fund. ' || long_body WHERE id = ?", (pid,))
            get_db().commit()
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/marketing")
        self.assertIn(b"claims to find or deliver investors", r.data)            # flagged on the page, beside the draft
        self.assertIn(b"the screen catches words, not meaning", r.data)
        with self.app.app_context(), self.app.test_request_context():
            # Approve and send two posts, record a LinkedIn visitor, and the evening report counts them
            db = get_db()
            for row in db.execute("SELECT id FROM posts WHERE purpose IN ('investors', 'managers') ORDER BY scheduled_for LIMIT 2").fetchall():
                db.execute("UPDATE posts SET status = 'approved', approved_at = ?, approved_by = 1 WHERE id = ?", (now_iso(), row["id"]))
            db.commit()
            self.assertEqual(marketing.publish_posts(today=dt.date(2026, 10, 6)), 2)
            db.execute("INSERT INTO page_views(day, path, source, visitor, signed_in) VALUES (?, '/calculator', 'linkedin', 'v1', 0)", (dt.date.today().isoformat(),))
            db.commit()
            rows = dict(metrics.social(today=dt.date.today()))
            self.assertEqual(rows["Posts sent to investors"], 1); self.assertEqual(rows["Posts sent to fund managers"], 1)
            self.assertEqual(rows["Visitors from LinkedIn"], 1); self.assertEqual(rows["Visitors from Facebook"], 0)
            self.assertGreaterEqual(rows["Posts waiting for approval"], 0)
            subject, body = metrics.daily_text(at=dt.datetime.combine(dt.date.today(), dt.time(19, 0)))
            self.assertIn("SOCIAL, LAST 7 DAYS", body); self.assertIn("Posts sent to fund managers           1", body)
            self.assertIn("Visitors from LinkedIn                1", body)
            self.assertTrue(all(len(line) <= 76 for line in body.splitlines()), [l for l in body.splitlines() if len(l) > 76])


class ChangesOf22October(Base):
    """One test per change of 22 October 2026 (HANDOFF.md, changes 30 and 31)."""
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def test_30_the_app_runs_its_own_clock_once_a_day_and_once_an_evening(self):
        from luminaz import clock
        from luminaz.db import get_db
        # Off under tests: create_app started no thread, and start() refuses
        self.assertFalse(clock.enabled(self.app)); self.assertIsNone(clock.start(self.app))
        day1 = dt.datetime(2026, 10, 22, 5, 50)
        with self.app.app_context():
            outbox = self.app.config["MAIL_OUTBOX"]
            before = len(os.listdir(outbox)) if os.path.isdir(outbox) else 0
            self.assertEqual(clock.tick(self.app, at=day1), {"daily": 0, "report": 0})          # before 6 am: nothing due
            self.assertEqual(clock.tick(self.app, at=day1.replace(hour=6, minute=20)), {"daily": 1, "report": 0})
            self.assertEqual(clock.tick(self.app, at=day1.replace(hour=6, minute=25)), {"daily": 0, "report": 0})   # a second worker, five minutes later
            self.assertEqual(clock.tick(self.app, at=day1.replace(hour=12)), {"daily": 0, "report": 0})
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM audit WHERE action = 'daily_job'").fetchone()[0], 1)
            self.assertEqual(clock.tick(self.app, at=day1.replace(hour=19, minute=5)), {"daily": 0, "report": 1})   # 7 pm: the report, once
            self.assertEqual(clock.tick(self.app, at=day1.replace(hour=20)), {"daily": 0, "report": 0})
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM audit WHERE action = 'daily_summary'").fetchone()[0], 1)
            # The next day both run again; a changed hour is respected
            from luminaz.db import set_setting
            set_setting("daily_job_hour", "9"); get_db().commit()
            day2 = day1 + dt.timedelta(days=1)
            self.assertEqual(clock.tick(self.app, at=day2.replace(hour=7)), {"daily": 0, "report": 0})
            self.assertEqual(clock.tick(self.app, at=day2.replace(hour=9, minute=1)), {"daily": 1, "report": 0})
            self.assertEqual(clock.tick(self.app, at=day2.replace(hour=19, minute=30)), {"daily": 0, "report": 1})
            st = clock.status()
            self.assertEqual(st["daily"], "2026-10-23"); self.assertEqual(st["report"], "2026-10-23")
            # Switched off: the clock claims nothing and the report stays unsent
            set_setting("daily_summary", "0"); get_db().commit()
            day3 = day2 + dt.timedelta(days=1)
            self.assertEqual(clock.tick(self.app, at=day3.replace(hour=19, minute=30)), {"daily": 1, "report": 0})
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/settings")
        self.assertIn(b"daily_job_hour", r.data); self.assertIn(b"daily job last ran 2026-10-24", r.data)

    def test_31_nightly_backup_uploads_to_a_bucket_when_the_keys_exist(self):
        from luminaz import offsite, jobs
        # The signing matches the signature AWS publishes for its documented example request
        headers = {"host": "examplebucket.s3.amazonaws.com", "range": "bytes=0-9",
                   "x-amz-content-sha256": offsite.EMPTY_SHA256, "x-amz-date": "20130524T000000Z"}
        auth = offsite.authorization("GET", "/test.txt", {}, headers, offsite.EMPTY_SHA256, "AKIAIOSFODNN7EXAMPLE",
                                     "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1", dt.datetime(2013, 5, 24))
        self.assertTrue(auth.endswith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"), auth)
        # Without the host settings nothing is attempted
        for k in ("ENDPOINT", "BUCKET", "KEY", "SECRET", "REGION"):
            os.environ.pop("LUMINAZ_BACKUP_S3_" + k, None)
        self.assertFalse(offsite.enabled())
        with self.app.app_context():
            jobs.backup()
            self.assertEqual(self.app.config["LAST_OFFSITE"], "off")
        # With them, each nightly backup is PUT to the bucket and the oldest beyond 30 are deleted
        os.environ.update({"LUMINAZ_BACKUP_S3_ENDPOINT": "https://s3.us-west-004.backblazeb2.com", "LUMINAZ_BACKUP_S3_BUCKET": "luminaz-backups",
                           "LUMINAZ_BACKUP_S3_KEY": "key-id", "LUMINAZ_BACKUP_S3_SECRET": "not-a-real-secret", "LUMINAZ_BACKUP_S3_REGION": "us-west-004"})
        calls = []
        class FakeResp:
            def __init__(self, status, body): self.status, self._b = status, body
            def read(self): return self._b
            def __enter__(self): return self
            def __exit__(self, *a): return False
        old_keys = "".join("<Contents><Key>backups/luminaz-2026%02d01-000000.sqlite</Key></Contents>" % m for m in range(1, 10))   # 9 old copies
        listing = ('<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">' + old_keys +
                   "<Contents><Key>backups/luminaz-20261022-061500.sqlite</Key></Contents></ListBucketResult>").encode()
        def fake_open(req, timeout=0):
            calls.append((req.get_method(), req.full_url, dict(req.header_items())))
            return FakeResp(200, listing if req.get_method() == "GET" else b"")
        try:
            with self.app.app_context():
                dest = jobs.backup()
                self.assertEqual(self.app.config["LAST_OFFSITE"], "failed (URLError)")   # the real network is not reachable from the tests
                # Now through the fake network: upload, list, no deletes at 10 copies; then deletes with keep=5
                calls.clear()
                self.assertEqual(offsite.upload_backup([dest, None], keep=30, opener=fake_open), "uploaded 1")
                self.assertEqual([c[0] for c in calls], ["PUT", "GET"])
                method, url, hdrs = calls[0]
                self.assertTrue(url.startswith("https://s3.us-west-004.backblazeb2.com/luminaz-backups/backups/luminaz-"), url)
                self.assertTrue(hdrs["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=key-id/"), hdrs)
                self.assertIn("us-west-004/s3/aws4_request", hdrs["Authorization"])
                self.assertEqual(hdrs["X-amz-content-sha256"], hashlib.sha256(open(dest, "rb").read()).hexdigest())
                self.assertIn("list-type=2", calls[1][1]); self.assertIn("prefix=backups%2Fluminaz-", calls[1][1])
                calls.clear()
                self.assertEqual(offsite.upload_backup([dest], keep=5, opener=fake_open), "uploaded 1")
                deletes = [c for c in calls if c[0] == "DELETE"]
                self.assertEqual(len(deletes), 10)                    # 5 oldest copies, each with its documents zip
                self.assertTrue(deletes[0][1].endswith("/backups/luminaz-20260101-000000.sqlite"), deletes[0][1])
                self.assertTrue(deletes[1][1].endswith("/backups/luminaz-20260101-000000-documents.zip"))
                self.assertFalse(any("20261022" in c[1] for c in deletes))
        finally:
            for k in ("ENDPOINT", "BUCKET", "KEY", "SECRET", "REGION"):
                os.environ.pop("LUMINAZ_BACKUP_S3_" + k, None)


class ChangesOf23October(Base):
    """One test per change of 23 October 2026 (HANDOFF.md, change 33)."""
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()

    def test_33_every_post_link_names_its_post_and_the_communications_page_credits_it(self):
        from luminaz import marketing, metrics
        from luminaz.db import get_db
        ua = {"User-Agent": "Mozilla/5.0 (test) Chrome/120"}
        monday = dt.date(2026, 10, 5)
        with self.app.app_context(), self.app.test_request_context():
            marketing.plan_posts(today=monday)
            db = get_db()
            post = db.execute("SELECT * FROM posts WHERE purpose = 'investors' ORDER BY scheduled_for").fetchone()
            r = marketing.render(post)
            self.assertIn("?src=linkedin&p=%d" % post["id"], r["platforms"]["linkedin"]["link"])     # the link names the post
            self.assertIn("&p=%d" % post["id"], marketing.payload(post)["platforms"]["facebook"]["link"])
            db.execute("UPDATE posts SET status = 'approved', approved_at = ?, approved_by = 1 WHERE id = ?", (now_iso(), post["id"]))
            db.commit()
            self.assertEqual(marketing.publish_posts(today=monday), 1)
        # A visitor arrives through the post's LinkedIn link, reads two pages, completes the calculator
        pid = post["id"]
        self.c.get("/calculator?src=linkedin&p=%d" % pid, headers=ua)
        self.c.get("/learn", headers=ua)
        r = self.c.post("/calculator", data={"joint": "no", "income_last": "250000", "income_prior": "210000", "income_expect": "yes",
                                             "assets": "0", "home_value": "0", "liabilities": "0", "mortgage": "0", "license": "no",
                                             "email": "frompost@x.com", "consent": "on"}, headers=ua)
        self.assertIn(b"appear to qualify", r.data)
        with self.app.app_context():
            db = get_db()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM page_views WHERE campaign = ?", (str(pid),)).fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT campaign, source FROM calculator_leads WHERE email = 'frompost@x.com'").fetchone()[0], str(pid))
            # A second visitor (another browser, no tag) is not credited to the post
        self.app.test_client().get("/calculator", headers={"User-Agent": "Mozilla/5.0 (other) Chrome/120"})
        with self.app.app_context():
            c = metrics.communications(weeks=8, today=monday + dt.timedelta(days=3))
            row = next(x for x in c["posts"] if x["id"] == pid)
            self.assertEqual((row["visitors"], row["leads"], row["accredited"], row["webinar_signups"]), (1, 1, 1, 0))
            self.assertIn("linkedin 1", row["platforms"])
            self.assertEqual(c["by_purpose"]["investors"]["posts"], 1); self.assertEqual(c["by_purpose"]["investors"]["leads"], 1)
            self.assertIn("reply_rate", c["outreach"])
            # The Monday email carries the block
            subject, body = metrics.summary(today=monday + dt.timedelta(days=6))
            self.assertIn("COMMUNICATIONS, LAST WEEK", body); self.assertIn("1 visitors", body)
        # The page renders for an admin, with the post and the nav link
        self.login("admin@luminaz.test")
        r = self.c.get("/admin/communications")
        self.assertEqual(r.status_code, 200)
        self.assertIn(post["topic"].encode(), r.data); self.assertIn(b"By purpose", r.data); self.assertIn(b"Webinars", r.data)
        self.assertIn(b"/admin/communications", self.c.get("/admin/").data)
        self.assertEqual(self.c.get("/admin/communications?weeks=4").status_code, 200)




class ChangesOf26October(Base):
    """Change 34 (HANDOFF.md, 26 October 2026): what the investor is looking for, and Yes / Maybe / No."""
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            demo_data.load()
            db = get_db()
            firm = db.execute("SELECT firm_id FROM funds WHERE fund_number = 1").fetchone()["firm_id"]
            db.execute("INSERT INTO funds(fund_number, firm_id, name, category, strategy, target_raise, min_investment, term_years, status, live_since, free_until, monthly_rate, created_at)"
                       " VALUES (2, ?, 'Pine Ridge Farmland Fund', 'Agriculture and timber', 'Row-crop farmland.', 8000000, 25000, 10, 'live', ?, ?, 850, ?)",
                       (firm, dt.date.today().isoformat(), dt.date.today().isoformat(), now_iso()))
            db.commit()
            self.ag = db.execute("SELECT id FROM funds WHERE fund_number = 2").fetchone()["id"]
            self.pe = db.execute("SELECT id FROM funds WHERE fund_number = 1").fetchone()["id"]

    def test_34_criteria_filter_the_catalog_and_answers_hide_or_keep_funds(self):
        self.login("investor@luminaz.test")
        page = self.c.get("/funds").data
        self.assertIn(b"Answer three questions", page)
        self.assertIn(b"Ridgeline Acquisition Fund I", page); self.assertIn(b"Pine Ridge Farmland Fund", page)
        # Criteria: farmland only, up to $50,000, up to 12 years -> the $100,000-minimum fund drops out
        r = self.c.post("/criteria", data={"categories": ["Agriculture and timber"], "max_min": "$50,000", "max_term": "12"}, follow_redirects=True)
        self.assertIn(b"Showing funds that fit what you told us", r.data)
        self.assertIn(b"Pine Ridge Farmland Fund", r.data); self.assertNotIn(b"Ridgeline Acquisition Fund I", r.data)
        # A term limit shorter than the fund's leaves nothing, and the page says how to widen it
        self.c.post("/criteria", data={"categories": ["Agriculture and timber"], "max_min": "", "max_term": "5"})
        page = self.c.get("/funds").data
        self.assertNotIn(b"Pine Ridge Farmland Fund", page); self.assertIn(b"show all funds", page)
        # "Show all" and a typed filter set the criteria aside; posting order is kept
        page = self.c.get("/funds?all=1").data
        self.assertLess(page.find(b"Ridgeline Acquisition Fund I"), page.find(b"Pine Ridge Farmland Fund"))
        self.assertIn(b"Pine Ridge Farmland Fund", self.c.get("/funds?category=Agriculture+and+timber").data)
        # The criteria are the investor's own: a manager never sees them
        self.c.get("/logout"); self.login("manager@luminaz.test")
        self.assertNotIn(b"Agriculture and timber", self.c.get("/managers/funds/%d" % self.pe).data)
        self.c.get("/logout"); self.login("investor@luminaz.test")
        # Yes / Maybe / No: one answer per fund; Yes and Maybe are the shortlist and watch the manager counts
        self.c.post("/funds/%d/answer/yes" % self.ag)
        self.c.post("/funds/%d/answer/maybe" % self.ag)
        with self.app.app_context():
            kinds = [r["kind"] for r in get_db().execute("SELECT kind FROM interest WHERE investor_id = (SELECT id FROM users WHERE email = 'investor@luminaz.test') AND fund_id = ?", (self.ag,))]
            self.assertEqual(kinds, ["watch"])
        self.assertIn(b"Maybe \xe2\x9c\x93", self.c.get("/funds/%d" % self.ag).data)
        # No hides it from the catalog, says how many are hidden, and can be undone from My funds
        r = self.c.post("/funds/%d/answer/no" % self.ag, follow_redirects=True)
        page = self.c.get("/funds?all=1").data
        self.assertNotIn(b"Pine Ridge Farmland Fund", page); self.assertIn(b"1 fund you marked No is hidden", page)
        self.assertIn(b"Pine Ridge Farmland Fund", self.c.get("/funds?all=1&show_no=1").data)
        me = self.c.get("/me").data
        self.assertIn(b"My funds", me); self.assertIn(b"Undo", me); self.assertIn(b"Agriculture and timber", me)
        with self.app.app_context():
            self.assertFalse(get_db().execute("SELECT 1 FROM interest WHERE fund_id = ? AND investor_id = (SELECT id FROM users WHERE email = 'investor@luminaz.test')", (self.ag,)).fetchone())
        self.c.post("/funds/%d/answer/clear" % self.ag)
        self.assertIn(b"Pine Ridge Farmland Fund", self.c.get("/funds?all=1").data)
        # A No never reaches a manager: their page shows shortlist and watch counts only
        self.c.post("/funds/%d/answer/no" % self.pe)
        self.c.get("/logout"); self.login("manager@luminaz.test")
        page = self.c.get("/managers/funds/%d" % self.pe).data
        self.assertNotIn(b"Marked No", page)
        # Only listed funds can be answered, and nonsense answers are refused
        self.c.get("/logout"); self.login("investor@luminaz.test")
        with self.app.app_context():
            draft = get_db().execute("SELECT id FROM funds WHERE status = 'submitted'").fetchone()["id"]
        self.assertEqual(self.c.post("/funds/%d/answer/yes" % draft).status_code, 404)
        self.assertEqual(self.c.post("/funds/%d/answer/love" % self.ag).status_code, 400)


if __name__ == "__main__":
    unittest.main()
