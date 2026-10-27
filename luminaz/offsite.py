"""Off-server backup copy to an S3-compatible bucket (change 31, 22 October 2026).

Why: the privacy policy promises an off-server backup, and the "copy to a synced folder" setting
(finding 12) only works where OneDrive or Dropbox is mounted, which a cloud host does not have.
A bucket at Backblaze B2, Cloudflare R2 or Amazon S3 costs about a dollar a month at this size.

How: after each nightly backup the database copy and the documents zip are uploaded with a plain
HTTPS PUT signed the standard way (AWS Signature Version 4), using only the standard library
(rule: no new dependency). The newest `keep` backups stay in the bucket; older ones are deleted.

Switched on by five host settings typed by Cliff (rule 4.12: keys never live in the code or the
database):
  LUMINAZ_BACKUP_S3_ENDPOINT   https://s3.us-west-004.backblazeb2.com  or  https://<account>.r2.cloudflarestorage.com
  LUMINAZ_BACKUP_S3_BUCKET     the bucket name (private; never a public bucket)
  LUMINAZ_BACKUP_S3_KEY        the key id
  LUMINAZ_BACKUP_S3_SECRET     the secret
  LUMINAZ_BACKUP_S3_REGION     us-west-004 for that B2 endpoint, auto for R2, us-east-1 for S3 (default)
Until all of the first four are set, nothing is attempted and the daily job reports "off".
"""
import datetime as dt
import hashlib
import hmac
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def config():
    c = {k: os.environ.get("LUMINAZ_BACKUP_S3_" + k.upper(), "").strip() for k in ("endpoint", "bucket", "key", "secret", "region")}
    c["region"] = c["region"] or "us-east-1"
    return c


def enabled(c=None):
    c = c or config()
    return all(c[k] for k in ("endpoint", "bucket", "key", "secret"))


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _quote(s):
    return urllib.parse.quote(s, safe="-_.~")


def _quote_path(s):
    """A URI path: each segment encoded, the slashes between them kept (what S3 signs against)."""
    return urllib.parse.quote(s, safe="-_.~/")


def canonical_request(method, path, query, headers, payload_hash):
    """The canonical request AWS specifies: method, URI path, sorted query, lower-cased sorted
    headers, the signed-header list, the payload hash. `query` is a dict; `headers` a dict."""
    canon_query = "&".join("%s=%s" % (_quote(k), _quote(str(v))) for k, v in sorted(query.items()))
    low = {k.lower(): " ".join(str(v).split()) for k, v in headers.items()}
    names = sorted(low)
    canon_headers = "".join("%s:%s\n" % (k, low[k]) for k in names)
    signed = ";".join(names)
    return "\n".join([method, path, canon_query, canon_headers, signed, payload_hash]), signed


def authorization(method, path, query, headers, payload_hash, key_id, secret, region, when, service="s3"):
    """The Authorization header value for one request (AWS Signature Version 4)."""
    amz_date = when.strftime("%Y%m%dT%H%M%SZ")
    scope = "%s/%s/%s/aws4_request" % (when.strftime("%Y%m%d"), region, service)
    creq, signed = canonical_request(method, path, query, headers, payload_hash)
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(creq.encode("utf-8")).hexdigest()])
    k = _sign(("AWS4" + secret).encode("utf-8"), when.strftime("%Y%m%d"))
    k = _sign(k, region)
    k = _sign(k, service)
    k = _sign(k, "aws4_request")
    sig = hmac.new(k, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (key_id, scope, signed, sig)


def request(method, object_key="", query=None, body=b"", c=None, when=None, opener=None):
    """One signed request to the bucket (path-style URL: endpoint/bucket/key). Returns (status, body)."""
    c = c or config()
    query = query or {}
    when = when or dt.datetime.now(dt.timezone.utc)
    u = urllib.parse.urlparse(c["endpoint"])
    path = "/" + _quote(c["bucket"]) + ("/" + _quote_path(object_key) if object_key else "")
    payload_hash = hashlib.sha256(body).hexdigest() if body else EMPTY_SHA256
    headers = {"host": u.netloc, "x-amz-date": when.strftime("%Y%m%dT%H%M%SZ"), "x-amz-content-sha256": payload_hash}
    if body:
        headers["content-length"] = str(len(body))
    auth = authorization(method, path, query, headers, payload_hash, c["key"], c["secret"], c["region"], when)
    url = "%s://%s%s" % (u.scheme, u.netloc, path)
    if query:
        url += "?" + "&".join("%s=%s" % (_quote(k), _quote(str(v))) for k, v in sorted(query.items()))
    req = urllib.request.Request(url, data=body if body else None, method=method)
    for k, v in headers.items():
        if k != "host":
            req.add_header(k, v)
    req.add_header("authorization", auth)
    open_ = opener or urllib.request.urlopen
    with open_(req, timeout=120) as resp:
        return resp.status, resp.read()


def list_keys(prefix, c=None, opener=None):
    status, body = request("GET", "", {"list-type": "2", "prefix": prefix}, c=c, opener=opener)
    root = ET.fromstring(body)
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    return sorted(el.text for el in root.iter(ns + "Key"))


def upload_backup(paths, keep=30, c=None, opener=None):
    """Upload the given backup files; then delete the oldest beyond `keep` database copies.
    Returns a short status word for the daily job's summary."""
    c = c or config()
    if not enabled(c):
        return "off"
    sent = 0
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        with open(p, "rb") as f:
            body = f.read()
        status, _ = request("PUT", "backups/" + os.path.basename(p), body=body, c=c, opener=opener)
        if status not in (200, 201):
            return "failed (%s on %s)" % (status, os.path.basename(p))
        sent += 1
    try:
        keys = [k for k in list_keys("backups/luminaz-", c=c, opener=opener) if k.endswith(".sqlite")]
        for old in keys[:-keep]:
            request("DELETE", old, c=c, opener=opener)
            z = old[:-7] + "-documents.zip"
            request("DELETE", z, c=c, opener=opener)
    except Exception as e:                       # pruning is housekeeping; the upload already succeeded
        return "uploaded %d, prune failed (%s)" % (sent, e.__class__.__name__)
    return "uploaded %d" % sent
