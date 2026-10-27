"""Two-step sign-in for administrators: TOTP (Google Authenticator, Authy, 1Password)
plus printed recovery codes. Standard library only; the secret is encrypted at rest
with a key derived from the app's secret key (Fernet if `cryptography` is installed,
otherwise an HMAC-keyed stream cipher, which still keeps the secret out of plain text)."""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

_KEY_CACHE = {}


def _key(app_secret):
    if app_secret not in _KEY_CACHE:
        _KEY_CACHE[app_secret] = hashlib.sha256(("luminaz-2fa:" + app_secret).encode()).digest()
    return _KEY_CACHE[app_secret]


def encrypt(plaintext, app_secret):
    try:
        from cryptography.fernet import Fernet
        f = Fernet(base64.urlsafe_b64encode(_key(app_secret)))
        return "f:" + f.encrypt(plaintext.encode()).decode()
    except ImportError:
        nonce = os.urandom(12)
        stream = _stream(_key(app_secret), nonce, len(plaintext))
        ct = bytes(a ^ b for a, b in zip(plaintext.encode(), stream))
        return "h:" + base64.b64encode(nonce + ct).decode()


def decrypt(token, app_secret):
    if token.startswith("f:"):
        from cryptography.fernet import Fernet
        f = Fernet(base64.urlsafe_b64encode(_key(app_secret)))
        return f.decrypt(token[2:].encode()).decode()
    raw = base64.b64decode(token[2:])
    nonce, ct = raw[:12], raw[12:]
    stream = _stream(_key(app_secret), nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, stream)).decode()


def _stream(key, nonce, n):
    out = b""
    counter = 0
    while len(out) < n:
        out += hmac.new(key, nonce + struct.pack(">I", counter), hashlib.sha256).digest()
        counter += 1
    return out[:n]


def new_secret():
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def totp(secret, for_time=None, step=30, digits=6):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = int((for_time or time.time()) // step)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify(secret, code, window=1):
    code = (code or "").strip().replace(" ", "")
    now = time.time()
    for i in range(-window, window + 1):
        if hmac.compare_digest(totp(secret, now + i * 30), code):
            return True
    return False


def provisioning_uri(secret, email, issuer="Luminaz"):
    return "otpauth://totp/%s:%s?secret=%s&issuer=%s&digits=6&period=30" % (issuer, email, secret, issuer)


def new_recovery_codes(n=8):
    return [secrets.token_hex(4) + "-" + secrets.token_hex(4) for _ in range(n)]


def hash_codes(codes):
    return ",".join(hashlib.sha256(c.encode()).hexdigest() for c in codes)


def use_recovery_code(hashed_csv, code):
    """Returns the remaining hashed list if the code matched, else None."""
    h = hashlib.sha256((code or "").strip().encode()).hexdigest()
    parts = [p for p in (hashed_csv or "").split(",") if p]
    if h in parts:
        parts.remove(h)
        return ",".join(parts)
    return None
