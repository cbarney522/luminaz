# Luminaz handoff log

Newest entry first. The builder adds an entry after every change. The reviewer reads the top entry
first. Rules are in AGENTS.md.

---

## 26 October 2026 · Claude (builder) · Change 34: what the investor is looking for, and Yes / Maybe / No

### What happened

- Diane asked (26 October) to "finish coding Luminaz for accredited investors". The investor portal
  already ran end to end; the piece still missing from her asks was the 28 September intake: the
  investor says what they want, then answers Yes / Maybe / No on funds. Built inside the rulebook:
  the answers are the investor's own filters, funds stay in posting order (rule 4.1), and nothing
  sorts funds by how well they "match" (section 5, still on hold).
- **68 of 68 tests pass** (Python 3.10, Flask 3.1, Linux shell on Diane's laptop; 67 before).
  Backup before the first edit: `../backups/app_2026-10-26_before_change_34.zip`. New test
  `ChangesOf26October.test_34_...`. One older assertion that looked for the word "Shortlisted"
  in the catalog now looks for "Yes" (the label changed; the behaviour did not). A copy of the
  laptop's database upgraded cleanly (two new tables, rows kept).

### Change 34

- **Three questions** (`/criteria`, new template `investor/criteria.html`): kinds of fund (tick
  any; none = all), the most to put into one fund (compared with the fund's minimum), the longest
  money can be tied up in years (compared with the fund's term). Stored in the new table
  `investor_criteria`, one row per investor. Only the investor sees them; no manager page or email
  reads that table.
- **Catalog**: with criteria saved and no filter typed, the catalog starts filtered by them and
  says so, with "Show all funds" and "Change my answers". Typing a filter, or `?all=1`, sets them
  aside. A "Term up to" filter was added beside the other two. Without criteria, a card invites
  the three questions. Order is unchanged: date listed, then fund number.
- **Yes / Maybe / No** on every tile and fund page, one answer per fund, plus Clear. Yes is the
  existing shortlist and Maybe the existing watch, so managers keep seeing the same anonymous
  counts. No is the new table `fund_passes`: the fund is hidden from that investor's catalog
  ("1 fund you marked No is hidden · Show it"), listed on My funds with Undo, and never shown to a
  manager or counted anywhere else. The old shortlist/watch route still works.
- **My funds** (was "My shortlist" in the nav and heading): the investor's answers to the three
  questions, Yes and Maybe, and No with Undo.

### Not built, and why

- The September prototype's other questions (ten fund aspects rated must/nice/doesn't matter, a
  goal, an upfront-cost limit) need fund fields that do not exist and a scoring step that would be
  the "match" feed section 5 holds. The fact-sheet fields Diane asked for on 22 October (IRR,
  distribution frequency) wait on her no-projections rule and the attorney.

### Open decisions for Diane (not built)

| # | Question | What the code does meanwhile |
|---|---|---|
| 48 | Should a new investor be sent to the three questions right after confirming their email, instead of being invited on the Funds page? | Invited by a card on the Funds page. |
| 49 | Wording: every sentence on the three-question page, the catalog banners and the Yes/Maybe/No note is the builder's draft. | Live as drafted. |

### Still open from before

- 46 and 47, 29 to 45, 21 to 28, 13, 15, finding 1 of 9 October, the legal drafts' figures.

---

## 23 October 2026 · Claude (builder) · Change 33: communications analytics, per-post attribution

### What happened

- Diane asked (23 October) for analytics on social media, webinars and other communications, and
  assumed an agent is needed. The numbers were mostly there (Metrics page, sources by platform,
  spend and cost per lead, webinar registrations by source) but nothing credited a result to a
  particular post. This change adds that and gathers everything on one page.
- **67 of 67 tests pass** (Python 3.10, Flask 3.1, in the Linux shell on Diane's laptop; 66
  before). Backup before the first edit: `../backups/app_2026-10-23_before_change_33.zip`. The new
  test is `ChangesOf23October.test_33_...`. One assertion in test 28 that checked the end of a
  tagged link now checks for the `&p=` tag as well.

### Change 33: every post link names its post; the Communications page

- `marketing._tagged` adds `&p=<post id>` after `?src=<platform>` on every link a post carries.
  `remember_source` keeps `?p=` in the session like `?src=`; page views, calculator leads and
  webinar registrations record it in a new `campaign` column (three migrations). A second
  browser without the tag is never credited.
- `metrics.communications(weeks)`: per sent post, the visitors, calculator leads, appear-accredited
  leads and webinar sign-ups that arrived through its link, with the split by platform; totals by
  purpose; visitors and leads by platform in the window; per webinar: registrations by source,
  joins, show rate, attendance ticked, replays sent; the education series by step; manager
  outreach by status with sent, replied, reply rate, yes or listed.
- New admin page `/admin/communications` (nav link "Communications"), windows of 4, 8, 26 or 52
  weeks. The Monday numbers email gains a "COMMUNICATIONS, LAST WEEK" block: posts sent, the top
  three posts by visitors, webinars with sign-ups, outreach sent and replied.
- What is not here, and why: likes, impressions and followers live inside LinkedIn and Facebook
  and the app cannot see them without each platform's API (LinkedIn's is restricted; Facebook's
  needs an app review); the posting service's own analytics show them. Email opens and clicks
  arrive with the sending service (Postmark or Resend) once one is connected; the app records
  sends, not opens, and keeps no tracking pixel (rule 4.9).
- No agent was added. The "agent" the request implies is a weekly reading of these numbers with
  a recommendation ("keep what worked, drop what did not"); that is the Metrics Agent writing,
  which waits on the Anthropic key. Until then the page and the Monday block are the analytics.

### Open decisions for Diane (not built)

| # | Question | What the code does meanwhile |
|---|---|---|
| 46 | Whether the Monday email should rank posts by leads rather than visitors once leads exist. | Visitors first, then leads. |
| 47 | A posting-service analytics import (Buffer or Zapier can push likes and impressions to a webhook) so platform engagement sits beside the app's counts. Needs the account first. | Nothing. |

### Still open from before

- 29 to 45, 21 to 28, 13, 15, finding 1 of 9 October, the legal drafts' $400/forty figures.

---

## 22 October 2026 (evening) · Claude (builder) · Change 32: family offices in the post banks

### What happened

- Diane's decisions of 22 October: market to family offices as investors (small and virtual
  single-family offices are the segment); a family office that lists a fund of its own, or a
  placement agent bringing a client's fund, pays the same $850 a month per fund as any manager;
  "$850 is the monthly cost for each fund that uses my portal."
- **66 of 66 tests pass** (Python 3.10, Flask 3.1, in the Linux shell on Diane's laptop). Backup
  before the first edit: `../backups/app_2026-10-22_before_change_32.zip`. Three assertions that
  counted posts now count 40 investor posts, 40 Learn articles and 13 manager posts; nothing else
  in them changed. No new test: the change is content, checked by the existing bank tests (length,
  forbidden phrases, the language screen with the post flags).

### Change 32: four investor posts for family-office principals, one manager post

- `content/posts.py` POSTS gains a thirteenth week: "The family office nobody calls a family
  office", "What a $20 million family sees that a $2 million investor doesn't", "Why a flat-fee
  listing site has no reason to push a fund at you", "The questions a family office asks before it
  wires". They rotate into the investor days like the rest and appear as Learn articles (40 now).
  None describes the slot count or the line (the provisional patent is to be filed first).
- MANAGER_POSTS gains "Family offices with a fund of their own": same four gates, same flat fee,
  placement agents welcome on the same terms, the manager signs, Luminaz takes nothing from and
  pays nothing to the agent.
- Nothing about pricing changed in code: price is per fund and never asks who submitted it.

### Open decisions for Diane (not built)

| # | Question | What the code does meanwhile |
|---|---|---|
| 43 | The lead agent scores a fund with a placement agent 10 points down (it "needs distribution less"). If Series 82 firms are welcome customers, flip that to neutral. | Still −10. |
| 44 | The listing agreement should state that Luminaz accepts no compensation from any placement agent beyond the listing fee (attorney wording, rule 4.11). | Not in the draft. |
| 45 | A postal letter and a LinkedIn routine for small family offices, and a rewrite of the September family-office outreach plan for free-investor terms, are documents, not code; both wait for the attorney switch before anything is sent. | Nothing. |

### Still open from before

- 29 to 42, 21 to 28, 13, 15, finding 1 of 9 October, the legal drafts' $400/forty figures.

---

## 22 October 2026 · Claude (builder) · Changes 30 and 31: the app runs its own clock; nightly backups upload to a bucket

### What happened

- Diane asked (21 October) what deployment looks like. Two things would have failed on deployment
  day: on Render or Railway a scheduled job runs in its own container and cannot open the instance
  disk (finding 16), and the off-server backup copy (finding 12) expects a synced folder a cloud
  host does not have. These two changes remove both, so the host needs nothing scheduled and
  Cliff's part is creating accounts and typing settings.
- **66 of 66 tests pass** (Python 3.10, Flask 3.1, in the Linux shell on Diane's laptop; 64
  before). Backup before the first edit: `../backups/app_2026-10-22_before_change_30.zip`. The two
  new tests are in class `ChangesOf22October`, numbered like the changes. No new dependency.

### Change 30: the app's own clock (`luminaz/clock.py`)

- Every web worker starts one background thread at boot (`clock.start(app)` at the end of
  `create_app`). Every five minutes it asks the database what is due: the daily job once a day at
  or after `daily_job_hour` (new setting, 6 = 6 am on the server's clock; set TZ=America/New_York
  on the host), and the evening report every tick, which sends itself once at or after its own
  hour exactly as before (`jobs.daily_summary`).
- Two workers never run the same thing twice: `_claim` is an atomic compare-and-set on a settings
  row (`clock_daily_last`, `clock_report_last` hold the day); SQLite serialises the write, so one
  worker wins and the other skips. A failed tick is logged and the clock carries on.
- Off under tests, and off when `LUMINAZ_CLOCK=0`; `manage.py` sets that for itself because its
  commands run the jobs directly. The "Run daily tasks" button and the manage.py commands are
  unchanged and remain the fallback. The Settings page shows the clock's state and when each
  thing last ran, beside the new hour field.
- DEPLOY.md section 5 should now read: nothing to schedule on Render or Railway; on a VPS the
  crontab lines are optional. (Not rewritten here; the one-line note was added at the top of that
  section.)

### Change 31: off-server backup to an S3-compatible bucket (`luminaz/offsite.py`)

- After each nightly backup, the database copy and the documents zip are uploaded by a signed
  HTTPS PUT (AWS Signature Version 4, standard library only) to a bucket at Backblaze B2,
  Cloudflare R2 or Amazon S3; the newest 30 copies are kept in the bucket and older ones deleted.
  The signing was checked against the example signature AWS publishes for its documented request
  (the test holds that vector).
- Switched on by five host settings typed by Cliff, never stored in code or the database (rule
  4.12): `LUMINAZ_BACKUP_S3_ENDPOINT`, `_BUCKET`, `_KEY`, `_SECRET`, `_REGION`. Until the first four
  exist the daily job reports `offsite: off`. The bucket must be private.
- The daily job's summary gains `offsite` ("off", "uploaded 2", or a failure word); a failure is
  logged and never stops the rest of the job. The synced-folder setting still works where a folder
  exists (a laptop or a VPS).

### Open decisions for Diane (not built)

| # | Question | What the code does meanwhile |
|---|---|---|
| 41 | The host. Render with the clock (nothing to schedule, Cliff creates accounts) or a VPS (crontab as DEPLOY.md says, Cliff maintains a Linux box). The builder recommends Render. | Works on both. |
| 42 | The daily job's hour (6 am) and whether the local laptop copy should also run the clock when the app is open (it does now; `LUMINAZ_CLOCK=0` in run.bat would stop it). | 6 am; the laptop runs it. |

### Still open from before

- 29 to 40 (18 and 21 October entries), 21 to 28 (16 October), 13, 15, finding 1 of 9 October, the
  legal drafts' $400/forty figures (attorney).

### What could not be tested here

- A real bucket: the network from the test shell is blocked, so the upload was tested against a
  fake server that records the requests and the documented AWS signature, not against Backblaze or
  Cloudflare. **First real run must be checked by Cliff**: after the daily job runs on the host,
  the bucket's file list should show `backups/luminaz-<date>.sqlite` and `-documents.zip`.
- The clock thread under gunicorn with two workers on a real host (the claim logic is tested; the
  threads are not). `run.bat`, the SMTP path, the Bookings link, the webhook.

---

## 21 October 2026 · Claude (builder) · Changes 28 and 29: posts by purpose, hooks, tagged links, the screen on every post, social in the evening report

### What happened

- Diane asked (21 October) for a social media plan that is implemented, organised by purpose
  (find accredited investors, recruit fund managers, fill webinars) with webinars included. These
  two changes are the part that lives in the app. The plan itself is the Claude artifact "Luminaz
  AI Org Chart and Social Strategy" (kept per her standing ask).
- **64 of 64 tests pass** (Python 3.10, Flask 3.1, in the Linux shell on Diane's laptop; 62
  before). Backup before the first edit: `../backups/app_2026-10-21_before_change_28.zip`. The two
  new tests are in class `ChangesOf21October`, numbered like the changes. Three older assertions
  that counted "6 posts" now count 8 (a manager Tuesday joined the three investor days); nothing
  else in them changed.
- The upgrade of the laptop's own database was tried on a copy: the three new columns appear, the
  seven new settings get their starting values, the $850 rate is untouched. The real
  `instance/` folder was not touched.

### Change 28: posts by purpose, with a hook line and one tagged link per platform

- `posts` gains `purpose` (investors / managers / webinars), `hook` (the first line a reader sees,
  editable on the Posts page) and `webinar_id`. Each purpose has its own weekdays and platforms on
  Settings: `post_days_investors` (Monday, Wednesday, Friday, as before), `post_days_managers`
  (Tuesday), `post_days_webinars` (Thursday), `post_platforms_*` (investors: linkedin, facebook, x;
  managers: linkedin; webinars: linkedin, facebook), `post_webinar_lead_days` (14). Blank a days
  field and that purpose stops. A weekday used by two purposes goes to the first in the order
  investors, managers, webinars.
- `content/posts.py`: twelve posts to fund managers (`MANAGER_POSTS`, each with an explicit hook;
  cost of raising capital, the four gates, the ten slots and the line, the founding ten, no
  projections, "you verify, not Luminaz", who sees what, pause, what a month costs, Form D, why a
  flat fee, who Luminaz is for), a manager disclaimer, and webinar templates for both audiences
  ("announce" until three days before, then "last call"; one of each per webinar). Investor posts
  get their hook from the first sentence (`hook_for`). Every line was written against rules 4.2,
  4.5 and 4.10 and the test checks the bank for the forbidden phrases.
- A webinar post is drafted only for an open webinar inside the lead window, and only while
  `attorney_approved` is 1: the sign-up page it links to is locked until then (section 5). Nothing
  about the lock on marketing email changed; posts were always approve-before-send (rule 4.7).
- `marketing.render(post)` now returns one text per platform, each with the link tagged
  `?src=linkedin`, `?src=facebook` or `?src=x` (investor posts link to the calculator, manager
  posts to the manager landing page, webinar posts to the sign-up page), so the Metrics page and
  the ROI table can tell the platforms apart. The webhook payload keeps its old keys and adds
  `purpose`, `hook` and `platforms`; the post-day email carries one block per platform.
- Posts page: the schedule per purpose at the top, a purpose tag on every post, the hook field, and
  the tagged links shown under each draft. Settings page: a "Marketing posts by purpose" block.

### Change 29: the marketing-language screen reads every post; the evening report counts social

- `admin.screen_text(text, extra=POST_FLAGS)`: five new patterns for claims Luminaz must never make
  about itself (rule 4.10 and 4.5: "we find/deliver/match investors", "verified investors",
  "vetted", an endorsed or recommended fund, a top or featured fund). The listing screen is
  unchanged; the new patterns apply to posts. Every draft on the Posts page shows its flags beside
  the text, the same way the fund page does. It flags; it does not block (the same rule as for
  listings: a founder reads and decides).
- Evening report: a "SOCIAL, LAST 7 DAYS" block (`metrics.social`): posts sent to investors, to fund
  managers, about webinars, posts waiting for approval, and visitors who arrived from LinkedIn,
  Facebook and X. The 76-character line rule holds.

### Open decisions for Diane (not built)

| # | Question | What the code does meanwhile |
|---|---|---|
| 36 | A manager post every Tuesday is now drafted by default (one a week, approve-before-send). Keep, change the day, or blank it until the thirty calls have happened? | Drafted on Tuesdays; `post_days_managers` on Settings. |
| 37 | The manager post "The first ten funds list free" says the free period is granted "while Luminaz starts up" and does not say it never ends. Decision 29 (an end to the founding free period) should be made before this post is approved. | Drafted like the others; approve-before-send. |
| 38 | Which platforms per purpose. Starting values: investors LinkedIn, Facebook, X; managers LinkedIn only; webinars LinkedIn and Facebook. | On Settings. |
| 39 | The hooks on the 36 investor posts are the first sentence of each post. Explicit hooks (shorter, sharper) are wording: the agent can write them once the Anthropic key exists, or Diane edits them on the page. | First sentence. |
| 40 | Facebook posts carry the same text as LinkedIn. A shorter Facebook variant is wording. | Same text, Facebook link tag. |

### Still open from before

- 29 to 35 (18 October entry), 21 to 28 (16 October), 13, 15, finding 1 of 9 October, the legal
  drafts' $400/forty figures (attorney), the off-server backup folder (Cliff).

### What could not be tested here

- `run.bat` and the Windows paths; the SMTP path; a real webhook (Zapier, Make or Buffer: none is
  set); the Bookings link.

---

## 18 October 2026 · Claude (builder) · Changes 26 and 27: $850, the founding ten, ten listing slots and the line

### What happened

- Diane's decisions of 17 October 2026, made in chat while the laptop was not linked: the price is
  **$850 a month** per live listing (up from $750); **the first ten funds list free** "as we are
  starting up the business"; **ten funds show at a time**, and fund managers **line up to be the
  next fund**. She had a working model of the slots and the line to play with first (the Claude
  artifact "Luminaz Listing Slots"); this entry is the code.
- **62 of 62 tests pass** (Python 3.10, Flask 3.1, run in the Linux shell on Diane's laptop; 60
  before). Backup before the first edit: `../backups/app_2026-10-18_before_change_26.zip`. The two
  new tests are in class `ChangesOf18October`, numbered like the changes.
- The upgrade of a database made by the previous code was tried on a copy: the two new columns
  appear, the three new settings get their starting values, and an existing database **keeps the
  rate it already holds ($750)**; the Settings page is where that number is changed. No database
  exists on the laptop yet (the app has never been run there), so the first run starts at $850.
- Thirteen existing tests that asserted the price ($750, in invoices, receipts, pages and the
  support assistant's answer) now assert $850. Nothing else in them changed.

### Change 26: $850 a month, and the first ten funds list free

- `founding_rate` and `standard_rate` start at 850 (`db.py`). The outreach draft's fallback rate
  is $850 too (the real one is read from Settings, as before).
- New settings: `founding_free_funds` (10) and `founding_fund_free_months` (0). When a fund goes
  live, `billing.publish_fund` gives it its fund number as before and then marks it a **founding
  fund** (`funds.founding_fund = 1`) if the number is within the first `founding_free_funds`. A
  founding fund's `free_until` is 9999-12-31 (free for as long as it is listed) when the months
  setting is 0, or the live date plus that many months. Nothing else in billing changed: the
  month-end invoice already skips days before `free_until`, so a founding fund is never invoiced,
  and the "monthly recurring" figures already exclude funds still inside a free period. The
  onboarding fee (off by default) is not charged to a founding fund either.
- Counted by fund number, so a removed founding fund does not hand its place to the next one:
  listing 11 is the first that pays, whatever happened to listings 1 to 10.
- Pages: the manager landing page, dashboard and signing page say how many founding places are
  left (`billing.founding_free_text()`, one sentence, available to every template); the manager's
  fund page says "founding fund: free for as long as it is listed" (or "free through <date>, then
  $850/month"); Settings has the two fields with a note that a fund's status is fixed the day it
  goes live.

### Change 27: ten listing slots and the line

- New setting `live_listing_slots` (10; 0 = no limit). Live and paused listings count against it
  (a paused listing stays visible, Diane's rule of 14 October, so it keeps its slot; see decision
  30). New column `funds.queued_at`.
- **Joining the line.** The manager's Publish click (gate 4) does what it did when a slot is open.
  When every slot is taken, `publish_fund` returns `"queued"`: the fund stays `approved`, its
  `queued_at` is stamped at full precision (two clicks in the same second keep their order), and
  the page says "in line at position k of n". A second click keeps the first place. The line is
  `billing.the_line()`: approved funds with a `queued_at`, ordered by that stamp and nothing else.
  No page, field or setting moves a fund up the line (rule 4.1): the review desk shows the order
  and has no controls on it.
- **A slot opens** when a listing closes (manager) or is removed (Luminaz): `close_fund` ends by
  calling `billing.fill_slots()`, which publishes funds from the line, first click first, while
  slots are open and their gates still pass (status approved and the newest 506(d) a pass; the
  signed agreement and Luminaz's approval were checked before the fund could be approved at all).
  A fund whose 506(d) gate closed since keeps its place and is skipped; the review desk marks it
  "not a pass: skipped until one is recorded". The manager of each fund that goes live is emailed
  ("Your Luminaz listing is live", transactional, with the fund number and whether it lists free as
  a founding fund). `fill_slots()` also runs after a 506(d) determination is recorded, after
  Settings are saved (a larger slot count lets funds in), and at the start of every daily job
  (`line_filled` in the job's summary) as the safety net.
- **Leaving the line.** "Leave the line" on the manager's fund page clears `queued_at`; the fund
  stays approved, and the next Publish click rejoins at the back.
- Pages: the manager's fund page shows the position, the date they joined, and that nothing is
  charged while they wait; the dashboard tags each fund in line and prints "x of 10 listing slots
  are taken, n in line"; the landing page has one bullet on the rule; the review desk has a slot
  stat and an "In line to go live" table; the admin fund page shows the position; Settings has the
  field with a note that lowering the number never removes a live listing and that "Live funds
  needed" (the catalog gate) must stay at or under it. The evening report gains three lines:
  slots taken, slots open, funds in line.
- Rule 4.2 check: nothing about the line touches money. Waiting is free; billing for a fund that
  goes live from the line starts that day exactly as for any other publish.

### Open decisions for Diane (not built)

| # | Question | What the code does meanwhile |
|---|---|---|
| 29 | The founding ten's free period has no end. A founding fund that takes two years to raise holds a slot for two years and never pays, and a free listing with no end is hard to take back later; the builder recommended an end (for example 6 months after going live). | `founding_fund_free_months` = 0: free for as long as listed. Any number ends it. The listing agreement draft does not mention founding funds at all (rule 4.11: attorney). |
| 30 | Pause and the slot. As built, a paused listing keeps its slot (it stays visible, 14 October rule), so a long pause blocks the line while paying nothing. Alternative: a pause frees the slot and the fund returns at the front of the line when it unpauses. | Paused listings count against the slot count. |
| 31 | A maximum time in a slot while others are waiting (say 12 months), after which a fund rotates to the back of the line. | No maximum. A fund keeps its slot while it is live or paused. |
| 32 | A fund in line goes live by itself when a slot opens (the manager already clicked Publish). The alternative from the working model: a 72-hour offer the manager must accept, else the slot passes to the next fund and they keep second place. | Automatic. The manager can leave the line at any time. |
| 33 | The catalog gate's "Live funds needed" (10) equals the slot count (10): the catalog cannot open until every slot is taken. Keep, or set the gate lower? | Both numbers on Settings; the Settings note says the gate must stay at or under the slot count. |
| 34 | Wording. Every sentence added to the pages in these two changes is the builder's draft: the founding-funds bullet and sentence, the slot bullet, the "in line" messages and the go-live email. | Live as drafted until Diane changes them. |
| 35 | If a database that already has live funds is ever upgraded, those funds are not marked founding (the mark is set the day a fund goes live) even when their number is within the first ten. No such database exists today. | Nothing; flagged in case a test database is kept and reused. |

### Still open from before

- 21 to 28 (16 October entry), 13 (win-back credit never applied), 15 (Founding Manager is only
  a rate lock), the legal drafts' $400/forty figures (attorney; now also the $850 and the founding
  ten), the off-server backup folder (Cliff), finding 1 of 9 October (documents required before
  approval: the checklist shows them, approval does not insist).

### What could not be tested here

- `run.bat` and the Windows paths (the tests ran in the Linux shell on the laptop, not in
  Windows); the SMTP path (no provider configured); the Bookings link.

---

## 16 October 2026 · Claude (builder) · Changes 13 to 25, from the first Claude-reviews-Claude pass

### What happened

- Diane decided that the reviewer is now a second Claude ("I want Claude to work with Claude"),
  not Gemini. AGENTS.md section 3, CLAUDE.md, the new REVIEWER.md and GEMINI.md say so. The
  reviewer is a separate session that has seen none of the build work; it read the rulebook, the
  top of this file and every source file, ran the tests, and reported fifteen findings in the
  review-pack format. Its first line: the 14 October changes mostly work, but the catalog gate
  could be stalled by one manager or wiped by one Settings save, and the attorney lock stopped
  only webinar emails.
- **60 of 60 tests pass** (Python 3.13, Flask 3.1, in the builder's workspace; 49 before). Backup
  before the first edit: `../backups/app_2026-10-16_before_change_13.zip`. The eleven new tests
  are in class `ReviewOf16October`, one per change, numbered like the changes below.
- The upgrade of an existing database was tried on a copy made by the previous code: the two
  rebuilt tables keep their rows and the new columns appear. (Found on the way: the schema
  comments held semicolons, which would have broken the first rebuild of `fund_pauses`; fixed.)

### What was fixed (the reviewer's numbering in brackets)

- **Change 13 [1] Rule 4.6 and listing agreement 3.2.** `billing.publish_fund` refuses unless the
  *newest* 506(d) determination starts with "Passed"; a "Failed" recorded after approval closes
  the gate again. The review desk can now **Suspend** a live listing (visible as paused, no
  requests, suspended days not charged, only Luminaz lifts it), **Lift** it, **Remove** it from
  the catalog (same money rules as a manager's close), and **Withdraw** an approval that never
  went live. The manager is emailed each time with the note typed on the page. The investor's
  paused notice no longer says "the manager has paused"; it says the listing is paused.
- **Change 14 [2, 13] Section 5 and CAN-SPAM.** One check, `mail.marketing_block()`, now holds
  *every* marketing email while `attorney_approved` is 0 or while the postal address in Settings
  has no street or box number: the education series waits where it is, outreach's Send button
  says why and keeps the draft, webinar reminders and replays wait, the new catalog-open note
  waits. Transactional email (confirmations, receipts, requests, the suspension notices) is not
  affected. The postal address got a field on Settings (it was command line only).
- **Change 15 [5] Rule 4.7.** Outreach follow-ups no longer send themselves. After
  `outreach_followup_days` the daily job writes the follow-up onto the lead (status
  `followup_drafted`, column `followup_body`) and puts it at the top of the outreach desk, where
  "Approve and send the follow-up" sends it.
- **Change 16 [3] The "a member of Luminaz has invested" notice** is recorded on the review desk
  (`funds.founder_invested_at`, a Disclosure card on the fund page), never derived from a manager's
  pipeline. The wording of the notice is unchanged.
- **Change 17 [4] Rule 4.8.** Typing an address into the calculator or a webinar form no longer
  lifts a do-not-email entry. If the address is on the list, one transactional email goes to that
  mailbox with a single-use link (`/resubscribe/<token>`, 7 days) that lifts it; the result email
  or the join link still goes. An investor's Pause no longer rewrites their email choice: Resume
  removes the pause entry only, so someone who had emails off keeps them off.
- **Change 18 [9]** The shortlist and watch buttons accept only live, paused or closed funds, and
  My shortlist lists only those; a draft or submitted fund's name cannot be read by number.
- **Change 19 [10]** The two-step sign-in allows five wrong codes and ten minutes, then throws the
  half-finished sign-in away.
- **Change 20 [8]** The catalog gate: the list it demands is capped (`investor_list_cap`, 5,000,
  Diane's number) so a $1 minimum cannot stall it; the two dates that start billing have their
  own form on Settings with a confirmation, so the main form (opened before the daily job wrote
  them) can never blank them, and a mistyped date is refused; the sign-up switch now affects
  sign-up only: "open" lets testers in without opening the catalog or starting anyone's billing,
  "closed" shuts sign-up even after the catalog opened. `billing_status()` says "people on the
  list who appear accredited (self-reported)" instead of "accredited investors" (rule 4.5).
- **Change 21 [14, builder's part]** A listing closed while paused stays paused through its
  closing day, so that day is not billed. Two messages that said a paused listing "returns to the
  catalog" now say it takes requests again (it never left the catalog).
- **Change 22 [15]** Webinar reminders go the calendar day before, whatever hour the job runs;
  the `?src=` word is stored in lowercase everywhere so `?src=LinkedIn` and spend typed "LinkedIn"
  meet on one ROI row; "Monthly recurring now" is $0 until billing has started; spend entries can
  be deleted.
- **Change 23 [12, builder's part]** Sentences that promised what the code does not do:
  "Nothing you enter is stored" became "the dollar figures you enter are never stored" (the email
  and the result are kept, rule 4.9); two pages still said the catalog opens at ten live funds;
  the manager page said every change is reviewed (routine changes to the target and minimum go
  live at once, by Diane's earlier rule) and now says so; the support assistant said every listed
  fund has filed a Form D (nothing checks that); a post said "no list exists"; the two webinar
  pages said "we'll email you when one is scheduled" (no code does that) and now say the page is
  where to look; education email 6 promised an alert about funds in a category you looked at
  (section 5, match-based) and now promises only the catalog-open note.
- **Change 24 [12]** The catalog-open note now exists: `jobs.send_catalog_open_notices()` sends one
  email per accredited calculator lead the first mornings after the catalog opens (500 a day),
  behind the same marketing lock, never twice (`calculator_leads.catalog_notified_at`).
- **Change 25 [7]** A fund can be approved only once its firm profile is approved (investors see
  the firm's name and description on the listing). When Luminaz approves a firm change that alters
  the principals, every approved or listed fund of that firm gets an open 506(d) check: the
  publish gate closes on an approved fund, and the fund page shows "the newest determination is
  not a pass" until a person records a new one.

### Open decisions for Diane (not built; the reviewer's numbering in brackets)

| # | Question | What the code does meanwhile |
|---|---|---|
| 21 [6] | The manager page prints how many self-reported accredited people the catalog waits for, next to cost comparisons. The reviewer reads that as close to "pricing tied to a raise" and "delivering investors" (section 5, rule 4.10) and wants the attorney to see the rule and the wording before any manager does. | Wording changed to "people who appear accredited (self-reported)". Added to the attorney packet as question 30. |
| 22 [3] | Whether to show the "a Luminaz founder has invested" notice at all, and in what words. | Shown only when Luminaz records it; the sentence is unchanged. Attorney packet question 31. |
| 23 [11] | The promotion kit tells a new manager to send investors the fund link "this week", but sign-up stays closed until the catalog opens, so they hit "Not open yet". Let people arriving from a manager's link sign up (does that count as opening?), or hide the kit until the catalog opens? | Unchanged. |
| 24 [14] | A paused listing stays visible for free for as long as it is paused, firm website link included. Cap how long, charge after N paused days, or hide the website while paused? | Unchanged: visible, free, indefinitely. |
| 25 [12] | The privacy draft says calculator results are kept "until you unsubscribe"; unsubscribing keeps the row (the do-not-email list needs the address). Delete or blank the row on unsubscribe, or the attorney changes the sentence? | Unchanged; legal drafts are not edited by the builder (rule 4.11). |
| 26 [2] | Whether outreach to fund managers should wait for the attorney too. Section 5 says "any marketing email"; the code now holds outreach as well. | Held with everything else until `attorney_approved` = 1. |
| 27 [8] | The cap on the list the catalog gate demands: 5,000 is the builder's placeholder. | `investor_list_cap` on Settings. |
| 28 [12] | "We'll email you when a webinar is scheduled" was removed from two pages because nothing sends it. Build it (one email per lead when a webinar opens, behind the lock), or leave the pages as they are? | Pages say the webinar page is where to look. |

### Still open from before

- 13 (win-back credit never applied), 15 (Founding Manager is only a rate lock), the legal drafts'
  $400/forty figures (attorney), the off-server backup folder (Cliff), finding 1 of 9 October
  (documents required before approval: the checklist shows them, approval does not insist).

### What could not be tested here

- `run.bat` and the Windows paths; the SMTP path (no provider configured); the Bookings link.

---

## 14 October 2026, night · Claude (builder) · Changes 9 to 12

### State of the code

- **49 of 49 tests pass** (Python 3.10, Flask 3.1, in the builder's workspace). No `instance` folder
  is left behind by a test run. Backup before the first edit:
  `../backups/app_2026-10-14_before_change_9.zip`.
- Diane answered the questions from the evening entry (decisions 17 to 20) and asked for the coding
  to be finished "so we can test the entire apps". Screens captured again from this code.

### Change 9: Diane's answers

- **Free until the catalog opens, and the 5x rule.** Billing no longer waits for a fixed number of
  investor accounts. Every listing is free until the investor catalog opens, and billing starts the
  first of the following month. The catalog opens when `investor_signup_threshold` funds are live
  (10) AND the accredited list (calculator leads who appear accredited and have not unsubscribed)
  is `investor_multiple` (5) times what the largest listed fund needs to sell out, target raise
  divided by minimum investment. Diane's words: "fund managers must always have a lot of accredited
  investors they can find." The daily job records `catalog_opened_on` and `billing_starts_on`; the
  sign-up switch (open / closed) still overrides; both dates can be typed on Settings.
  `billing.readiness()` shows the four numbers on the admin Billing page and in plain words on the
  manager landing page, dashboard and sign page. Investor sign-up opens with the catalog.
  **Flagged to Diane in chat:** at 5x, a $15M fund with a $50,000 minimum needs a 1,500-person list
  before anyone is billed, so the first revenue month could be a year or more away; 2x, or a cap on
  the list, is one number on Settings.
- **Paused listings stay visible.** A manager's pause now keeps the fund in the catalog with a
  "Paused, not taking requests" label; the fund page explains it and hides the request form; the
  request route refuses (404); shortlist and watch still work; paused days are still not charged.
  Non-payment pauses look the same to investors.
- **Investor pause** stays as built (emails off, shortlist hidden, account kept). **Catalog** stays
  option B (no preference given).
- Tests rewritten for the new gate (1,250 leads needed for the sample fund; the open switch; billing
  the month after) and the visible pause.
- Also in chat: Diane's target of **50 funds raising at a time** ($37,500 a month at $750).

### Change 10: findings 8 and 12, before real users

- **Password-reset links expire** after `reset_link_minutes` (60) and work once; they use their own
  column, so a pending email confirmation is no longer overwritten by a reset request.
- **Admins must have two-step sign-in.** With `require_admin_2fa` = 1 (the starting value), an admin
  without it is sent to the Security page before any admin page opens. Managers and investors are
  not affected. For a test machine: `py -3 manage.py setting require_admin_2fa 0` (new command,
  because that switch lives on a page the rule blocks). The tests run with it off except the one
  that checks it.
- **Off-server backup copy.** `backup_copy_dir` in Settings: the nightly backup and the documents
  zip are also copied there (a OneDrive, Dropbox or mounted folder). A missing folder never breaks
  the backup itself. Cliff names the folder; nothing else is needed. With these two the privacy
  policy's promises are true.

### Change 11: the webinar sign-up page

- New `luminaz/webinars.py`: `/webinars` (open webinars), `/webinars/<id>` (sign-up: name, email,
  consent recorded with text and time, the `?src=` tag kept), confirmation email with a personal
  join link, `/webinars/<id>/join/<token>` (records the click, sends them to Zoom), reminder the
  day before and replay afterwards through the daily job (marketing emails with the unsubscribe
  link and postal footer), and `/admin/webinars` to create a webinar (draft, open, done), paste the
  Zoom and replay links, see registrations by source and tick who attended. The unsubscribe link
  works for webinar tokens too.
- **The lock.** Settings `attorney_approved` (0): the public pages say "coming soon", sign-ups are
  refused, reminders and replays do not send. Admins can preview the pages. This is Diane's rule
  from Launch Tasks in code; flip it to 1 only when the attorney has approved the terms and
  privacy policy.
- Test: the whole flow, locked then approved, including the once-only reminder and replay.

### Change 12: marketing spend and cost per accredited lead

- Metrics page: a form to record spend by month and source word, and a table of spend, calculator
  leads, accredited leads, webinar sign-ups and cost per accredited lead per source and month
  (Diane: "track ROI for marketing"). Nothing is computed from investments.

### Not tested

`run.bat` on Windows; real email; the Dockerfile and Procfile; the catalog and sign-up pages on a
real phone; a real Zoom link.

### Wording and design I chose, for Diane to approve

The readiness sentence on the manager pages; the paused label and notice; every webinar page and
email; the Metrics spend table; the first-sign-in two-step requirement message.

### Still open

| # | Open | What the code does now |
|---|---|---|
| 17 | Is 5x the right multiple? | 5 on Settings; chat note explains the timing it implies |
| 21 | Listing agreement, manager terms and attorney scope page say $400 and forty firms | Unchanged (rule 4.11) |
| 13 | Win-back credit promised in outreach, never applied | Unchanged |
| 15 | Founding Manager is only a rate lock | Pages say so |
| 1 | Approve a fund with no documents uploaded? | Allowed (Diane's call) |
| 22 | Which account the off-server backup folder syncs to | Cliff |

### Next, in this order unless Diane says otherwise

1. Cliff runs it on the laptop; both founders click through all three portals and the webinar page.
2. Gemini review of this pack.
3. Finding 1 if Diane says yes; the two manager-side FAQ pages; the LinkedIn starter pack (not code).

---

## 14 October 2026, evening · Claude (builder) · Changes 5 to 8

### State of the code

- **44 of 44 tests pass** (Python 3.10 with Flask 3.1, in the builder's Linux workspace). A test run
  leaves no `instance` folder behind. The app had still never been started on Diane's laptop.
- Backup before the first edit: `../backups/app_2026-10-14_before_change_5.zip`.
- Screens captured from this code with sample data: investor home, manager landing, About, the
  catalog at laptop and wide widths, the investor pause page, the manager dashboard and invoices.

### Change 5: $750, free until enough investors, billed at month end, pause, receipts

- **Decided by Diane, 14 October:** $750 a month per fund ("fund managers tend to pay a 1 percent
  finder's fee; I am going very cheap"). Fund managers are free until there are enough accredited
  investors. She is paid by the end of the month, prorated when a manager was not subscribed the
  whole month or paused. Managers can pause.
- **Price.** Starting values in `db.py`: founding and standard rate 750, free months 0 and 0,
  Founding Manager cap 25 (rate lock only). An existing database changes on the Settings page.
- **Free until enough investors.** New setting `free_until_investors` (250 as the starting value:
  the number Diane has not set yet, so it is on the Settings page). While confirmed investor
  accounts are below it, no fund is billed. The first daily run after the number is reached writes
  `billing_starts_on`, the first day of the following month, and billing begins there. 0 means no
  waiting period. `billing.billing_status()` puts the state in plain words on the manager landing
  page, dashboard, sign page and admin Billing page.
- **Billed in arrears.** `run_billing` no longer invoices the month ahead. On every run, each
  finished month without an invoice gets one for the days the listing was live that month,
  rate x live days / days in the month, issued the day the job runs, due net_days later. Missed
  runs catch up by themselves. The new `live_days` column shows on invoices and the Billing page.
- **Pause.** New table `fund_pauses` (fund, reason manager / nonpayment, paused day, resumed day).
  A manager pauses from the fund page: the listing leaves the catalog (status `paused`) and those
  days are not charged; Resume brings it back. A non-payment pause is the same status, recorded with
  its own reason, and the manager's Resume button refuses it until the invoice is paid. A pause
  covers the day it starts; the resume day counts as live.
- **Close.** The closing month is invoiced at once (`final`) for the days through the closing day,
  minus paused days. No more prepayment credits, because nothing is prepaid.
- **Receipts.** `record_payment` emails the firm's owner a receipt with the amount, method and
  invoice link.
- **Wording updated** to match: dashboard, sign page, fund page, invoices, invoice, Billing page,
  the support assistant's answers (plus a new pause answer), the outreach email, the Settings page.
- **Tests.** Five tests encoded the rules Diane replaced and were rewritten rather than deleted:
  the $350 test, the invoice-in-advance test, the two close tests, and the approve test's rate.
  New: month-end amounts and live days; close through the closing day and nothing after; manager
  pause by date and by button with the catalog hiding the fund; non-payment pause refusing the
  manager's Resume; free until enough investors then billing the month after; the receipt email.
- **Sample data** now backdates one fund so that exactly one invoice (last month, $750, all days)
  exists after `manage.py demo`.

### Change 6: landing pages, header, footer, About, eight categories

- **Asked for by Diane:** a landing page for fund managers and one for investors, headers and
  footers, an About page, the disclosure that Luminaz does not accredit anyone (the fund manager
  confirms accredited status), and legal language that the portal does not sell funds. Wording was
  drafted on the "Luminaz Landing Pages" artifact and is hers to approve.
- `base.html`: the header reads "Luminaz for Fund Managers" on manager pages, with its own menu
  (How it works, Pricing, What we check, About, Investor site). Every page ends with the same
  footer: the two-paragraph disclosure (not a broker-dealer, investment adviser or finder; does not
  offer, sell or recommend securities; no fee tied to any investment; does not verify or certify
  accredited status, the manager does under Rule 506(c); listings in the order received; private
  funds involve risk), links, "We do not sell your data", the company, the postal address from
  Settings and the support address.
- `/` rewritten: hero, three cards, the categories as the first step, five how-it-works steps.
  `/managers/` rewritten: hero, cost-of-raising table, the Pricing card from Settings, what you
  get, what we check, five listing steps, categories, and a "Book a 15-minute call" button that
  appears when the new setting `booking_url` is filled in. New `/about` page (in the sitemap).
- **"Vetted" is gone** from the home page, the site description, the structured data and the
  manager page (finding 2 closed); every page now says what is checked.
- **Eight categories** in `db.py` with a one-line note each: the four, plus Energy (asked for),
  Infrastructure, Agriculture and timber, Specialty. The listing form, the catalog filter, the home
  page and the education email all read the list. Hedge funds, REITs and Reg A stay out.
- **Founder signature** starting value now says 18 years (finding 5). An existing database keeps
  what it has until Settings is changed.
- **Test:** disclosure, About link and the eight categories on both landing pages and About; the
  manager header; $750 and the free-until wording; the booking button only when the link is set;
  no "vetted"; no licensing claims on About.

### Change 7: catalog tiles, investor pause, the verification article

- **Catalog.** Option B from the "Luminaz Catalog Rows" page: tiles, as many per row as fit, ten on
  a wide monitor, about seven on a laptop, two on a phone. Posting order reads left to right then
  down. The strategy text moved off the tile and stays on the fund page. The catalog page is the
  only full-width page (`main.wide`). Diane had not chosen A, B or C when she said "start coding";
  B is the builder's pick and can be swapped.
- **Investor pause.** On the Notifications page an investor can pause: no educational emails
  (opt-in off, address suppressed), shortlist and requests hidden on /me, account and password kept;
  Resume reverses all of it. New column `users.paused_at`. Diane said "investors can pause as
  needed"; this is the builder's reading, to confirm.
- **Verification article.** `luminaz/content/verification.py`, at
  `/learn/how-accredited-status-is-verified`, first on the Learn page and in the sitemap: the
  manager verifies, what they may ask for, which letters count, the three-month clock, the March
  2025 minimum-investment route, and four commonly used services with the three conditions Diane
  agreed to (no endorsement, no fee from them, no letter through Luminaz). Every fund page carries a
  "Before you request materials" note that links to it. Attorney packet question 29 covers it.

### Change 8: finding 7, sign-in can no longer bounce to another website

- `auth.safe_next()` accepts only a path on this site: `//example.com`, `https://...` and
  `/\example.com` are refused after a correct password, in both the password step and the
  two-step page. Test added.

### Not tested

`run.bat` on Windows; real email delivery (receipts and all other mail go to `instance\outbox`);
the Dockerfile and Procfile; the catalog on a real phone.

### Wording and design I chose, for Diane to approve

Everything on the two landing pages, the About page and the footer; the "Free until the investor
catalog opens to enough investors" line; the pause wording on both sides; the verification article;
the eight category notes; the catalog tile layout (option B).

### Decisions still open (the code took the plainest reading)

| # | Open | What the code does now |
|---|---|---|
| 17 | How many investor accounts is "enough"? | 250 in Settings; the daily job starts billing the month after it is reached |
| 18 | Does a manager pause hide the listing and stop the days? | Yes, both; resume with one click |
| 19 | What does an investor pause mean? | Emails off, shortlist hidden, account kept |
| 20 | Catalog A, B or C? | B |
| 21 | The listing agreement and manager terms still say $400 and forty firms; the attorney scope page says $400 | Unchanged (rule 4.11); the sign page's terms box says $750 above the old text |
| 13 | The win-back credit is still promised in outreach and never applied | Unchanged |
| 15 | With one rate, Founding Manager status is only a rate lock | Pages now say exactly that |

### Also today, outside the code

- "Luminaz Launch Skills" (the skills needed to launch both platforms, with owners),
  "Luminaz Catalog Rows" and "Luminaz Landing Pages" were published as pages for Diane and Cliff.

### Next, in this order unless Diane says otherwise

1. Diane's answers to 17 to 20 above; swap the catalog layout if she picks A or C.
2. Finding 8 (password-reset links never expire) and finding 12 (admins must have two-step sign-in
   on; off-site backup copy), before real users.
3. The webinar sign-up page.
4. Marketing spend per channel on the Metrics page, for the cost per accredited lead Diane asked for.
5. Finding 1 (documents required before approval), if Diane says yes.

---

## 9 October 2026, late afternoon · Claude (builder) · Change 4

### State of the code

- **36 of 36 tests pass** (Python 3.10 and 3.13 with Flask 3.1). A test run still leaves no
  `instance` folder behind.

### Change 4: the evening report, at 7 pm

- **Asked for by Diane:** "a daily report at 7pm daily regarding how Luminaz is doing." She also
  asked how the daily checklist of things to do gets created. Until now nothing created one.
- **Before:** the daily job emailed yesterday's numbers whenever it happened to run (change 2
  called it the morning email).
- **Now:** `jobs.daily_summary()` sends once a day, at or after the hour in the new setting
  `daily_summary_hour` (19, with a field on the Settings page). The email, written by
  `metrics.daily_text()`, has three parts:
  - today's numbers so far, each beside yesterday's whole-day figure;
  - **Waiting on you**, from the new `metrics.waiting()`: funds, firm profiles and listing changes
    to review, posts to approve, outreach emails drafted and not sent, support questions that need
    a person, invoices past due. Empty queues are left out. This is the daily checklist, and
    nothing in it is typed in;
  - the totals so far.
- **What triggers it:** the new command `manage.py report`, meant to be scheduled every hour. It
  is silent before the hour and silent once it has sent. `manage.py report now` skips the wait and
  still sends only once a day. The daily job and the "Run daily tasks" button stay as a fallback:
  they send the report if they run at or after the hour. `jobs.run_all()` takes an optional `at`
  so that this can be tested.
- **Why every hour:** hosts schedule in UTC, which ignores daylight saving time. An hourly run
  plus the `TZ` setting keeps the report at 7 pm Eastern all year (DEPLOY.md section 5).
- **Tests:** the morning-email test became `test_daily_numbers_table_and_evening_report`, and
  `test_evening_report_lists_what_is_waiting_on_the_founders` is new. Three deliberate breaks each
  made a test fail: removing the wait for the hour, dropping the fund queue from the list, and
  swapping today's column with yesterday's.
- **Checked by hand, not by the test suite:** `manage.py report` and `manage.py report now`, in a
  throwaway copy. A test cannot import `manage.py` without creating the real `instance` folder.
- **Not tested:** a real schedule on a real host, and real email delivery.
- **Wording I chose, for Diane to approve:** the email's headings ("TODAY SO FAR", "WAITING ON
  YOU", "TOTALS SO FAR"), its labels and subject line, and the two labels on the Settings page.
- **Limits to know:**
  - The report cannot arrive until the site is on a host with an email provider. On Diane's laptop
    it is written to `instance\outbox` as a text file, like every other email.
  - It reports only what the app records. It knows nothing about the attorney, the reviewer, or
    decisions that live in documents.
  - Whatever happens after 7 pm shows in the next evening's "yesterday, whole day" column.
  - If the hourly command and the daily job both run in the same moment after 7 pm, both could
    send. The worst case is a second copy of the email to the founders.
- **Also changed:** `README.txt` (the test count said 30; it is 36), `DEPLOY.md` section 5,
  `AGENTS.md` (two lines of the code map, and a new step 7 in the builder's routine), and one
  sentence on the Metrics page.
- **Undo:** `../backups/app_2026-10-09_before_change_4.zip`.

### New finding

| # | Finding | Who decides |
|---|---|---|
| 16 | **The scheduled jobs may not be able to run on Render or Railway the way DEPLOY.md describes.** There, a "cron job" is usually a separate container, and I believe it cannot open the web app's `instance` disk, where the database is. Not checked against either host's current documentation. If it is true, `manage.py daily` and `manage.py report` need another trigger there: a timer inside the web app, or a protected address that the host's scheduler calls. A plain server with `crontab` is not affected. | Cliff chooses the host, then the builder adapts |

### Also today, outside the code

- Diane asked whether she may buy a list of accredited investors without being a fund manager.
  Answered in chat: buying is open to anyone, and the rules are about how a list is used. It is
  now question 28 in the attorney packet. Rule 4.8 ("No purchased lists") is unchanged, because
  she has not decided.
- A scheduled Claude task now sends Diane a short status report each evening at about 7 pm: what
  changed, what is waiting on her and on others, and a checklist for the next day. It runs in the
  cloud, so it cannot open this folder. It is written from "Where Luminaz stands" in the research
  file, which is why step 7 was added to the builder's routine in AGENTS.md. It changes nothing,
  and it is separate from the app's own report above, which needs a host.
- Diane wants Gemini working on the code today. The review pack is rebuilt with this change. She
  carries it to Gemini, because the builder cannot reach the reviewer.

### Next, in this order unless Diane says otherwise

1. Whatever the first Gemini review turns up that holds.
2. Finding 7 (sign-in redirect), with a test.
3. The webinar sign-up page, when Diane says go.
4. Finding 1 (documents required before approval), if Diane says yes.

---

## 9 October 2026, afternoon · Claude (builder) · Changes 2 and 3

### State of the code

- **35 of 35 tests pass** (Python 3.10 and 3.13 with Flask 3.1). A test run still leaves no
  `instance` folder behind.
- Every screen on the tour page was captured again from this code.

### Change 2: daily numbers, and counting home-screen installs

- **Asked for by Diane:** "see how many people downloaded the app and track how many subscribe,"
  as a daily update.
- **What is true today:** Luminaz is a website. Nobody downloads it. A person can add it to a
  phone's home screen, but the manifest had no icons, so browsers did not offer that.
- **Built:**
  - `metrics.daily()` and a "Day by day, last 14 days" table at the top of `/admin/metrics`:
    visitors, email sign-ups, how many appear accredited, investor accounts, fund managers, funds
    published, requests, added to a home screen, opened from a home screen.
  - `jobs.daily_summary()`: a morning email with yesterday's numbers, sent by the daily job to
    `post_notify_email` (else `support_email`). New setting `daily_summary`, on by default, with a
    field on the Settings page.
  - Home-screen counting: new table `app_events`, `POST /app-event` (`investor.py`),
    `static/app.js`, icons in the manifest and an Apple touch icon in `base.html`. One row per
    visitor per day, no cookie. `/app-event` is exempt from the two-domain redirect.
  - `luminaz/visitors.py`: the no-cookie visitor hash, now shared by the page counter and the new
    counter (`count_view` in `__init__.py` uses it; its behaviour is unchanged).
  - `db.day_bounds()`: a day means a day on the computer's clock. DEPLOY.md section 5 now says to
    set `TZ` on the host.
- **Tests:** three new ones. The time-zone test is skipped on Windows, because a test cannot
  switch the clock's zone there.
- **Checked in a real browser (Chromium):** the manifest has no installability errors; an install
  event makes one row; opening in home-screen mode, Android style and iPhone style, makes one row
  per visitor per day; the site sets no cookie.
- **Not tested:** a real phone. An iPhone does not report an install, only an open. Anyone can
  post to `/app-event`, so a script could push the counts up (one row per visitor per day limits
  it). Good enough for a prototype; look again before the numbers matter.
- **Wording and design I chose, for Diane to approve:** the table headings, the email text, the
  manifest description ("Where accredited investors discover private funds. Free for
  investors."), and the icon (the half-sun from the page header).

### Change 3: the price

- **Decided by Diane:** $350 a month per fund for everyone, cancel any time. The first 25 fund
  managers get three months free.
- **Starting values** in `db.py`: `founding_manager_cap` 25, `founding_rate` 350, `standard_rate`
  350 (they were 40, 400 and 750). These seed a new database only. An existing one is changed on
  the Settings page.
- **No price is typed into a page or an email any more.** The support answer, the outreach email,
  the manager landing page description and the win-back credit labels read Settings through the
  new `billing.quoted_rate()`. All of them now say "fund managers," which is what the code counts.
  This closes finding 4 below.
- **Tests:** three expected amounts changed from 400 to 350, and one new test. It fails if a price
  is typed back into the support answer.
- **Not changed:** one free month for later firms, the Founding rate lock, and the onboarding fee
  and closed-listing tier (both still switched off).
- **Legal drafts not touched (AGENTS.md rule 4.11).** Section 4.2 of `listing_agreement.md` still
  says "first forty firms" and "$400 per month," in both `luminaz/legal/` and `../legal/`.
  `../attorney/Attorney_Scope_and_Questions.md` also says $400. So on the sign page the "Your
  terms" box says $350 and the agreement text under it says $400. The attorney has to update the
  drafts.

### New findings

| # | Finding | Who decides |
|---|---|---|
| 13 | **The win-back credit is promised but never applied.** The outreach email can say the first invoice carries a credit, and the outreach desk shows a credit tag, but nothing in `billing.py` applies one. | Diane: build it or drop the offer |
| 14 | **The draft listing agreement and the attorney scope document carry the old price and count** (see change 3). | Attorney |
| 15 | **With one price for everyone, "Founding rate locked" gives a Founding Manager nothing beyond the three free months.** The agreement, the dashboard and the outreach email still present the lock as a benefit. | Diane |

### Decisions from Diane today

Free to investors, with no $10 fee. Off-site backup paid for from the start. Webinars chosen and
the founding-circle outreach dropped. The price above.

### Next, in this order unless Diane says otherwise

1. Finding 7 (sign-in redirect), with a test.
2. The webinar sign-up page, when Diane says go.
3. Finding 1 (documents required before approval), if Diane says yes.
4. Whatever the first Gemini review turns up that holds.

---

## 9 October 2026 · Claude (builder) · First full check, and change 1

### State of the code

- **31 of 31 tests pass** (run on Python 3.10 and 3.13 with Flask 3.1).
- Before today the last code change was 26 September 2026. There was no `instance` folder, so
  neither the app nor the tests had ever been run from this folder.
- Walked the whole path in a running copy with brand-new accounts. Every step worked: manager
  sign-up, email confirmation, firm profile, listing form, signed agreement, three documents
  uploaded, review desk refuses approval without a 506(d) determination, determination recorded,
  approval, manager publishes, investor sign-up, confirmation, catalog in posting order, request
  for materials, manager emailed and sees the request in the pipeline, a manager cannot open
  another firm's fund. This walk was scripted by hand. It is not yet part of the test suite.
- **Not tested:** `run.bat` on Windows (it cannot be run from Linux), sending real email, the
  506(d) agent's internet lookups, two-step sign-in in a browser, the Dockerfile and Procfile.

### Change 1: tests no longer write into the real data folder

- **Problem.** The test suite pointed its database and outbox at a temp folder but not its instance
  folder. Every test run left three things in `app/instance/`: a secret key, a copy of the *test*
  database in `instance/backups/`, and a test PDF in `instance/documents/`. On a machine holding
  real data, that puts a test database among the real backups, and the keep-the-last-30 pruning in
  `jobs.backup()` could then remove the oldest real one.
- **Fix.** `create_app()` now takes `INSTANCE_PATH` from the test config (`luminaz/__init__.py`, one
  line plus a comment). The tests pass their temp folder (`tests/test_app.py`, one line). New test
  `test_tests_never_write_into_the_real_instance_folder`. It fails if the fix is undone.
- **Unchanged.** `run.py` and `manage.py` call `create_app()` with no config and still use
  `app/instance`.
- **Checked.** 31 tests pass. After a test run there is no `instance` folder. A normal start still
  creates it in the right place.
- **Undo.** The folder as it was is in `../backups/app_2026-10-09_before_change_1.zip`.

### Also added today, with no change in behaviour

`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `HANDOFF.md`, `tools/make_review_pack.py`.

### Found and not changed: each needs a decision

| # | Finding | Who decides |
|---|---|---|
| 1 | **A fund can be approved and published with no documents uploaded.** The manager's fund page says "Your listing can't go live until the three core documents are on file," and the investor home page and the manager landing page both tell people core documents are on file. `admin.fund()` checks only the signed agreement and the 506(d) determination. Recommended: refuse approval until a PPM, an operating agreement and subscription documents are uploaded. | Diane |
| 2 | **"Vetted" is on investor-facing pages in four places:** the site-wide meta description (`base.html`) and, on the home page, the structured data, the first line under the headline, and a card heading. The business plan says to describe what is checked and avoid the word, and `admin.py` itself flags "vetted by Luminaz" when a manager writes it. Suggested wording is below. | Diane, then the attorney |
| 3 | **The marketing-language screen skips the firm profile.** It reads a fund's name, strategy and key terms, but not the firm description or principals, which investors see on every fund page. The sample firm description says "Two prior funds, both fully returned." | Diane |
| 4 | **Founding Manager wording disagrees with the code.** The code, Settings and the manager landing page count the first 40 *firms*. The support assistant and the outreach email say the first 40 *funds*. Both also have "$400" typed in rather than read from Settings. | Diane |
| 5 | **Founder signature.** The default in Settings reads "Former financial advisor · 20 years DoD contracts management". Diane said 18 years on 8 October. It goes at the bottom of every outreach email. | Diane |
| 6 | **Investment outcomes are recorded.** The manager's pipeline has an "invested" stage and Metrics shows "Reported invested." Nothing is charged on it. Whether Luminaz should hold that information at all is a question for the attorney. | Attorney |
| 7 | **Sign-in can be used to bounce someone to another website.** `/login?next=//example.com` redirects there after a correct password, because the check only looks for a leading slash (`auth.py`, in `login` and `second_step`). Confirmed in a running copy. Small fix; needed before real users. | Builder, next change |
| 8 | **Password-reset links never expire** and reuse the email-confirmation token column (`auth.py`). Fine for a prototype; needed before real users. | Builder, before launch |
| 9 | **The support assistant's optional AI mode names one model in code** (`claude-sonnet-4-5` in `support.py`). It is off unless a key is set. Check the name when a key is first added. | Builder, before launch |
| 10 | **Calculator message.** The form requires an email, but the error text says "or leave the email blank." | Diane |
| 11 | **No version history.** Until Git is set up, the builder zips `app/` into `../backups/` before each session. | Cliff |
| 12 | **The draft privacy policy promises two things the app does not yet guarantee:** "data is backed up off-server" and "admin access requires two-step sign-in" (`luminaz/legal/privacy_policy.md`). Backups are written to the same disk (`jobs.backup()`; DEPLOY.md section 6 says to copy them by hand), and an admin without two-step sign-in set up can still sign in with a password alone (`auth.login`). Both must be true before real users. | Builder and Cliff, before launch |

### Suggested wording for finding 2 (not applied)

- Meta description: "Luminaz is where accredited investors discover closed-end 506(c) private funds
  in real estate, business acquisition, private debt, and venture. Free for investors."
- Home page, line under the headline: "Closed-end 506(c) funds in real estate, business
  acquisition, private debt, and venture, listed by the managers running them. Free for investors.
  Always."
- Home page, card heading: "What is checked before a fund is listed" (the text under it already
  lists the checks and can stay).
- Home page, structured data: "A listing site where accredited investors discover closed-end 506(c)
  private funds. Not a broker-dealer or investment adviser."

### Not built

Webinar sign-up page; releasing new listings twice a month; online payments (invoices are marked
paid by hand); a real email provider; hosting and the two domains. The premium tier with
highlighted funds is on hold (AGENTS.md section 5).

### Later the same day: direction from Diane

- She prefers webinars for finding investors and has dropped the founding-circle outreach. A webinar
  sign-up page (name, email, recorded consent, a source tag on every link) is therefore the most
  useful next feature. Not started: it waits for her go-ahead.
- She asked about charging investors $10 once, and about buying a list of accredited investors.
  Neither is decided. Both contradict text already in the app ("Free for investors. Always." and
  rule 4.8, no purchased lists), so nothing changes in the code until she decides.
- Decided by Diane: off-site backup will be paid for from the start, as an operating cost, and is
  not advertised as a feature. When hosting exists, the nightly backup should copy itself off the
  server automatically (finding 12). Cliff supplies the storage account; no key goes in the code.

### Next, in this order unless Diane says otherwise

1. Finding 7 (sign-in redirect), with a test.
2. The webinar sign-up page, when Diane says go.
3. Finding 1 (documents required before approval), if Diane says yes.
4. Whatever the first Gemini review turns up that holds.
