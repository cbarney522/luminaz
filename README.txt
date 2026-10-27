LUMINAZ APPLICATION
===================

One application, three portals:
  http://127.0.0.1:5000/            Luminaz for investors (calculator, catalog, shortlist, requests)
  http://127.0.0.1:5000/managers/   Luminaz for Fund Managers (listings, agreement, pipeline, invoices)
  http://127.0.0.1:5000/admin/      Review desk (approvals, mods, 506(d), billing, settings)

TO START IT ON THIS COMPUTER
  1. Install Python once from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
  2. Double-click run.bat. It installs the one library it needs, loads sample data the first
     time, opens your browser, and keeps running until you close the window.

FIRST SIGN-IN AS ADMIN
  Admin pages open only after two-step sign-in is set up (Security page: scan the QR code with any
  authenticator app, enter the code, print the recovery codes). To skip that on a test machine:
  py -3 manage.py setting require_admin_2fa 0

SAMPLE ACCOUNTS (first run only; delete the instance folder to start clean)
  admin@luminaz.test      the review desk (you)
  manager@luminaz.test    a fund manager with a live fund
  manager2@luminaz.test   a fund manager waiting for approval
  investor@luminaz.test   an investor
  password for all:       luminaz-demo-2026

WHEN YOU ARE READY FOR REAL DATA
  delete the "instance" folder, then run:   py -3 manage.py create-admin you@yourdomain.com
  Emails: until a provider is configured, every email the app sends is written as a text file
  in instance\outbox so you can read it. Confirmation links inside them work when pasted into
  the browser.

WHAT IS BUILT
  - Investor: landing page with the eight categories as the first step, About page, footer with the
    platform disclosure on every page, accreditation calculator (keeps result + email only), six-week
    education email series with unsubscribe, sign-up gated until N funds are live, self-attested
    accreditation basis, posting-order catalog as tiles (as many per row as fit, ten on a wide screen)
    with filters, shortlist and watch (anonymous to managers), material requests (the one moment
    contact reaches a manager) with a "before you request materials" note and a Learn article on how
    verification works, pause and resume the account, support page with an assistant that answers
    how-to questions and refuses to judge funds.
  - Manager: landing page with header, footer and pricing, sign-up, firm profile with principals,
    self-serve listing in one of eight categories, typed listing agreement with name/title/time/IP
    and document hash, $850 a month per fund (Settings; the first ten funds to go live list free),
    free for every fund until the investor catalog opens (enough live funds AND an accredited list
    5x what the largest listed fund needs; both numbers on Settings), billed at the end of each
    month for the days the listing was live, ten listings live at a time with a line for the rest
    (a Publish click while every slot is taken joins the line; the first in line goes live by
    itself when a slot opens),
    Founding Manager status for the first 25 firms (rate locked), numbered funds and numbered mods
    (routine fields auto-apply, everything else reviewed), fund document uploads (PPM, operating
    agreement, subscription docs; seen by Luminaz only), the manager's own Publish click after
    approval, pause and resume (the listing stays visible with a "paused" label, takes no requests,
    paused days are not charged), private request pipeline, reminders when a request sits untouched,
    invoices with live days, emailed receipts, close listing with the closing month invoiced at once,
    promotion kit.
  - Admin: review desk with the four weekly numbers, firm and fund approval with a vetting
    checklist, marketing-language screen, documents on file, 506(d) determination recorded
    before any approval, one-click run of the bad-actor agent (when placed in
    ..\agents\bad_actor_agent), billing (issue, pause at 10 days past due, resume, record
    payments, credits), outreach desk (import the lead agent's CSV, agent drafts each email, you
    approve and send, follow-up drafted for your approval, reply tracking, win-back credit), support tickets,
    two-step sign-in with recovery codes, settings, audit log, "Run daily tasks" button, and a
    Posts page: marketing posts by purpose (change 28): to accredited investors (Mon/Wed/Fri, from a
    36-post bank), to fund managers (Tue, from a 12-post bank), and about any open webinar (Thu,
    once the attorney switch is on). Each opens with a hook line you can edit, and goes out as one
    text per platform with its own ?src= link (LinkedIn, Facebook, X; set per purpose on Settings),
    to a Zapier/Make/Buffer webhook or emailed to you to paste until a webhook is set. The
    marketing-language screen flags words on every draft. Nothing posts without your Approve click.
    Communications page (change 33): what every post, webinar, email series and outreach email
    brought, from the app's own counts; every post link carries &p=<post id> so visitors, leads and
    webinar sign-ups are credited to the post. Likes and impressions stay in the posting service.
  - Consent and unsubscribe: recorded consent text and time on every calculator lead and account;
    one unsubscribe link that works for leads, accounts, and outreach contacts (one-click header
    too); a Notifications page for account holders; a do-not-email list every marketing send checks;
    postal address and unsubscribe line on every marketing email (CAN-SPAM); an unsubscribed address
    comes back only through a confirmation link sent to that mailbox. Every marketing email is held
    until "Attorney has approved" is 1 in Settings and the postal address holds a street or box number.
  - Webinars: public list and sign-up page (name, email, recorded consent, ?src= tag), confirmation
    with a personal join link that records who joined, reminder the day before and replay afterwards
    (daily job), admin page to create webinars and mark attendance. Locked until "Attorney has
    approved" is 1 on the Settings page; admins can preview meanwhile.
  - Security: login throttle, cross-site post guard, admins must set up two-step sign-in before any
    admin page opens (Settings: require_admin_2fa; py -3 manage.py setting require_admin_2fa 0 to
    switch it off on a test machine), password-reset links expire after 60 minutes and work once,
    nightly backup also copied to a folder you name (Settings: backup_copy_dir), plus the items in
    DEPLOY.md section 10.
  - Marketing spend: on the Metrics page, type in what you spent by month and source word; the page
    shows leads, accredited leads, webinar sign-ups and the cost per accredited lead for each.
  - Metrics: first-party visitor counting (no cookies, no third party), ?src= attribution on every
    link and lead, a Metrics page with a day-by-day table, the funnel and twelve weekly columns,
    funds by interest, an evening report by email at 7 pm (the day's numbers so far and what is
    waiting on you) and a Monday email with last week's. Luminaz can be added to a phone's home
    screen, and those installs and opens are counted the same no-cookie way (iPhones report only
    the opens).
  - Search: public Learn section (36 articles), sitemap.xml, robots.txt, meta descriptions, Open
    Graph, structured data, noindex on private pages. See DEPLOY.md section 9.
  - Two domains: set the investor host and manager host in Settings and the app routes each
    side to its own domain.
  - Legal: draft listing agreement, manager terms, investor terms, privacy policy in luminaz\legal.
    All marked DRAFT for the Georgia attorney.

STILL YOUR CALL
  Real email provider and hosting (see DEPLOY.md), payment rail (bank transfer / check now;
  ACH provider later), closed-listing tier and onboarding fee (settings exist, switched off).

DAILY JOB
  py -3 manage.py daily      billing, education emails, catalog-open note, nudges, follow-up drafts, backup
  Or click "Run daily tasks" on the Billing page. See DEPLOY.md to schedule it.
  py -3 manage.py report     the evening report; scheduled every hour, it sends once, at 7 pm
  py -3 manage.py report now sends it right away, to try it (until an email provider is set up
                             it is saved as a text file in instance\outbox)

TESTS
  py -3 -m unittest discover tests      (49 end-to-end tests)
