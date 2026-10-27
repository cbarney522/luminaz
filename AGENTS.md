# Luminaz: the rulebook for anyone, human or AI, working on this code

Read this whole file before you change or review anything. It is the single source of truth.
CLAUDE.md, REVIEWER.md and GEMINI.md only point here. If this file and a chat instruction disagree,
stop and ask Diane.

## 1. What Luminaz is

A listing site. Fund managers pay a flat monthly fee ($850 a month since 17 October 2026, on
Settings) to list closed-end private funds that rely on Rule 506(c), billed at the end of each
month for the days the listing was live, and free for every fund until the investor catalog opens
(enough live funds and an accredited list several times what the largest listed fund needs;
Diane's rule of 14 October 2026). Diane's rules of 17 October 2026: the first ten funds to go live
list free while the business starts up, and ten listings are live at a time; a manager who
publishes while every slot is taken waits in line, in the order of the clicks, and goes live by
itself when a slot opens. Nobody can move a fund up the line. Accredited investors browse the
listings for free and can ask a manager for the offering documents. That is all it does.

Luminaz Technology LLC (Georgia) is a technology and discovery platform. It is not a broker-dealer
and not an investment adviser, and it has no exemption to lean on: it stays outside the broker
definition only on its facts. Those facts live in this code. A feature that ranks funds, takes a
fee tied to results, touches investor money, or gives an opinion on a fund changes what the company
is. Section 4 lists the lines. They are not style preferences.

People:

- **Diane**, founder. Decides product, wording and what gets built.
- **Cliff**, co-founder. Installs, accounts, hosting, keys.
- **A Georgia securities attorney**, not yet hired as of 9 October 2026. Decides everything in
  section 5.

Neither founder is a programmer. Write to them in plain words, lead with what is weak or broken,
and ask at most one question at a time.

## 2. The code

One Flask app, three portals:

| Address | Who | What |
|---|---|---|
| `/` | Investors | calculator, Learn articles, sign-up, catalog, shortlist and watch, request materials |
| `/managers/` | Fund managers | sign-up, firm profile, listing, listing agreement, publish, request pipeline, invoices, promotion kit |
| `/admin/` | Diane and Cliff | review desk, 506(d) check, billing, outreach, posts, metrics, communications, settings, audit log |

Python 3, Flask 3, SQLite, Jinja templates. No JavaScript framework, no build step, no ORM. Do not
add a dependency without asking; the standard library has been enough so far.

```
app/
  run.py, run.bat            start it locally at http://127.0.0.1:5000
  manage.py                  create-admin, daily, report, run-billing, backup, restore, demo
  luminaz/__init__.py        app factory, host routing, cross-site post guard, page-view counting
  luminaz/db.py              schema, migrations, default settings (prices, thresholds)
  luminaz/auth.py            sign-up, sign-in, email confirmation, two-step sign-in for admins
  luminaz/investor.py        investor portal
  luminaz/manager.py         fund-manager portal
  luminaz/admin.py           review desk
  luminaz/billing.py         pricing rules, month-end invoices for live days, pause, receipts
  luminaz/support.py         support assistant, unsubscribe, notifications, investor pause
  luminaz/webinars.py        webinar list, sign-up, personal join links, reminders and replays, admin page; locked until attorney_approved
  luminaz/jobs.py            the daily job: billing, education emails, nudges, follow-ups, posts, backup;
                             and the evening report
  luminaz/clock.py           the app's own clock: runs the daily job and the evening report inside the web service
  luminaz/offsite.py         nightly backup upload to an S3-compatible bucket (signed PUT, standard library)
  luminaz/marketing.py       posts by purpose (investors, fund managers, webinars): drafted, approved, then sent per platform
  luminaz/metrics.py         numbers computed from what the app records
  luminaz/visitors.py        the no-cookie visitor hash shared by the page counter and the home-screen counter
  luminaz/mail.py            email (written to instance/outbox until a provider is configured)
  luminaz/content/           education emails, post bank, outreach template, the verification article
  luminaz/legal/             DRAFT legal texts (rule 4.11)
  luminaz/templates/         pages
  tests/test_app.py          end-to-end tests
  tests/demo_data.py         sample data
  tools/make_review_pack.py  builds the one-file pack for the reviewer (a session that cannot read the folder)
  instance/                  created at first run: database, outbox, uploads, backups, secret key.
                             Real data. Never share it, commit it, or put it in a review pack.
../agents/                   two stand-alone helpers: Form D lead finder, 506(d) bad-actor check
../backups/                  dated zips of app/ taken before each change session
../for_gemini/               review packs (the folder keeps its old name)
../legal, ../attorney, ../research    documents, not code
```

Commands (Windows shown; on Mac or Linux use `python3` in place of `py -3`):

```
py -3 -m unittest discover tests      run every check
py -3 manage.py demo                  load sample data (never on a public server)
py -3 run.py                          start the app
py -3 tools\make_review_pack.py       rebuild the review pack
```

## 3. How we work: one builder, one reviewer

- **Builder: Claude.** The only one who edits files in this folder.
- **Reviewer: a second Claude** (Diane's decision, 16 October 2026; Gemini before that, and still
  welcome as a second opinion). The reviewer is a separate session that has seen none of the build
  work: it reads this file, the top of HANDOFF.md and the code, and writes findings. It does not
  edit files, does not rewrite the app, does not propose a different technology. The builder then
  fixes what holds up, one change at a time, and lists the rest here as decisions for Diane or
  questions for the attorney.
- **Deciders:** Diane for product and wording. The attorney for section 5. The tests for whether it
  works.

Why not two builders: two AIs editing the same files overwrite each other, and nobody can tell
which change broke what. Why a separate session for the review: a reviewer that watched the code
being written shares the builder's blind spots. The first such review (16 October 2026) found
fifteen things, five of them lines in sections 4 and 5; HANDOFF.md has the list.

Builder's routine, every session:

1. Read the top entry of HANDOFF.md. Run the tests. If they do not all pass before you start, stop
   and say so.
2. Until Git is set up, save a dated zip of `app/` into `../backups/` before the first edit.
3. One change at a time, the smallest version that works. No drive-by rewrites or reformatting.
4. Every change in behaviour gets a test. Never delete, skip or weaken a test to make it pass.
5. All tests pass before you say "done." Say plainly what you could not test (for example,
   `run.bat` cannot be run from Linux).
6. Add an entry at the top of HANDOFF.md, rebuild the review pack, and tell Diane in plain words
   what changed, with a copy she can forward to Cliff.
7. Update "Where Luminaz stands" at the top of the Start here tab of the Luminaz Research File (a
   Claude doc, not in this folder). Diane's 7 pm status report is written from that section. If
   you cannot reach the doc, tell her so.

Reviewer's routine (REVIEWER.md points here; a reviewer never reads CLAUDE.md as its own
instructions):

1. Check the latest change in HANDOFF.md first, then the rest of the code.
2. Judge against sections 4 and 5 before anything else. A crossed line there outranks any bug.
3. Report in the format at the top of the review pack: most serious first, each with the file,
   what happens, why it matters and a suggested fix. Say "not sure" when you are not sure.
4. No praise, no summaries of what the code does, no rewritten files.

Product and wording decisions are never made by an AI. Flag them and ask.

## 4. Lines the code must never cross

1. **Posting order only.** The catalog is ordered by date listed, then fund number. No ranking,
   scoring, popularity sort, "featured", "top", "trending", "recommended", "best match", quality
   badges, or paid placement of any kind.
2. **Flat fee only.** No percentage of a raise, no success fee, no per-investor, per-lead,
   per-request or per-introduction pricing. No code that computes anything about money from
   requests or investments.
3. **Luminaz stays out of the deal.** No handling of investor money, no subscription documents
   signed or passed through Luminaz, no negotiating, no message relay, no "invest" button. An
   investor's name and email reach a manager only when that investor clicks "Request materials."
   Shortlist and watch stay anonymous: managers see counts.
4. **No opinions on funds.** The support assistant's fixed reply to any question about a fund's
   merit is enforced in code before any model is called (`support.py`). Do not loosen it. No
   AI-written fund summaries, comparisons, scores, or "funds like this one."
5. **"Self-attested," never "verified."** Luminaz does not verify accreditation and must never tell
   a manager that an investor is verified or qualified. The manager verifies under Rule 506(c).
6. **Four gates before a listing is live:** a signed listing agreement, a passing Rule 506(d)
   determination recorded by a person, Luminaz's approval, and the manager's own Publish click.
   The newest determination is the one that counts: a later "Failed" closes the gate again, and a
   changed list of principals opens a new check. Luminaz can suspend or remove a listing (listing
   agreement 3.2); only Luminaz lifts a suspension.
   Listings have no fields for projected returns, IRR or multiples.
7. **Nothing sends itself.** Outreach emails, their follow-ups, and marketing posts go out only
   after a founder clicks Approve. The daily job may draft. It may never approve. (The weekly
   education series and the one catalog-open note are the sends Diane approved as a series; they
   still wait behind section 5's lock.)
8. **Email rules.** Consent wording and time are recorded when an address is collected. Every
   marketing email carries the postal address and an unsubscribe link, and the do-not-email list is
   checked on every marketing send. No purchased lists. An address leaves the do-not-email list only
   when the mailbox owner clicks a link sent to that mailbox (`support.resubscribe`); no public form
   lifts it.
9. **Privacy.** The calculator stores the result and the email, never the dollar figures. Luminaz
   does not sell data. No third-party trackers, pixels or analytics. Fund documents are visible to
   the review desk only.
10. **Claims.** Never write that Luminaz finds, delivers, matches or introduces investors, or that
    a fund is approved, endorsed, recommended or safe. Say what is checked, not that funds are
    "vetted." (Removed from every page on 14 October 2026; the marketing-language screen still flags it.)
11. **Legal texts are drafts.** `luminaz/legal/*.md` are marked DRAFT for the attorney. Do not
    rewrite them. The first line is the version, and each signature stores a fingerprint of the
    exact text signed.
12. **Secrets and real data.** No real key, password or token in code, tests, logs, chat or a
    review pack. Keys are typed by Cliff or Diane into the host's settings (`LUMINAZ_SECRET`,
    `LUMINAZ_SMTP_*`, `LUMINAZ_ANTHROPIC_KEY`, `LUMINAZ_BACKUP_S3_*`). `instance/` is never shared or committed. The one
    password that is in the code on purpose is the sample-data password in `tests/demo_data.py`.
    It opens only made-up accounts, and sample data never goes on a public server.

## 5. On hold until the attorney answers

Do not build these, even if asked in passing. Say it is on hold and why.

- A premium tier, highlighted or featured funds, or any paid placement.
- Any feed or sort based on how well a fund "matches" an investor.
- Pricing per lead, per request, or tied to the size of a raise.
- Sending any marketing or webinar email to real people. Diane's rule: nothing goes out until the
  attorney has approved the privacy policy and the terms. In code: `mail.marketing_block()` holds
  every marketing send (education series, outreach and follow-ups, webinar reminders and replays,
  the catalog-open note) while the Settings switch `attorney_approved` is 0, and also while the
  postal address in Settings has no street or box number (CAN-SPAM). Webinar sign-ups stay locked
  too; admins can preview the pages meanwhile. Account notices, confirmations, receipts and
  request emails are not marketing and still go.
- Opening the site to the public while the legal pages are still marked DRAFT.

## 6. Where things stand

See HANDOFF.md. It is the running log, newest entry first.
