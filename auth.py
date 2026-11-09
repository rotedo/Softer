"""Login: ADMIN_PASSWORD env (or PBKDF2 hash saved via /api/admin/password), HMAC cookie, rate limit."""
import hashlib, hmac, os, secrets, time
import store

TTL = 30 * 86400
_FAILS = {}


def _secret():
    s = os.environ.get("APP_SECRET")
    if s:
        return s.encode()
    s = store.kv_get("_secret")
    if not s:
        s = secrets.token_hex(32)
        store.kv_set("_secret", s)
    return s.encode()


def configured():
    return bool(store.kv_get("pw_hash") or os.environ.get("ADMIN_PASSWORD"))


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()


def check_password(pw):
    h = store.kv_get("pw_hash")
    if h:
        return hmac.compare_digest(_hash(pw, h["salt"]), h["hash"])
    env = os.environ.get("ADMIN_PASSWORD", "")
    return bool(env) and hmac.compare_digest(pw.encode(), env.encode())


def set_password(pw):
    if len(pw) < 10:
        raise ValueError("password must be at least 10 characters")
    salt = secrets.token_hex(16)
    store.kv_set("pw_hash", {"salt": salt, "hash": _hash(pw, salt)})


def limited(ip):
    t = time.time()
    _FAILS[ip] = [x for x in _FAILS.get(ip, []) if t - x < 900]
    return len(_FAILS[ip]) >= 5


def login(pw, ip):
    if limited(ip):
        return None
    if check_password(pw or ""):
        _FAILS.pop(ip, None)
        return token()
    _FAILS.setdefault(ip, []).append(time.time())
    return None


def token():
    exp = str(int(time.time()) + TTL)
    return exp + "." + hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()


def valid(tok):
    try:
        exp, sig = tok.split(".")
        return int(exp) > time.time() and hmac.compare_digest(sig, hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest())
    except Exception:
        return False
