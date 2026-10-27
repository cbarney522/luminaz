# Putting Luminaz on the internet

Everything runs from one small server. Budget: about $10 to $25 a month for hosting plus
the two domains and an email-sending account.

## 1. Pick a host

Any of these works; all three take the files as they are.

| Host | How it deploys | Notes |
|---|---|---|
| Render (render.com) | Connect a Git repo or upload; it reads the `Procfile` | Add a persistent disk mounted at `/opt/render/project/src/instance` so the database survives deploys |
| Railway (railway.app) | Same, reads the `Dockerfile` | Add a volume at `/app/instance` |
| A plain VPS (DigitalOcean, Hetzner, Lightsail) | `pip install -r requirements.txt`, run gunicorn behind Caddy or nginx | Most control, most steps |

The database is a single SQLite file in `instance/`. That is fine well past the first hundred
funds. Whatever you choose, the `instance` folder must be on a disk that persists.

## 2. Environment variables

| Variable | What it does |
|---|---|
| `LUMINAZ_SECRET` | Long random string; signs sessions and encrypts 2FA secrets. Generate once, never change it. |
| `LUMINAZ_HTTPS=1` | Marks cookies secure and builds https links. Set it on every public server. |
| `LUMINAZ_SMTP_HOST`, `LUMINAZ_SMTP_PORT`, `LUMINAZ_SMTP_USER`, `LUMINAZ_SMTP_PASSWORD`, `LUMINAZ_MAIL_FROM` | Outgoing email. Until set, emails are written to `instance/outbox` instead of sent. Postmark, Resend, Amazon SES, and Mailgun all give SMTP credentials on sign-up. |
| `LUMINAZ_PUBLIC_HOST` | Host used for links in emails sent from the command line (`manage.py daily`). Defaults to the investor host setting. |
| `LUMINAZ_ANTHROPIC_KEY` | Optional. Lets the support assistant compose answers from its knowledge base instead of keyword-matching it. |
| `PORT` | Set by the host. |

## 3. Two domains, one app

Point both domains at the same server (an A record, or the CNAME the host gives you). Then, in
the admin Settings page, fill in **Investor site host** and **Fund manager portal host**. From
then on manager and admin pages redirect to the manager domain and investor pages to the
investor domain. Sign-in, legal pages, support, and unsubscribe work on both.

Leave both blank while testing on one address.

## 4. First run on the server

```
py -3 manage.py create-admin you@yourdomain.com      # or python3 on Linux
```

Sign in, go to **Security**, and turn on two-step sign-in for every admin before the first fund
manager is invited. Print the recovery codes.

## 5. The daily job

**Change 30 (22 October 2026): the app runs its own clock.** Every web worker runs the daily job
once a day (Settings: `daily_job_hour`, 6 am) and the evening report at its hour, from inside the
web service, so on Render or Railway there is nothing to schedule and finding 16 no longer applies.
Set `TZ=America/New_York` on the service. The commands below still work and are optional on a VPS.

Once a day, run:

```
python3 manage.py daily
```

Set the host's `TZ` environment variable to the founders' time zone (`America/New_York`) so
"today" and "yesterday" in the numbers, invoices and posts mean their day, not the server's.

It issues invoices, pauses late listings, sends the next education email to calculator leads,
nudges managers about untouched requests, drafts outreach follow-ups for your approval, and writes a backup to
`instance/backups` (last 30 kept, with a zip of the uploaded documents). Render and Railway have
a "cron job" service type for this; on a VPS use `crontab -e`:

```
15 6 * * *  cd /app && python3 manage.py daily >> instance/daily.log 2>&1
```

The same job is behind the **Run daily tasks** button on the Billing page, so nothing breaks if
the schedule is missed; the button is safe to press at any time.

### The evening report, at 7 pm

Every hour, also run:

```
python3 manage.py report
```

It does nothing until 7 pm on the founders' clock. Then it emails them once: the day's numbers so
far beside yesterday's, what is waiting on them (funds, firm profiles and listing changes to
review, posts to approve, outreach emails to send, support questions, invoices past due), and the
totals. The hour is on the Settings page. It goes to the same address as the Monday numbers.

Why every hour and not once at 7 pm: most hosts schedule in UTC, which does not move with
daylight saving time. An hourly run plus the `TZ` setting above keeps the report at 7 pm Eastern
all year. The scheduled job must have the same `TZ` setting as the web app.

```
0 * * * *  cd /app && python3 manage.py report >> instance/daily.log 2>&1
```

`python3 manage.py report now` sends it at once, to try it (still only once a day). If the hourly
schedule is missing, the daily job or the **Run daily tasks** button sends the report when it runs
at or after that hour.

Not checked yet: on Render and Railway a scheduled job may run in its own container, which
cannot open the web app's `instance` disk. If so, neither this command nor `manage.py daily` can
run there as a separate cron service. Settle it when the host is chosen (HANDOFF.md, finding 16).

## 5b. Social media posting (optional)

The three weekly posts can go out by themselves once you connect a posting service. Zapier, Make,
and Buffer all offer a "catch webhook" trigger: create a Zap/scenario whose trigger is a webhook
and whose action is "create post" on LinkedIn, Facebook Page, and X; paste the webhook URL into
**Settings → Webhook that posts to social media**. Each approved post is sent to it as JSON
(`long`, `short`, `hashtags`, `topic`, `scheduled_for`) on its day. Until then the app emails you
the approved text on the day and you paste it. Plans start around $20 a month.

## 6. Backups off the server

**Change 31 (22 October 2026): a bucket.** Create a private bucket at Backblaze B2 or Cloudflare R2
(about a dollar a month) and type five settings into the host: `LUMINAZ_BACKUP_S3_ENDPOINT`,
`LUMINAZ_BACKUP_S3_BUCKET`, `LUMINAZ_BACKUP_S3_KEY`, `LUMINAZ_BACKUP_S3_SECRET`, `LUMINAZ_BACKUP_S3_REGION`
(`us-west-004` for that B2 endpoint, `auto` for R2). Every nightly backup is then uploaded and the
newest 30 kept. Check the bucket after the first daily run. The synced-folder setting below still
works on a laptop or a VPS.

`instance/backups` is on the same disk as the database. Put the path of a folder that is synced or
mounted elsewhere (OneDrive, Dropbox, an rclone mount, a second disk) into Settings, "Also copy each
nightly backup to this folder", and every nightly backup is copied there too. Without that, copy
the newest `luminaz-*.sqlite` and its `-documents.zip` somewhere else by hand once a week.
To restore: stop the app, `python3 manage.py restore instance/backups/<file>`, start it.

## 7. Before the first real listing

- [ ] Attorney has signed off on the four legal documents in `luminaz/legal`
- [ ] Payment instructions in Settings show the real bank details
- [ ] Settings: the price, the catalog-opening rule (live funds, the multiple, the cap on the list), the booking page link, and the postal address printed in the footer and on marketing email (a street or PO box; marketing email is held until it has one)
- [ ] Support email in Settings is a real, watched inbox
- [ ] Both admins have two-step sign-in on (the app insists on it: Settings `require_admin_2fa` = 1)
- [ ] "Attorney has approved" set to 1 in Settings only once it is true; every marketing email (education series, outreach, webinars, the catalog-open note) and webinar sign-ups stay locked until then
- [ ] The off-server backup folder in Settings points at synced or mounted storage, and a backup appeared there
- [ ] Sent yourself a test email through the SMTP settings and it arrived (check spam)
- [ ] Daily job scheduled and has run once
- [ ] Evening report scheduled every hour, and `manage.py report now` reached the founders' inbox
- [ ] Sample data cleared (delete `instance/luminaz.sqlite` and run `create-admin` again)

## 7b. Tracking

Traffic is counted inside the app: one row per page view with the day, path, source, and a daily
hash of address + browser that cannot be reversed and changes every day. No cookie, no consent
banner, no data leaves the server. Put `?src=linkedin`, `?src=facebook`, `?src=newsletter`,
`?src=podcast` on the links you share; the source follows the visitor to the calculator and is
recorded on the lead. The Metrics page shows the funnel, twelve weekly columns, sources, top
pages, and funds by investor interest. Every Monday the daily job emails last week's numbers to
the address in Settings (post notify email, else support email). If you later want Google
Analytics as well, add its tag to `base.html`; expect to need a cookie banner if you do.

## 8. Performance notes

Measured on a test database with 600 funds, 3,400 accounts, 30,000 material requests, 60,000
shortlists, 100,000 page views and 50,000 audit rows: every page renders in under 30 ms, the
daily billing run in under 10 ms. The database at that size is about 23 MB. Built in: indexes on
every column the app filters or joins on, SQLite in WAL mode (readers never wait for the daily
job), a week of browser caching on static files, gzip on every HTML page, and grouped queries
on the dashboards so page time does not grow with the number of funds. Two gunicorn workers
handle a few hundred simultaneous users; raise `--workers` to the number of CPU cores if the
host reports load. Nothing in the app needs Redis, Postgres, or a queue until well past the
first thousand funds.

## 9. Getting found on Google

Built in: a public **Learn** section (36 articles about accredited investor status at `/learn/...`,
the same text as the weekly posts), `sitemap.xml`, `robots.txt`, a meta description and canonical
link on every public page, Open Graph tags for link previews, structured data (Organization on
the home page, FAQ on the calculator, Article on each Learn page), and `noindex` on every
signed-in, manager, and admin page so nothing private is ever listed.

What only you can do, in order:
1. Once the domains are live, open Google Search Console (search.google.com/search-console),
   add both domains, verify by DNS record, and submit `https://<investor domain>/sitemap.xml`.
   Do the same in Bing Webmaster Tools; it takes five minutes and Bing feeds DuckDuckGo.
2. Create a Google Business Profile for the LLC (free) with the Acworth address or a service area.
3. Every weekly post should link to its Learn page, not just the calculator: those links are
   what tell Google the pages matter. Ask each listed fund manager to link to their Luminaz
   listing from their own site; a "listed on Luminaz" line in their footer is the single most
   valuable link you can get.
4. Expect nothing for the first 2 to 3 months on a new domain, then slow growth. Search
   Console's "Performance" tab shows which queries bring people in; write the next Learn
   articles around the questions that appear there.

## 10. Security: what is built in, and what only you can do

Built in: passwords hashed (never stored), two-step sign-in for admins with recovery codes,
sign-in paused after eight wrong passwords in fifteen minutes, cross-site form posts refused,
cookies HttpOnly/Secure/SameSite, security headers on every response, no data in URLs, uploaded
documents stored outside the web root and served only to admins, private pages marked noindex,
an audit log of every approval, payment, sign-in, and settings change, encrypted 2FA secrets,
daily backups, and a do-not-email list.

Only you can do these:
1. Keep `LUMINAZ_SECRET` secret and never change it (it encrypts the 2FA secrets and signs sessions).
2. Turn on two-step sign-in for both admin accounts before the first manager is invited, and keep
   the recovery codes on paper, not in email.
3. Use a password manager; a unique 16+ character password for the host, the registrar, the email
   provider, the bank, and Luminaz itself. Two-step sign-in on all of them.
4. HTTPS only: set `LUMINAZ_HTTPS=1` and let the host issue the certificate. Never run the public
   site over plain http.
5. Weekly copy of `instance/backups` somewhere the server can't reach (a cloud drive).
6. Don't email fund documents or investor lists around; read them in the app. What isn't
   copied can't leak.
7. When someone leaves (a future contractor, an admin), remove the account the same day; the audit
   log shows what they touched.
8. Report a breach affecting Georgia residents' personal data within the time Georgia law
   requires (currently without unreasonable delay); the attorney's memo should include the
   procedure.
