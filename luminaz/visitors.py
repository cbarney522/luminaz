"""Who counts as a visitor, without cookies. One helper, so page views and installed-app events
count the same person the same way: a hash of the day, the app's secret, the address and the
browser. It cannot be reversed, it changes every day, and nothing is stored on the visitor's device."""
import datetime as dt
import hashlib

from flask import current_app, request

BOT_WORDS = ("bot", "crawl", "spider", "preview", "curl", "python-requests")


def is_bot(user_agent):
    ua = (user_agent or "").lower()
    return not ua or any(w in ua for w in BOT_WORDS)


def visitor_hash(day=None):
    day = day or dt.date.today().isoformat()
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()
    ua = request.headers.get("User-Agent", "")
    return hashlib.sha256((day + current_app.config["SECRET_KEY"] + ip + ua).encode()).hexdigest()[:24]
