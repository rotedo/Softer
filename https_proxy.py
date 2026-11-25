"""Free HTTPS for the app with NO terminal commands.
The app downloads Caddy (a small web server) by itself, gets a real certificate for your free DuckDNS name using the DNS challenge
(so no port 80 and no root rights are needed) and serves the app on https://NAME.duckdns.org:8443/app.
You only paste the DuckDNS name + token in Settings > HTTPS and open TCP port 8443 in the AWS security group."""
import json, os, platform, re, signal, subprocess, threading, time, urllib.request

import store

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "caddy_data")
BIN, CF, LOG, PID = (os.path.join(DIR, n) for n in ("caddy", "Caddyfile", "caddy.log", "caddy.pid"))
HTTPS_PORT = 8443
_lock = threading.Lock()
LAST = {"error": ""}


def cfg():
    return store.kv_get("https_cfg", {}) or {}


def _valid(domain, token):
    domain = str(domain or "").strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0].split(":")[0]
    token = str(token or "").strip()
    if not re.fullmatch(r"[a-z0-9-]{3,40}\.duckdns\.org", domain):
        raise ValueError("name must look like yourname.duckdns.org")
    if not re.fullmatch(r"[0-9a-fA-F-]{30,40}", token):
        raise ValueError("the DuckDNS token looks wrong (copy it from duckdns.org, it has letters, digits and dashes)")
    return domain, token


def caddyfile(domain, app_port):
    return ("{\n\tadmin off\n\tauto_https disable_redirects\n}\n"
            f"{domain}:{HTTPS_PORT} {{\n\ttls {{\n\t\tdns duckdns {{env.DUCKDNS_API_TOKEN}}\n\t}}\n"
            f"\treverse_proxy 127.0.0.1:{app_port} {{\n\t\theader_up X-Real-IP {{remote_host}}\n\t\tflush_interval -1\n\t}}\n}}\n")


def _download():
    if os.path.exists(BIN) and os.path.getsize(BIN) > 10_000_000:
        return
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if not arch:
        raise RuntimeError("unsupported machine type: " + platform.machine())
    os.makedirs(DIR, exist_ok=True)
    url = f"https://caddyserver.com/api/download?os=linux&arch={arch}&p=github.com/caddy-dns/duckdns"
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-terminal/1.0"})
    with urllib.request.urlopen(req, timeout=240) as r, open(BIN + ".part", "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(BIN + ".part", BIN)
    os.chmod(BIN, 0o755)


def _duck_update(domain, token):
    """points NAME.duckdns.org at this server's public IP (the address DuckDNS sees us coming from)"""
    u = f"https://www.duckdns.org/update?domains={domain.split('.')[0]}&token={token}&ip="
    r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "orderflow-terminal/1.0"}), timeout=20).read().decode().strip()
    if not r.startswith("OK"):
        raise RuntimeError("DuckDNS refused the update (wrong name or token)")


def _pid():
    try:
        p = int(open(PID).read().strip())
        os.kill(p, 0)
        return p
    except Exception:
        return 0


def running():
    return bool(_pid())


def stop():
    p = _pid()
    if p:
        try:
            os.kill(p, signal.SIGTERM)
        except Exception:
            pass
        time.sleep(1)


def start():
    with _lock:
        c = cfg()
        domain, token = _valid(c.get("domain"), c.get("token"))
        LAST["error"] = ""
        try:
            _download()
            os.makedirs(DIR, exist_ok=True)
            try:
                _duck_update(domain, token)
            except Exception as e:  # not fatal: the name may already point to us
                LAST["error"] = "DuckDNS update: " + str(e)[:120]
            open(CF, "w").write(caddyfile(domain, int(os.environ.get("PORT", "8000"))))
            if running():
                return True
            env = dict(os.environ, HOME=DIR, XDG_DATA_HOME=DIR, XDG_CONFIG_HOME=DIR, DUCKDNS_API_TOKEN=token)
            lg = open(LOG, "ab")
            p = subprocess.Popen([BIN, "run", "--config", CF, "--adapter", "caddyfile"], cwd=DIR, env=env, stdout=lg, stderr=lg, start_new_session=True)
            open(PID, "w").write(str(p.pid))
            return True
        except Exception as e:
            LAST["error"] = (type(e).__name__ + ": " + str(e))[:240]
            return False


def save(domain, token, on=True):
    c = cfg()
    d, t = _valid(domain, token or c.get("token"))
    store.kv_set("https_cfg", {"domain": d, "token": t, "on": bool(on)})
    stop()
    if on:
        threading.Thread(target=start, daemon=True).start()
    return status()


def disable():
    c = cfg()
    c["on"] = False
    store.kv_set("https_cfg", c)
    stop()
    return status()


def autostart():
    if cfg().get("on"):
        threading.Thread(target=start, daemon=True).start()


def log_tail(n=18):
    try:
        return "\n".join(open(LOG, errors="ignore").read().splitlines()[-n:])[-2500:]
    except Exception:
        return ""


def status():
    c = cfg()
    return {"on": bool(c.get("on")), "domain": c.get("domain", ""), "has_token": bool(c.get("token")), "running": running(),
            "url": f"https://{c['domain']}:{HTTPS_PORT}/app" if c.get("domain") else "", "port": HTTPS_PORT,
            "root": hasattr(os, "geteuid") and os.geteuid() == 0, "error": LAST["error"], "log": log_tail()}
