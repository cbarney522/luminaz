# Putting Luminaz on the NewMoneyStrategy.com server (LiquidWeb Cloud VPS, AlmaLinux 8, InterWorx)

For Cliff. Written 7 November 2026. **None of this has been run on your server yet.** Do the steps in
order and tell Claude what you see at each one.

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

## Step 5: Hand the websites to Luminaz

Add the proxy settings from `deploy/apache-proxy.conf.example` to each of the three names, in the
place InterWorx keeps custom settings. **Use the "keep it private" option in that file until Diane
and the attorney say the site can open** (AGENTS.md section 5).

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
