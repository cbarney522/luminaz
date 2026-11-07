# Putting Luminaz on the NewMoneyStrategy.com server (LiquidWeb Cloud VPS, AlmaLinux 8, InterWorx)

For Cliff. Written 7 November 2026. **None of this has been run on your server yet.** Do the steps in
order and tell Claude what you see at each one.

## Where Luminaz lives today (7 November 2026; keep this section current)

- **Temporary home:** NewMoneyStrategy.com, a LiquidWeb Cloud VPS (AlmaLinux 8, InterWorx). It moves
  to a Luminaz domain once the site works the way Diane and Cliff want.
- **Three names, one app:** `www.` (investors), `managers.` (fund managers), `admin.` (founders), all
  under newmoneystrategy.com. They are Settings values (`investor_host`, `manager_host`,
  `admin_host`), not code.
- **Private on purpose:** Apache asks for a password before any page (logins `cliff` and `diane`,
  file `/etc/luminaz/htpasswd`), until Diane and the attorney open the site (AGENTS.md section 5).
- **On the server:** code in `/opt/luminaz/app`, data in `/opt/luminaz/app/instance` (never
  deployed over), Python in `/opt/luminaz/venv`, settings and the secret key in
  `/etc/luminaz/luminaz.env` (root only; a copy is in Cliff's password manager), service `luminaz`,
  deploy watcher `luminaz-deploy.path`, deploy log `/var/log/luminaz-deploy.log`,
  Apache file `/home/newmoney/var/newmoneystrategy.com/apache/luminaz.conf`.
- **How a change goes live:** Claude pushes to `main` on GitHub (`cbarney522/luminaz`), the tests run,
  and if all pass the code goes to the server over FTPS and installs itself (about two minutes). A
  failed test means nothing is deployed. A failed health check puts the previous version back.
- **GitHub secrets used:** `NEWMONEYSTRATEGY_FTP_SERVER`, `NEWMONEYSTRATEGY_FTP_USERNAME`,
  `NEWMONEYSTRATEGY_FTP_PASSWORD`.
- **When something looks wrong (as root on the server):**
  `systemctl status luminaz` and `journalctl -u luminaz -n 50` for the app;
  `tail -30 /var/log/luminaz-deploy.log` for the last deploy;
  `systemctl start luminaz-deploy.service` to redeploy what is already uploaded;
  the GitHub Actions tab shows each run, and "Run workflow" redeploys without a change.
- **Not done yet:** offsite backups (backups sit on the same server), outgoing email (SMTP lines in
  `luminaz.env` are still commented out), the real postal address on Settings, and the "remove an
  admin" page (admins are removed by hand in the database).

## How it works

1. Diane asks Claude for a change. Claude changes the code, runs the tests, and pushes to GitHub.
2. GitHub runs the tests again. If any fails, nothing is sent.
3. If they pass, GitHub sends the code to the server over encrypted FTP (FTPS) into one folder, then
   uploads a one-line "signal" file.
4. The server notices the signal file, copies the new code into place, installs what it needs,
   restarts Luminaz, and checks that it answers. If it does not answer, it puts the previous
   version back. The log is `/var/log/luminaz-deploy.log`.

The database, uploads and backups live in `/opt/luminaz/app/instance`. A deploy never touches that
folder.

## Weak spots, up front

- **FTP only carries files.** It cannot restart anything, which is why the server watches the signal
  file. If that watcher breaks, deploys will upload but not take effect.
- **Plain FTP is not safe.** The workflow uses FTPS. If your FTP account does not accept FTPS, stop
  and tell Claude; do not switch the workflow to plain FTP.
- **The Apache step is the least certain.** InterWorx manages Apache and can overwrite hand edits.
  Ask LiquidWeb support where InterWorx keeps custom settings for a domain (a "vhost include").
- **Backups on the same server are not enough.** Turn on the offsite backup (Settings keys
  `LUMINAZ_BACKUP_S3_*`, see DEPLOY.md) before real data goes in.
- **Anyone who can push to the GitHub repo can change what runs on the server.** Keep the GitHub
  accounts protected with two-step sign-in.

## Step 1: GitHub secrets (Settings, Secrets and variables, Actions)

Already added: `NEWMONEYSTRATEGY_FTP_PASSWORD`. Add two more:

- `NEWMONEYSTRATEGY_FTP_SERVER`: the FTP host name (for example `ftp.newmoneystrategy.com`).
- `NEWMONEYSTRATEGY_FTP_USERNAME`: the FTP account name.

## Step 2: Two folders on the server

Log in to the FTP account and create two folders in its starting directory: `luminaz-incoming` and
`luminaz-signal`. Then, over SSH as root, find their full paths, for example
`/home/ftpuser/luminaz-incoming` and `/home/ftpuser/luminaz-signal` (`ls -d /home/*/luminaz-*`).
Some FTP accounts are locked into a folder, so the FTP path and the server path can differ.

## Step 3: Run the setup script (once)

```
sudo -i
dnf -y install git
git clone https://github.com/cbarney522/luminaz /root/luminaz-src
cd /root/luminaz-src
bash deploy/server-setup.sh /home/FTPUSER/luminaz-incoming /home/FTPUSER/luminaz-signal
```

It installs Python 3.12, creates a `luminaz` user, starts Luminaz on port 8000 (only reachable from
the server itself), and starts the signal watcher. It creates `/etc/luminaz/luminaz.env` with a
random secret. **Copy that file somewhere safe (a password manager): if it is lost or changed, every
admin's two-step setup breaks.**

Then create the first admin:

```
cd /opt/luminaz/app
runuser -u luminaz -- /opt/luminaz/venv/bin/python manage.py create-admin you@example.com
```

## Step 4: Three DNS names, one server

In the domain's DNS, point these at the server's IP address: `www`, `managers`, `admin`
(newmoneystrategy.com). In InterWorx, add them to the site (as the main domain and two subdomains or
aliases) and request one SSL certificate that covers all three (InterWorx offers Let's Encrypt).

## Step 5: Hand the websites to Luminaz (tested 7 November 2026 on InterWorx 8, AlmaLinux 8)

InterWorx keeps custom Apache settings in a per-domain folder, switched off until the server admin
enables it. As root:

```
/home/interworx/bin/config.pex --set --name "HTTPD_USE_CUSTOM_INCLUDE" --value "1" --domain newmoneystrategy.com
~iworx/bin/httpd.pex --sync-vhosts --domain newmoneystrategy.com
```

All of the domain's vhosts (the main name with www, managers, admin) then include
`/home/newmoney/var/newmoneystrategy.com/apache/*.conf`, so **one** file covers every name. Create
the private-access logins first (`htpasswd -c /etc/luminaz/htpasswd cliff`, then
`htpasswd /etc/luminaz/htpasswd diane`; `chgrp apache` and `chmod 640` the file), then create
`luminaz.conf` in that folder with the contents of `deploy/apache-proxy.conf.example`, then:

```
httpd -t && systemctl reload httpd
curl -sI https://admin.newmoneystrategy.com/login | head -3     # expect: HTTP/2 401
```

The file starts the site **private** (a password in front of everything) until Diane and the
attorney open it. To open it, delete the `<Location />` block and reload Apache.

Side effect: the main name, `ftp.` and `mail.` also reach Luminaz, because they share the main
vhost. Nothing in the app depends on them.

## Step 6: Tell Luminaz its three names

Sign in at `https://admin.newmoneystrategy.com/login`, open Settings, Domains, and enter:

- Investor site host: `www.newmoneystrategy.com`
- Fund manager portal host: `managers.newmoneystrategy.com`
- Admin host: `admin.newmoneystrategy.com`

Also on Settings: the postal address. Then turn on two-step sign-in (Security) for every admin.

## Step 7: Try a deploy

On GitHub, open Actions, Test and deploy, Run workflow. When it finishes, read
`/var/log/luminaz-deploy.log` on the server: the last line should say "Deploy finished."

## Later: moving to a Luminaz domain

The three names are Settings values, not code. Moving means: copy `/opt/luminaz/app/instance` and
`/etc/luminaz/luminaz.env` to the new server (same secret), run this setup there, point the new DNS
names at it, and change the three hosts in Settings.
