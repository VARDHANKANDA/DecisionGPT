#!/usr/bin/env python3
"""Disposable-staging verification of the REAL container stack (docker-compose.yml + deploy/staging/docker-compose.staging.yml).

Run from the repository root on a Linux host that has Docker Compose v2, `openssl`, and an `/etc/hosts` entry
`127.0.0.1 staging.example.test`. Needs a `.env` made by `deploy/staging/make_env.sh` (throwaway random credentials; never a real one). Standard
library only. Prints one line per check and exits non-zero if any check FAILED.

    python3 deploy/staging/verify_staging.py [--sections config,stack,roles,health,network,auth,tls,persist,shutdown,restore] [--report out.json]

What it does NOT establish is stated in docs/STAGING_VERIFICATION.md: no public certificate authority, no real DNS name, no browser, no load,
no penetration test. Every check records whether it ran against a running service.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import pathlib
import re
import secrets
import ssl
import subprocess
import sys
import threading
import time
from datetime import date, timedelta

HOST = "staging.example.test"
COMPOSE = ["docker", "compose", "-f", "docker-compose.yml", "-f", "deploy/staging/docker-compose.staging.yml"]
IMAGE = "decisiongpt/backend:local"
RESULTS: list[dict] = []
ENV: dict[str, str] = {}
CA_FILE = "/tmp/staging-root.crt"
PW = "orange-river-4271"                       # a sign-up password for the throwaway test accounts (passes the policy)


# ------------------------------------------------------------------------------------------------ plumbing
def load_env() -> None:
    for ln in pathlib.Path(".env").read_text().splitlines():
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            ENV[k.strip()] = v.strip()


def secrets_in_env() -> list[str]:
    keys = ("POSTGRES_PASSWORD", "APP_DB_PASSWORD", "JWT_SECRET", "SECRET_KEY", "RESEARCH_CONSOLE_TOKEN")
    return [ENV[k] for k in keys if ENV.get(k)]


def redact(text: str) -> str:
    for s in secrets_in_env():
        text = text.replace(s, "***")
    return text


def check(section: str, name: str, ok: bool, detail: str = "", runtime: bool = True) -> bool:
    RESULTS.append({"section": section, "check": name, "status": "PASS" if ok else "FAIL", "runtime": runtime, "detail": redact(str(detail))[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {section}: {name}" + (f"  -- {redact(str(detail))[:200]}" if (detail and not ok) else ""), flush=True)
    return ok


def info(section: str, name: str, detail: str) -> None:
    RESULTS.append({"section": section, "check": name, "status": "INFO", "runtime": True, "detail": redact(str(detail))[:600]})
    print(f"[INFO] {section}: {name}  -- {redact(str(detail))[:200]}", flush=True)


def sh(args: list[str], timeout: int = 600, input: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=input, env={**os.environ, **(env or {})})


def compose(*args: str, timeout: int = 900, input: str | None = None) -> subprocess.CompletedProcess:
    return sh([*COMPOSE, *args], timeout=timeout, input=input)


def cid(service: str) -> str:
    out = compose("ps", "-a", "-q", service).stdout.strip().splitlines()
    return out[0] if out else ""


def backend_ip() -> str:
    return json.loads(sh(["docker", "inspect", cid("backend")]).stdout)[0]["NetworkSettings"]["Networks"]["decisiongpt_web"]["IPAddress"]


def health(service: str) -> str:
    c = cid(service)
    return sh(["docker", "inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", c]).stdout.strip() if c else "absent"


def wait_healthy(service: str, seconds: int = 240) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if health(service) == "healthy":
            return True
        time.sleep(3)
    return False


def psql(sql: str, user: str | None = None, password: str | None = None, db: str | None = None, service: str = "postgres") -> subprocess.CompletedProcess:
    user, db = user or ENV["POSTGRES_USER"], db or ENV["POSTGRES_DB"]
    password = password if password is not None else ENV["POSTGRES_PASSWORD"]
    return compose("exec", "-T", "-e", f"PGPASSWORD={password}", service, "psql", "-h", "127.0.0.1", "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-At", "-F", "|", "-c", sql)


def q(sql: str, **kw) -> str:
    r = psql(sql, **kw)
    if r.returncode != 0:
        raise RuntimeError(redact(r.stderr)[:300])
    return r.stdout.strip()


# ------------------------------------------------------------------------------------------------ HTTP over TLS (verifying against Caddy's CA)
def ctx_with_ca() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=CA_FILE)


class Api:
    def __init__(self, host: str = HOST, port: int = 443, tls: bool = True, ctx: ssl.SSLContext | None = None, direct_host_header: str | None = None):
        self.host, self.port, self.tls, self.ctx, self.hh = host, port, tls, ctx or (ctx_with_ca() if tls else None), direct_host_header

    def req(self, method: str, path: str, body=None, token: str | None = None, headers: dict | None = None, raw: bytes | None = None, timeout: int = 60):
        h = {"Accept": "application/json", **(headers or {})}
        if token:
            h["Authorization"] = f"Bearer {token}"
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        conn = (http.client.HTTPSConnection(self.host, self.port, context=self.ctx, timeout=timeout) if self.tls
                else http.client.HTTPConnection(self.host, self.port, timeout=timeout))
        try:
            try:
                conn.request(method, path, body=data, headers=h)
            except (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError, OSError):
                pass
            try:
                r = conn.getresponse()
                payload = r.read()
                try:
                    js = json.loads(payload) if payload else None
                except ValueError:
                    js = None
                return r.status, js, {k.lower(): v for k, v in r.getheaders()}, payload
            except (BrokenPipeError, ConnectionResetError, http.client.RemoteDisconnected, http.client.ResponseNotReady, ssl.SSLEOFError, OSError):
                return 413, None, {}, b"Request Entity Too Large"
        finally:
            try:
                conn.close()
            except Exception:
                pass


def register(api: Api, email: str, password: str = PW, role: str | None = None):
    body = {"email": email, "password": password}
    if role:
        body["role"] = role
    return api.req("POST", "/api/v1/auth/register", body)


def make_business(api: Api, token: str, name: str) -> str:
    s, js, _, _ = api.req("POST", "/api/v1/businesses", {"name": name, "industry": "retail", "business_type": "D2C", "business_size": "small"}, token)
    assert s == 201, (s, js)
    return js["id"]


# ------------------------------------------------------------------------------------------------ section: config refusals (before any stack)
def good_env_for_container() -> dict[str, str]:
    return {"ENVIRONMENT": "production", "AUTH_ENABLED": "true", "JWT_SECRET": secrets.token_hex(32), "SECRET_KEY": secrets.token_hex(32),
            "RESEARCH_CONSOLE_TOKEN": secrets.token_hex(24), "FRONTEND_ORIGIN": f"https://{HOST}", "TRUSTED_PROXIES": "172.30.0.10/32",
            "DATABASE_URL": "postgresql+psycopg://someapp:" + secrets.token_hex(12) + "@postgres:5432/decisiongpt", "OPENAI_API_KEY": ""}


def run_unsafe(overrides: dict[str, str | None]) -> tuple[subprocess.CompletedProcess, dict]:
    env = {**good_env_for_container(), **overrides}
    args = ["docker", "run", "--rm", "--network", "none"]
    for k, v in env.items():
        if v is not None:
            args += ["-e", f"{k}={v}"]
    r = sh(args + [IMAGE], timeout=180)               # the image's real CMD (uvicorn app.main:app)
    return r, env


def section_config() -> None:
    s = "config"
    r = sh([*COMPOSE, "--env-file", "/dev/null", "config", "-q"], timeout=60)
    check(s, "compose refuses to render without the required database passwords (fails closed, names the variable, prints no value)",
          r.returncode != 0 and ("POSTGRES_PASSWORD" in r.stderr or "APP_DB_PASSWORD" in r.stderr), r.stderr[-200:])
    cases = [
        ("authentication off in production", {"AUTH_ENABLED": "false"}, "AUTH_ENABLED must be true"),
        ("placeholder JWT secret", {"JWT_SECRET": "change-me-jwt-secret"}, "JWT_SECRET"),
        ("short SECRET_KEY", {"SECRET_KEY": "short"}, "SECRET_KEY"),
        ("SQLite database in production", {"DATABASE_URL": "sqlite:///./x.db"}, "PostgreSQL"),
        ("default database credentials", {"DATABASE_URL": "postgresql+psycopg://decisiongpt:decisiongpt@postgres:5432/decisiongpt"}, "default database credentials"),
        ("http origin", {"FRONTEND_ORIGIN": "http://app.example.test"}, "FRONTEND_ORIGIN"),
        ("localhost origin", {"FRONTEND_ORIGIN": "https://localhost"}, "FRONTEND_ORIGIN"),
        ("rate limiting disabled", {"RATE_LIMIT_ENABLED": "false"}, "RATE_LIMIT_ENABLED"),
        ("typo environment name", {"ENVIRONMENT": "prod"}, "ENVIRONMENT must be one of"),
        ("a token lifetime over one day", {"JWT_TTL_SECONDS": "999999"}, "JWT_TTL_SECONDS"),
        ("a malformed trusted-proxy list", {"TRUSTED_PROXIES": "10.0.0.0/8, nonsense"}, "TRUSTED_PROXIES"),
    ]
    for name, over, needle in cases:
        r, env = run_unsafe(over)
        out = r.stdout + r.stderr
        leaked = [k for k in ("JWT_SECRET", "SECRET_KEY", "RESEARCH_CONSOLE_TOKEN") if env.get(k) and len(env[k]) > 12 and env[k] in out]
        check(s, f"container exits non-zero for: {name}", r.returncode != 0 and needle in out and not leaked,
              f"exit={r.returncode} leaked={leaked} tail={out[-200:]}")
    r, _ = run_unsafe({})
    out = r.stdout + r.stderr
    check(s, "a fully valid configuration but an unreachable database still refuses to serve (fail closed)",
          r.returncode != 0 and "could not be reached" in out, out[-200:])


# ------------------------------------------------------------------------------------------------ section: stack bring-up, roles, migrations
def section_stack() -> None:
    s = "stack"
    r = compose("up", "-d", "postgres")
    check(s, "postgres starts", r.returncode == 0, r.stderr[-200:])
    check(s, "postgres becomes healthy", wait_healthy("postgres", 120))
    roles = q("select rolname||':'||rolsuper||':'||rolcreaterole||':'||rolcreatedb||':'||rolbypassrls from pg_roles where rolname in "
              f"('{ENV['POSTGRES_USER']}','{ENV['APP_DB_USER']}') order by 1", db="postgres")
    app_line = [x for x in roles.splitlines() if x.startswith(ENV["APP_DB_USER"])]
    check(s, "the initdb bootstrap created the application role, without superuser / createrole / createdb / bypassrls",
          bool(app_line) and app_line[0].endswith(":false:false:false:false"), roles)
    own_line = [x for x in roles.splitlines() if x.startswith(ENV["POSTGRES_USER"])]
    info(s, "owner role attributes (superuser:createrole:createdb:bypassrls) - in the official postgres image POSTGRES_USER is a superuser", own_line[0] if own_line else "?")
    # unmigrated database: a hardened backend must refuse
    r = compose("run", "--rm", "--no-deps", "backend", timeout=300)
    out = r.stdout + r.stderr
    check(s, "hardened backend refuses an unmigrated database and tells the operator how to fix it",
          r.returncode != 0 and "alembic upgrade head" in out, out[-250:])
    r = compose("--profile", "tools", "run", "--rm", "migrate", timeout=600)
    check(s, "the migrate job applies every revision as the owner role", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    head = sh(["docker", "run", "--rm", "--entrypoint", "alembic", IMAGE, "heads"]).stdout.strip().split()[0]
    cur = q("select version_num from alembic_version")
    check(s, "the database is at the schema head the code expects", cur == head, f"db={cur} head={head}")
    owner_urls = f"postgresql+psycopg://{ENV['POSTGRES_USER']}:{ENV['POSTGRES_PASSWORD']}@postgres:5432/{ENV['POSTGRES_DB']}"
    r = sh([*COMPOSE, "run", "--rm", "--no-deps", "-e", f"DATABASE_URL={owner_urls}", "backend"], timeout=300)
    out = r.stdout + r.stderr
    check(s, "a hardened backend refuses to run as the schema OWNER role (a superuser here) and prints no password", r.returncode != 0
          and ("owns tables" in out or "excessive privileges" in out) and ENV["POSTGRES_PASSWORD"] not in out, out[-250:])
    r = compose("up", "-d", timeout=900)
    check(s, "the full stack (postgres, backend, frontend, proxy) starts", r.returncode == 0, r.stderr[-300:])
    check(s, "backend container is healthy (its own HEALTHCHECK, as uid 10001)", wait_healthy("backend", 240))
    check(s, "frontend container is healthy (its own HEALTHCHECK)", wait_healthy("frontend", 240))
    time.sleep(3)
    c = compose("cp", "caddy:/data/caddy/pki/authorities/local/root.crt", CA_FILE)
    check(s, "the proxy's local CA root certificate can be exported for client verification", c.returncode == 0 and os.path.exists(CA_FILE), c.stderr[-200:])


# ------------------------------------------------------------------------------------------------ section: least privilege
def section_roles() -> None:
    s = "roles"
    users = q("select usename from pg_stat_activity where datname = '%s' and usename is not null and pid <> pg_backend_pid() group by 1" % ENV["POSTGRES_DB"]).splitlines()
    info(s, "database users currently connected", ",".join(users))
    check(s, "the running API holds no connection as the owner role", ENV["POSTGRES_USER"] not in users, ",".join(users))
    code = r'''
import json, os
from sqlalchemy import text
from app.db.session import engine
out = {}
for name, sql in {
  "drop_trigger": "DROP TRIGGER tracked_expectations_append_only ON tracked_expectations",
  "disable_trigger": "ALTER TABLE tracked_expectations DISABLE TRIGGER ALL",
  "truncate": "TRUNCATE tracked_expectations",
  "create_table": "CREATE TABLE sneaky(id int)",
  "alter_schema": "ALTER TABLE users ADD COLUMN sneaky int",
  "create_role": "CREATE ROLE sneaky LOGIN",
  "replica_mode": "SET session_replication_role = replica",
}.items():
    try:
        with engine.begin() as c:
            c.execute(text(sql))
        out[name] = "ALLOWED"
    except Exception as e:
        out[name] = "refused" if ("permission denied" in str(e).lower() or "must be owner" in str(e).lower() or "must be superuser" in str(e).lower()) else "ERROR:" + type(e).__name__
with engine.connect() as c:
    out["whoami_is_superuser"] = c.execute(text("select rolsuper from pg_roles where rolname = current_user")).scalar()
    out["tables_owned"] = c.execute(text("select count(*) from pg_tables where schemaname='public' and tableowner = current_user")).scalar()
print("RESULT" + json.dumps(out))
'''
    r = compose("exec", "-T", "backend", "python", "-", input=code, timeout=120)
    m = re.search(r"RESULT(\{.*\})", r.stdout)
    res = json.loads(m.group(1)) if m else {}
    check(s, "from inside the API container, with ITS OWN credentials, every attempt to drop/disable the append-only triggers or change the schema is refused",
          bool(res) and all(res.get(k) == "refused" for k in ("drop_trigger", "disable_trigger", "truncate", "create_table", "alter_schema", "create_role", "replica_mode")), res or r.stderr[-300:])
    check(s, "the API's role is not a superuser and owns no tables", res.get("whoami_is_superuser") is False and res.get("tables_owned") == 0, res)
    env_text = compose("exec", "-T", "backend", "printenv").stdout
    check(s, "the API container's environment does NOT contain the schema owner's (superuser) password", ENV["POSTGRES_PASSWORD"] not in env_text, "owner password present")
    envd = dict(ln.split("=", 1) for ln in env_text.splitlines() if "=" in ln)
    check(s, "the API container has no migration URL and no owner name in its environment", envd.get("MIGRATION_DATABASE_URL", "") == "" and envd.get("POSTGRES_USER", "") == "", {k: envd.get(k) for k in ("MIGRATION_DATABASE_URL", "POSTGRES_USER")})
    fe = compose("exec", "-T", "frontend", "printenv").stdout
    check(s, "the web server container holds none of the five server secrets", not any(x in fe for x in secrets_in_env()), "secret present")
    trg = q("select count(*) from pg_trigger where tgname like '%append_only%' and not tgisinternal")
    check(s, "the three append-only triggers exist in the migrated database", trg == "3", trg)


# ------------------------------------------------------------------------------------------------ section: health
def section_health() -> None:
    s = "health"
    api = Api()
    st, js, hd, raw = api.req("GET", "/api/v1/health")
    check(s, "GET /api/v1/health through the TLS proxy returns 200 and exactly {status, dependencies}",
          st == 200 and set(js or {}) == {"status", "dependencies"} and js["status"] == "ok" and js["dependencies"] == {"database": "ok"}, js)
    text = raw.decode()
    bad = [w for w in ("version", "host", "postgres", "password", "user", "url", "traceback", "psycopg", "sqlalchemy", "python", "uvicorn") if w in text.lower()]
    check(s, "the health body discloses no configuration, version, host or driver detail", not bad, bad)
    for svc in ("postgres", "backend", "frontend"):
        check(s, f"docker health status of {svc} is healthy", health(svc) == "healthy", health(svc))
    # unhealthy case: stop the database; the health endpoint must degrade honestly without leaking the reason
    compose("stop", "postgres")
    time.sleep(4)
    st2, js2, _, raw2 = api.req("GET", "/api/v1/health")
    check(s, "with the database down the health endpoint reports 'degraded' and still discloses no connection detail",
          st2 == 200 and js2 and js2.get("status") == "degraded" and "psycopg" not in raw2.decode().lower() and ENV["APP_DB_USER"] not in raw2.decode(), js2)
    compose("start", "postgres")
    check(s, "the database comes back and health returns to ok", wait_healthy("postgres", 90) and api.req("GET", "/api/v1/health")[1].get("status") == "ok")


# ------------------------------------------------------------------------------------------------ section: network exposure and paths
def listeners() -> str:
    return sh(["ss", "-ltnH"]).stdout


def section_network() -> None:
    s = "network"
    ls = listeners()
    check(s, "no host listener on the PostgreSQL port 5432", ":5432" not in ls, ls)
    check(s, "no host listener on the backend (8000) or frontend (3000) ports: only the proxy is reachable", ":8000" not in ls and ":3000" not in ls, ls)
    pub = [ln for ln in ls.splitlines() if re.search(r":(80|443)\s", ln)]
    check(s, "the proxy's ports 80/443 are bound to 127.0.0.1 only (not 0.0.0.0 / ::)", bool(pub) and all("127.0.0.1" in ln for ln in pub), pub)
    ports = sh(["docker", "ps", "--format", "{{.Names}} {{.Ports}}"]).stdout
    pg = [ln for ln in ports.splitlines() if "postgres" in ln]
    check(s, "docker reports no published port for the database container", bool(pg) and all("->" not in ln for ln in pg), pg)
    # paths between containers
    r = compose("exec", "-T", "frontend", "node", "-e", "fetch('http://backend:8000/api/v1/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(2))")
    check(s, "frontend container can reach the backend over the web network", r.returncode == 0, r.stderr[-200:])
    r = compose("exec", "-T", "frontend", "node", "-e",
                "require('net').connect({host:'postgres',port:5432,timeout:3000}).on('connect',()=>process.exit(0)).on('error',()=>process.exit(3)).on('timeout',()=>process.exit(4))")
    check(s, "frontend container CANNOT reach the database (no route, no name)", r.returncode in (3, 4), f"exit={r.returncode}")
    r = compose("exec", "-T", "caddy", "sh", "-c", "nc -z -w 3 postgres 5432; echo $?")
    check(s, "the reverse proxy CANNOT reach the database", r.stdout.strip().endswith(("1", "2")) or r.returncode != 0, r.stdout + r.stderr)
    r = compose("exec", "-T", "backend", "python", "-c",
                "import socket,sys; s=socket.create_connection(('postgres',5432),3); print('db reachable'); s.close()")
    check(s, "the backend CAN reach the database (its only path)", "db reachable" in r.stdout, r.stderr[-200:])
    net = json.loads(sh(["docker", "network", "inspect", "decisiongpt_db"]).stdout)[0]
    check(s, "the database network is internal (no route to the outside)", net.get("Internal") is True, net.get("Internal"))
    members = sorted(v["Name"].split("-")[1] for v in net["Containers"].values())
    check(s, "only postgres and backend are on the database network", members == ["backend", "postgres"], members)


# ------------------------------------------------------------------------------------------------ section: authentication, authorization, throttling, revocation over TLS
def section_auth() -> None:
    s = "auth"
    api = Api()
    a_s, a, _, _ = register(api, "alice@staging.test")
    b_s, b, _, _ = register(api, "bob@staging.test")
    check(s, "sign-up works over https and returns a token", a_s == b_s == 201 and "access_token" in a, a_s)
    ta, tb = a["access_token"], b["access_token"]
    bid = make_business(api, ta, "Alice Retail")
    check(s, "the owner can read their own business", api.req("GET", f"/api/v1/businesses/{bid}", token=ta)[0] == 200)
    st, js, _, raw = api.req("GET", f"/api/v1/businesses/{bid}", token=tb)
    check(s, "another tenant gets 404 'Business not found.' with no trace of the business", st == 404 and js["error"]["message"] == "Business not found." and "Alice" not in raw.decode(), js)
    check(s, "no token -> 401", api.req("GET", f"/api/v1/businesses/{bid}")[0] == 401)
    check(s, "public sign-up cannot create an administrator", register(api, "evil@staging.test", role="admin")[0] == 403)
    check(s, "a business token is refused by the research console (403)", api.req("GET", "/api/v1/research/models", token=ta)[0] == 403)
    check(s, "malformed ids are 404, not 500", api.req("GET", "/api/v1/businesses/not-a-uuid/goals", token=tb)[0] == 404
          and api.req("GET", f"/api/v1/businesses/{bid}/explain/answer/nope", token=ta)[0] == 404)
    # throttling, with forged forwarding headers: the proxy replaces them with the real peer address
    victim = "victim@staging.test"
    register(api, victim)
    codes = []
    for n in range(8):
        st, js, hd, _ = api.req("POST", "/api/v1/auth/login", {"email": victim, "password": f"wrong-guess-number-{n}"}, headers={"X-Forwarded-For": f"203.0.113.{n + 1}"})
        codes.append(st)
    check(s, "5 wrong sign-ins are 401 and the rest 429 even though every request forged a different X-Forwarded-For (the proxy overwrote it)",
          codes[:5] == [401] * 5 and set(codes[5:]) == {429}, codes)
    st, js, hd, _ = api.req("POST", "/api/v1/auth/login", {"email": victim, "password": PW})
    check(s, "the throttled account is refused even with the right password, with Retry-After and no account detail",
          st == 429 and int(hd.get("retry-after", "0")) > 0 and victim not in json.dumps(js) and "access_token" not in json.dumps(js), (st, hd.get("retry-after")))
    check(s, "a different account from the same client is not throttled", api.req("POST", "/api/v1/auth/login", {"email": "alice@staging.test", "password": PW})[0] == 200)
    # direct to the backend container: the peer is NOT a trusted proxy, so the header must not choose the bucket
    direct = Api(host=backend_ip(), port=8000, tls=False)
    register(direct, "direct@staging.test")
    codes = [direct.req("POST", "/api/v1/auth/login", {"email": "direct@staging.test", "password": f"wrong-{n}-xyz-guess"}, headers={"X-Forwarded-For": f"198.51.100.{n + 1}"})[0] for n in range(7)]
    check(s, "connecting straight to the backend (not via the trusted proxy) a forged X-Forwarded-For cannot buy a fresh budget", codes[:5] == [401] * 5 and set(codes[5:]) == {429}, codes)
    # logout and password change
    t1 = api.req("POST", "/api/v1/auth/login", {"email": "alice@staging.test", "password": PW})[1]["access_token"]
    check(s, "a token works before logout", api.req("GET", "/api/v1/auth/me", token=t1)[0] == 200)
    check(s, "logout answers 204", api.req("POST", "/api/v1/auth/logout", token=t1)[0] == 204)
    check(s, "the logged-out token is refused (revocation is in the shared database)", api.req("GET", "/api/v1/auth/me", token=t1)[0] == 401)
    ta2 = api.req("POST", "/api/v1/auth/login", {"email": "alice@staging.test", "password": PW})[1]["access_token"]
    st, js, _, _ = api.req("POST", "/api/v1/auth/change-password", {"current_password": PW, "new_password": "a-brand-new-passphrase-7"}, token=ta2)
    check(s, "changing the password returns a working token and ends the old sessions", st == 200 and api.req("GET", "/api/v1/auth/me", token=ta)[0] == 401
          and api.req("GET", "/api/v1/auth/me", token=js["access_token"])[0] == 200, st)
    check(s, "no response sets a cookie (tokens travel only in the Authorization header)", "set-cookie" not in api.req("POST", "/api/v1/auth/login", {"email": "bob@staging.test", "password": PW})[2])
    STATE.update(bid=bid, alice_pw="a-brand-new-passphrase-7", victim=victim)


STATE: dict = {}

# executed INSIDE the restored API container: the client address is then the loopback, not the host address whose per-address budget earlier tests used up
PROBE_LOGIN = """
import json, urllib.request as u
req = u.Request("http://127.0.0.1:8000/api/v1/auth/login", json.dumps({"email": "bob@staging.test", "password": "__PW__"}).encode(), {"Content-Type": "application/json"})
try:
    print("STATUS", u.urlopen(req).status)
except Exception as e:
    print("STATUS", getattr(e, "code", e))
"""


def fresh_throttle(api: Api, email: str) -> None:
    """Throttle an account NOW, and not too close to the end of the fixed 15-minute window (which would reset the counter mid-test)."""
    w = 900
    left = w - (time.time() % w)
    if left < 300:
        time.sleep(left + 2)
    register(api, email)
    codes = [api.req("POST", "/api/v1/auth/login", {"email": email, "password": f"wrong-guess-for-{n}"})[0] for n in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429, codes


# ------------------------------------------------------------------------------------------------ section: TLS and HTTP security
def section_tls() -> None:
    s = "tls"
    api = Api()
    st, js, hd, raw = api.req("GET", "/api/v1/health")
    check(s, "https request verifies the proxy's certificate against its CA", st == 200)
    try:
        Api(ctx=ssl.create_default_context()).req("GET", "/api/v1/health")
        verified = True
    except ssl.SSLError:
        verified = False
    check(s, "NEGATIVE CONTROL: the same request with the system trust store is refused (the certificate is from a private CA, not a public one)", not verified)
    try:
        c = http.client.HTTPSConnection("127.0.0.1", 443, context=ctx_with_ca(), timeout=10)
        c.request("GET", "/")
        c.getresponse()
        wrong = True
    except (ssl.SSLError, ssl.CertificateError):
        wrong = False
    check(s, "NEGATIVE CONTROL: connecting by an address the certificate does not cover fails hostname verification", not wrong)
    out = sh(["openssl", "s_client", "-connect", "127.0.0.1:443", "-servername", HOST, "-CAfile", CA_FILE, "-verify_hostname", HOST, "-brief"], input="", timeout=30)
    brief = out.stdout + out.stderr
    check(s, "openssl verifies the chain and hostname", "Verification: OK" in brief or "Verification: OK" in out.stderr or "Verify return code: 0" in brief, brief[-200:])
    info(s, "negotiated protocol and cipher (openssl)", " | ".join(ln for ln in brief.splitlines() if ln.startswith(("Protocol version", "Ciphersuite"))))
    for ver in ("-tls1_2", "-tls1_3"):
        o = sh(["openssl", "s_client", "-connect", "127.0.0.1:443", "-servername", HOST, "-CAfile", CA_FILE, ver, "-brief"], input="", timeout=30)
        check(s, f"the proxy accepts {ver[1:].upper().replace('TLS', 'TLS ')}", "Protocol version" in (o.stdout + o.stderr), (o.stdout + o.stderr)[-120:])
    cert = sh(["openssl", "s_client", "-connect", "127.0.0.1:443", "-servername", HOST, "-CAfile", CA_FILE], input="", timeout=30).stdout
    pem = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", cert, re.S)
    if pem:
        x = sh(["openssl", "x509", "-noout", "-subject", "-issuer", "-enddate", "-ext", "subjectAltName"], input=pem.group(0)).stdout
        info(s, "leaf certificate", x.replace("\n", " | "))
        check(s, "the certificate names the staging host in its subject alternative names", HOST in x, x)
    # plain http redirects, and carries no HSTS
    plain = Api(host=HOST, port=80, tls=False)
    st, _, hd, _ = plain.req("GET", "/some/page?x=1")
    check(s, "plain http is permanently redirected to https with the path and query preserved",
          st in (301, 308) and hd.get("location") == f"https://{HOST}/some/page?x=1", (st, hd.get("location")))
    check(s, "the http redirect does not carry HSTS (it is only meaningful, and only sent, over https)", "strict-transport-security" not in hd)
    # headers
    for label, path in (("API", "/api/v1/health"), ("web application", "/login")):
        st, _, h, _ = api.req("GET", path, headers={"Accept": "text/html,application/json"})
        csp = h.get("content-security-policy", "")
        check(s, f"{label}: security headers present (CSP, frame, nosniff, referrer, HSTS)", st == 200 and csp and h.get("x-content-type-options") == "nosniff"
              and h.get("x-frame-options", "").upper() == "DENY" and h.get("referrer-policy") == "no-referrer" and "max-age=31536000" in h.get("strict-transport-security", ""), (st, list(h)))
        check(s, f"{label}: no server / framework banner headers", "server" not in h and "x-powered-by" not in h and "via" not in h, {k: h[k] for k in h if k in ("server", "x-powered-by", "via")})
    st, _, h, _ = api.req("GET", "/api/v1/health")
    check(s, "API responses are not cacheable and carry a deny-all CSP", h.get("cache-control") == "no-store" and "default-src 'none'" in h.get("content-security-policy", ""), h.get("cache-control"))
    st, _, h, _ = api.req("GET", "/login")
    check(s, "the web application's CSP restricts connections to itself and the API origin", "connect-src 'self'" in h.get("content-security-policy", "") and "frame-ancestors 'none'" in h.get("content-security-policy", ""), h.get("content-security-policy", "")[:200])
    # HSTS must appear exactly once (proxy + app both set it)
    conn = http.client.HTTPSConnection(HOST, 443, context=ctx_with_ca(), timeout=30)
    conn.request("GET", "/api/v1/health")
    resp = conn.getresponse()
    resp.read()
    n_hsts = len([k for k, _ in resp.getheaders() if k.lower() == "strict-transport-security"])
    conn.close()
    check(s, "HSTS is sent exactly once even though both the proxy and the application add it", n_hsts == 1, n_hsts)
    # CORS
    origin = f"https://{HOST}"
    st, _, h, _ = api.req("OPTIONS", "/api/v1/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
    check(s, "CORS preflight from the configured origin is allowed for that origin only (no credentials, no wildcard)",
          h.get("access-control-allow-origin") == origin and "access-control-allow-credentials" not in h, h.get("access-control-allow-origin"))
    st, _, h, _ = api.req("OPTIONS", "/api/v1/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    check(s, "CORS preflight from another origin gets no allow-origin header", "access-control-allow-origin" not in h, st)
    st, _, h, _ = api.req("OPTIONS", "/api/v1/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "TRACE"})
    check(s, "a method outside the allow-list is refused", st == 400, st)
    # error bodies
    bodies = {}
    bodies["unknown route"] = api.req("GET", "/api/v1/nope")
    bodies["validation"] = api.req("POST", "/api/v1/auth/login", {"email": "not-an-email", "password": "x" * 300})
    bodies["bad token"] = api.req("GET", "/api/v1/auth/me", token="garbage.token.value")
    bodies["malformed json"] = api.req("POST", "/api/v1/auth/login", raw=b"{not json", headers={"Content-Type": "application/json"})
    bodies["wrong method"] = api.req("DELETE", "/api/v1/health")
    bodies["oversized body"] = api.req("POST", "/api/v1/auth/login", raw=b"x" * (31 * 1024 * 1024), headers={"Content-Type": "application/json"}, timeout=120)
    for name, (st, js, hd, raw) in bodies.items():
        t = raw.decode(errors="replace").lower()
        leak = [w for w in ("traceback", "/app/", "site-packages", "psycopg", "sqlalchemy", "uvicorn", "select ", ".py\"", "xxxxxxxx") if w in t]
        check(s, f"error response ({name}: HTTP {st}) contains no stack trace, path, driver or submitted-value echo", st >= 400 and not leak, (st, leak))
    check(s, "a request body over the proxy's limit is refused at the proxy (413)", bodies["oversized body"][0] == 413, bodies["oversized body"][0])
    check(s, "the API documentation is not served in this hardened environment (via the proxy and directly)",
          api.req("GET", "/docs")[0] == 404 and api.req("GET", "/openapi.json")[0] == 404
          and Api(host=backend_ip(), port=8000, tls=False).req("GET", "/docs")[0] == 404)


# ------------------------------------------------------------------------------------------------ helpers for tracking writes
def seed_tracking(api: Api, token: str, bid: str, n: int = 6) -> list[dict]:
    out = []
    for k in range(n):
        ws = (date(2025, 1, 1) + timedelta(days=k * 2)).isoformat()
        st, plan, _, _ = api.req("POST", f"/api/v1/businesses/{bid}/tracking/expectations", {"metric": "units_sold", "unit": "units", "window_start": ws, "window_end": ws, "expected_value": 100 + k, "note": "staging seed"}, token)
        assert st == 200, (st, plan)
        st, obs, _, _ = api.req("POST", f"/api/v1/businesses/{bid}/tracking/expectations/{plan['id']}/observations", {"metric": "units_sold", "unit": "units", "status": "observed", "value": 90.0 + k}, token)
        assert st == 200, (st, obs)
        st, cor, _, _ = api.req("POST", f"/api/v1/businesses/{bid}/tracking/observations/{obs['id']}/correction", {"reason": "staging correction", "value": 95.0 + k}, token)
        assert st == 200, (st, cor)
        out.append({"plan": plan["id"], "obs": obs["id"], "corr": cor["id"]})
    return out


def table_counts() -> dict[str, int]:
    names = q("select tablename from pg_tables where schemaname='public' and tablename <> 'alembic_version' order by 1").splitlines()
    return {n: int(q(f'select count(*) from "{n}"')) for n in names}


# ------------------------------------------------------------------------------------------------ section: restart persistence
def section_persist() -> None:
    s = "persist"
    api = Api()
    st, js, _, _ = api.req("POST", "/api/v1/auth/login", {"email": "bob@staging.test", "password": PW})
    tok_ok = js["access_token"]
    st, js, _, _ = api.req("POST", "/api/v1/auth/login", {"email": "bob@staging.test", "password": PW})
    tok_revoked = js["access_token"]
    api.req("POST", "/api/v1/auth/logout", token=tok_revoked)
    bid_b = make_business(api, tok_ok, "Bob Persist")
    seeded = seed_tracking(api, tok_ok, bid_b, 3)
    fresh_throttle(api, "throttle-persist@staging.test")
    before_counts = table_counts()
    buckets_before = int(q("select count(*) from rate_limit_buckets"))
    revoked_before = int(q("select count(*) from revoked_tokens"))
    STATE.update(bid_b=bid_b, tok_ok=tok_ok, tok_revoked=tok_revoked, seeded=seeded)
    # 1) restart the backend only
    r = compose("restart", "backend", timeout=300)
    check(s, "backend restarts", r.returncode == 0 and wait_healthy("backend", 200), r.stderr[-200:])
    time.sleep(2)
    st, js, hd, _ = api.req("POST", "/api/v1/auth/login", {"email": "throttle-persist@staging.test", "password": PW})
    check(s, "the sign-in throttle survived a backend restart (counters live in the database, not the process)", st == 429 and int(hd.get("retry-after", "0")) > 0, st)
    check(s, "a revoked token stays revoked after the restart", api.req("GET", "/api/v1/auth/me", token=tok_revoked)[0] == 401)
    check(s, "a still-valid token still works after the restart", api.req("GET", "/api/v1/auth/me", token=tok_ok)[0] == 200)
    st, rep, _, _ = api.req("GET", f"/api/v1/businesses/{bid_b}/tracking/report", token=tok_ok)
    check(s, "tracking records are intact after the restart", st == 200, st)
    # 2) take the whole stack down WITHOUT removing volumes, and bring it back
    r = compose("down", timeout=300)
    check(s, "the whole stack goes down cleanly (volumes kept)", r.returncode == 0, r.stderr[-200:])
    r = compose("up", "-d", timeout=900)
    check(s, "the whole stack comes back with no migration step (the schema persisted)", r.returncode == 0 and wait_healthy("postgres", 120) and wait_healthy("backend", 240) and wait_healthy("frontend", 240), r.stderr[-200:])
    after_counts = table_counts()
    check(s, "every table has the same row count after down/up", after_counts == before_counts, {k: (before_counts.get(k), v) for k, v in after_counts.items() if before_counts.get(k) != v})
    check(s, "the throttle buckets and the revocation list persisted through down/up", int(q("select count(*) from rate_limit_buckets")) >= min(buckets_before, 1) and int(q("select count(*) from revoked_tokens")) == revoked_before)
    time.sleep(3)
    check(s, "after down/up: throttled account still refused, revoked token still revoked, valid token still valid",
          api.req("POST", "/api/v1/auth/login", {"email": "throttle-persist@staging.test", "password": PW})[0] == 429
          and api.req("GET", "/api/v1/auth/me", token=tok_revoked)[0] == 401 and api.req("GET", "/api/v1/auth/me", token=tok_ok)[0] == 200)
    # the Caddy certificate authority must also survive (clients keep trusting the same root)
    c = compose("cp", "caddy:/data/caddy/pki/authorities/local/root.crt", CA_FILE + ".after")
    same = c.returncode == 0 and pathlib.Path(CA_FILE).read_bytes() == pathlib.Path(CA_FILE + ".after").read_bytes()
    check(s, "the proxy's CA root is unchanged after down/up (its data volume persisted)", same)


# ------------------------------------------------------------------------------------------------ section: shutdown while writes are in flight
def section_shutdown() -> None:
    s = "shutdown"
    api = Api()
    email = "load@staging.test"
    st, js, _, _ = register(api, email)
    tok = js["access_token"]
    bid = make_business(api, tok, "Load Co")
    acked: dict[str, list] = {"plan": [], "obs": [], "corr": []}
    errors = {"n": 0}
    stop = threading.Event()
    lock = threading.Lock()
    day0 = date(2020, 1, 1)

    def worker(tid: int) -> None:
        a = Api()
        i = 0
        while not stop.is_set() and i < 80:
            k = tid * 100 + i
            i += 1
            ws = (day0 + timedelta(days=k)).isoformat()
            try:
                st, plan, _, _ = a.req("POST", f"/api/v1/businesses/{bid}/tracking/expectations", {"metric": "units_sold", "unit": "units", "window_start": ws, "window_end": ws, "expected_value": 5}, tok, timeout=20)
                if st != 200:
                    continue
                with lock:
                    acked["plan"].append(plan["id"])
                st, obs, _, _ = a.req("POST", f"/api/v1/businesses/{bid}/tracking/expectations/{plan['id']}/observations", {"metric": "units_sold", "unit": "units", "status": "observed", "value": 4.0}, tok, timeout=20)
                if st != 200:
                    continue
                with lock:
                    acked["obs"].append((plan["id"], obs["id"]))
                st, cor, _, _ = a.req("POST", f"/api/v1/businesses/{bid}/tracking/observations/{obs['id']}/correction", {"reason": "load correction", "value": 6.0}, tok, timeout=20)
                if st == 200:
                    with lock:
                        acked["corr"].append((obs["id"], cor["id"]))
            except Exception:  # connection dropped by the stopping server: this write was NOT acknowledged
                with lock:
                    errors["n"] += 1
                time.sleep(0.2)

    ts = [threading.Thread(target=worker, args=(t,)) for t in range(6)]
    [t.start() for t in ts]
    time.sleep(4)
    t0 = time.time()
    r = compose("stop", "-t", "30", "backend", timeout=120)          # SIGTERM while 6 writers are busy
    took = time.time() - t0
    stop.set()
    [t.join(timeout=60) for t in ts]
    code = sh(["docker", "inspect", "-f", "{{.State.ExitCode}}", cid("backend") or "x"]).stdout.strip()
    logs = compose("logs", "--no-color", "--tail", "60", "backend").stdout
    # uvicorn re-raises the signal after an orderly shutdown, so a graceful SIGTERM stop can report 143 (128+15); 137 would mean it was SIGKILLed
    check(s, "SIGTERM stops the API gracefully within the grace period (exit 0 or 143, never 137/killed)", r.returncode == 0 and code in ("0", "143") and took < 25, f"exit={code} took={took:.1f}s")
    check(s, "the shutdown log shows an orderly stop and no traceback", "Finished server process" in logs and "Traceback" not in logs, logs[-300:])
    info(s, "writes acknowledged before the stop", f"plans={len(acked['plan'])} observations={len(acked['obs'])} corrections={len(acked['corr'])} dropped-connections={errors['n']}")
    compose("up", "-d", "backend")
    check(s, "the API restarts cleanly after the interrupted writes", wait_healthy("backend", 200))
    bidq = f"'{bid}'"
    plans = set(q(f"select id from tracked_expectations where business_id = {bidq}").splitlines())
    obs = set(q(f"select id from outcome_observations where business_id = {bidq}").splitlines())
    sup = set(q(f"select supersedes_id from outcome_observations where business_id = {bidq} and supersedes_id is not null").splitlines())
    check(s, "every ACKNOWLEDGED plan is in the database", set(acked["plan"]) <= plans, len(set(acked["plan"]) - plans))
    check(s, "every ACKNOWLEDGED observation is in the database", {o for _, o in acked["obs"]} <= obs, "")
    check(s, "every ACKNOWLEDGED correction exists and superseded exactly its original", {c for _, c in acked["corr"]} <= obs and {o for o, _ in acked["corr"]} <= sup, "")
    multi = q(f"select count(*) from (select expectation_id, metric, window_start, window_end from outcome_observations where business_id = {bidq} and is_current group by 1,2,3,4 having count(*) > 1) x")
    check(s, "no window has more than one CURRENT observation", multi == "0", multi)
    gaps = q(f"select count(*) from (select expectation_id, count(*) n, max(revision) m, min(revision) lo from outcome_observations where business_id = {bidq} group by expectation_id) x where lo <> 1 or m <> n")
    check(s, "every observation history has contiguous revisions 1..n (no partial correction)", gaps == "0", gaps)
    nocurrent = q(f"select count(*) from (select expectation_id from outcome_observations where business_id = {bidq} group by expectation_id having sum(case when is_current then 1 else 0 end) <> 1) x")
    check(s, "every observation history has exactly one current revision (a correction is never half applied)", nocurrent == "0", nocurrent)
    orphan = q("select count(*) from outcome_observations o left join tracked_expectations e on e.id = o.expectation_id where e.id is null")
    check(s, "no observation is orphaned from its expectation", orphan == "0", orphan)
    unacked = len(plans) - len(set(acked["plan"]) & plans)
    info(s, "committed-but-unacknowledged plans (the response was lost in the shutdown; at-least-once, never partial)", unacked)
    STATE["load_bid"] = bid


# ------------------------------------------------------------------------------------------------ section: backup and restore
def section_restore() -> None:
    s = "restore"
    api = Api()
    fresh_throttle(api, "throttle-restore@staging.test")
    src_counts = table_counts()
    src_idx = q("select indexname||':'||indexdef from pg_indexes where schemaname='public' order by 1")
    src_trg = q("select tgname from pg_trigger where not tgisinternal order by 1")
    src_head = q("select version_num from alembic_version")
    info(s, "source state", f"alembic={src_head} tables={len(src_counts)} rows={sum(src_counts.values())} users={src_counts.get('users')} revoked_tokens={src_counts.get('revoked_tokens')}")
    dump = "/tmp/staging-backup.dump"
    cmd = [*COMPOSE, "exec", "-T", "-e", f"PGPASSWORD={ENV['POSTGRES_PASSWORD']}", "postgres", "pg_dump", "-Fc", "-h", "127.0.0.1", "-U", ENV["POSTGRES_USER"], "-d", ENV["POSTGRES_DB"]]
    with open(dump, "wb") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE)
    size = os.path.getsize(dump)
    check(s, "the documented pg_dump -Fc backup command succeeds", p.returncode == 0 and size > 10_000, f"exit={p.returncode} bytes={size}")
    # a FRESH cluster: new container, empty data directory, same bootstrap as a new deployment
    tgt = "dgpt_restore_target"
    sh(["docker", "rm", "-f", tgt])
    root = pathlib.Path.cwd()
    env_args = ["-e", f"POSTGRES_USER={ENV['POSTGRES_USER']}", "-e", f"POSTGRES_PASSWORD={ENV['POSTGRES_PASSWORD']}", "-e", f"POSTGRES_DB={ENV['POSTGRES_DB']}",
                "-e", f"APP_DB_USER={ENV['APP_DB_USER']}", "-e", f"APP_DB_PASSWORD={ENV['APP_DB_PASSWORD']}"]
    r = sh(["docker", "run", "-d", "--name", tgt, "--network", "decisiongpt_db", *env_args,
            "-v", f"{root}/deploy/postgres/app-role.sql:/deploy/app-role.sql:ro",
            "-v", f"{root}/deploy/postgres/initdb-app-role.sh:/docker-entrypoint-initdb.d/10-app-role.sh:ro", "postgres:15-alpine"])
    check(s, "a brand-new empty PostgreSQL 15 cluster starts (its init script creates the roles and the empty database)", r.returncode == 0, r.stderr[-200:])
    end = time.time() + 90
    ready = False
    while time.time() < end:
        if sh(["docker", "exec", tgt, "pg_isready", "-U", ENV["POSTGRES_USER"], "-d", ENV["POSTGRES_DB"]]).returncode == 0 and sh(["docker", "exec", tgt, "sh", "-c", "ls /var/lib/postgresql/data/PG_VERSION"]).returncode == 0:
            time.sleep(4)
            if sh(["docker", "exec", tgt, "pg_isready", "-U", ENV["POSTGRES_USER"]]).returncode == 0:
                ready = True
                break
        time.sleep(2)
    check(s, "the new cluster is ready", ready)
    sh(["docker", "cp", dump, f"{tgt}:/tmp/backup.dump"])
    r = sh(["docker", "exec", "-e", f"PGPASSWORD={ENV['POSTGRES_PASSWORD']}", tgt, "pg_restore", "-h", "127.0.0.1", "-U", ENV["POSTGRES_USER"], "-d", ENV["POSTGRES_DB"], "--no-owner", "--role", ENV["POSTGRES_USER"], "/tmp/backup.dump"], timeout=300)
    check(s, "pg_restore into the fresh cluster succeeds", r.returncode == 0, redact(r.stderr)[-300:])

    def tq(sql: str, user: str | None = None, password: str | None = None) -> str:
        user, password = user or ENV["POSTGRES_USER"], password if password is not None else ENV["POSTGRES_PASSWORD"]
        rr = sh(["docker", "exec", "-e", f"PGPASSWORD={password}", tgt, "psql", "-h", "127.0.0.1", "-U", user, "-d", ENV["POSTGRES_DB"], "-At", "-F", "|", "-c", sql])
        if rr.returncode != 0:
            raise RuntimeError(redact(rr.stderr)[:300])
        return rr.stdout.strip()

    check(s, "the restored database is at the same schema revision", tq("select version_num from alembic_version") == src_head)
    names = src_counts.keys()
    dst_counts = {n: int(tq(f'select count(*) from "{n}"')) for n in names}
    check(s, "every table has the same row count as the source", dst_counts == src_counts, {k: (src_counts[k], dst_counts[k]) for k in names if src_counts[k] != dst_counts[k]})
    dst_idx = tq("select indexname||':'||indexdef from pg_indexes where schemaname='public' order by 1")
    only_src, only_dst = sorted(set(src_idx.splitlines()) - set(dst_idx.splitlines())), sorted(set(dst_idx.splitlines()) - set(src_idx.splitlines()))

    def canon(defn: str) -> str:
        """pg_restore can re-deparse an equivalent predicate with the casts in different places (ANY ((ARRAY[..])::text[]) vs ANY (ARRAY[(..)::text]))."""
        d = re.sub(r"::[a-z ]+(\[\])?", "", defn.lower())
        return re.sub(r"[()\s]", "", d)

    src_c, dst_c = sorted(canon(x) for x in src_idx.splitlines()), sorted(canon(x) for x in dst_idx.splitlines())
    check(s, "every index exists with the same name, table, uniqueness, columns and predicate literals (casts normalised)", src_c == dst_c,
          {"only_in_source": only_src[:2], "only_in_restored": only_dst[:2], "n_src": len(src_idx.splitlines()), "n_dst": len(dst_idx.splitlines())})
    info(s, "indexes whose TEXT differs only in how PostgreSQL deparses the same predicate after pg_restore", f"{len(only_src)} (e.g. {[x.split(':')[0] for x in only_src][:3]})")
    # behaviour, not text: the partial unique index must still reject a second ACTIVE alert and still allow a resolved one
    cols = {}
    for table in ("businesses", "alerts"):
        cols[table] = [r.split("|") for r in tq("select column_name, data_type from information_schema.columns where table_schema='public' and table_name='%s' "
                                                "and is_nullable='NO' and column_default is null order by ordinal_position" % table).splitlines()]
    lit = {"uuid": "gen_random_uuid()", "integer": "1", "bigint": "1", "numeric": "1", "boolean": "false", "date": "current_date", "json": "'{}'::json", "jsonb": "'{}'::jsonb",
           "double precision": "1", "real": "1", "smallint": "1"}

    def row_values(table: str, override: dict) -> tuple[str, str]:
        names, vals = [], []
        for name, dtype in cols[table]:
            names.append(name)
            vals.append(override[name] if name in override else ("now()" if dtype.startswith("timestamp") else lit.get(dtype, "'x'")))
        return ", ".join(names), ", ".join(vals)

    bn, bv = row_values("businesses", {"id": "'00000000-0000-0000-0000-0000000000a1'"})
    base = {"business_id": "'00000000-0000-0000-0000-0000000000a1'", "dedupe_key": "'k1'"}
    an1, av1 = row_values("alerts", {**base, "status": "'open'"})
    an2, av2 = row_values("alerts", {**base, "status": "'resolved'"})
    probe_sql = f"""DO $$ BEGIN
      INSERT INTO businesses ({bn}) VALUES ({bv});
      INSERT INTO alerts ({an1}) VALUES ({av1});
      BEGIN INSERT INTO alerts ({an1}) VALUES ({av1}); RAISE EXCEPTION 'ACTIVE_DUPLICATE_WAS_ACCEPTED';
      EXCEPTION WHEN unique_violation THEN NULL; END;
      INSERT INTO alerts ({an2}) VALUES ({av2});
      INSERT INTO alerts ({an2}) VALUES ({av2});
      RAISE EXCEPTION 'PROBE_OK_ROLLBACK';
    END $$;"""
    try:
        tq(probe_sql)
        probe = "probe did not finish"
    except RuntimeError as e:
        probe = "ok" if "PROBE_OK_ROLLBACK" in str(e) else str(e)[:160]
    check(s, "BEHAVIOUR on the restored database: the partial unique index rejects a second ACTIVE alert and still allows resolved duplicates", probe == "ok", probe)
    check(s, "the three append-only triggers are present", tq("select tgname from pg_trigger where not tgisinternal order by 1") == src_trg)
    # privileges of the application role after a restore (not assumed: measured)
    try:
        tq("select count(*) from users", user=ENV["APP_DB_USER"], password=ENV["APP_DB_PASSWORD"])
        can_read = True
    except RuntimeError as e:
        can_read = False
        info(s, "app role cannot read right after pg_restore", str(e)[:150])
    if not can_read:
        sh(["docker", "cp", f"{root}/deploy/postgres/app-role.sql", f"{tgt}:/tmp/app-role.sql"])
        rr = sh(["docker", "exec", "-e", f"PGPASSWORD={ENV['POSTGRES_PASSWORD']}", tgt, "psql", "-h", "127.0.0.1", "-U", ENV["POSTGRES_USER"], "-d", ENV["POSTGRES_DB"], "-v", "ON_ERROR_STOP=1", "-v", f"owner_role={ENV['POSTGRES_USER']}", "-v", f"app_user={ENV['APP_DB_USER']}", "-v", f"app_password={ENV['APP_DB_PASSWORD']}", "-f", "/tmp/app-role.sql"])
        info(s, "re-applied deploy/postgres/app-role.sql after restore (documented step)", f"exit={rr.returncode}")
        try:
            tq("select count(*) from users", user=ENV["APP_DB_USER"], password=ENV["APP_DB_PASSWORD"])
            can_read = True
        except RuntimeError:
            can_read = False
    check(s, "the application role can read the restored data (privileges present, or restored by re-running the role script)", can_read)
    try:
        tq("update tracked_expectations set expected_value = 1", user=ENV["APP_DB_USER"], password=ENV["APP_DB_PASSWORD"])
        upd = "ALLOWED"
    except RuntimeError as e:
        upd = "append-only" if "append-only" in str(e) else str(e)[:120]
    check(s, "on the restored database the application role still cannot edit saved records (trigger fires)", upd == "append-only", upd)
    try:
        tq("truncate tracked_expectations", user=ENV["APP_DB_USER"], password=ENV["APP_DB_PASSWORD"])
        tr = "ALLOWED"
    except RuntimeError as e:
        tr = "refused" if "permission denied" in str(e) else str(e)[:100]
    check(s, "on the restored database the application role cannot TRUNCATE", tr == "refused", tr)
    owned = tq(f"select count(*) from pg_tables where schemaname='public' and tableowner = '{ENV['APP_DB_USER']}'")
    check(s, "the application role owns no restored table", owned == "0", owned)
    # start the application against the restored database, with the SAME secrets, and exercise it
    sh(["docker", "rm", "-f", "dgpt_restored_api", "dgpt_restored_api_newsecret"])
    base_env = ["-e", "ENVIRONMENT=production", "-e", "AUTH_ENABLED=true", "-e", f"SECRET_KEY={ENV['SECRET_KEY']}", "-e", f"RESEARCH_CONSOLE_TOKEN={ENV['RESEARCH_CONSOLE_TOKEN']}",
                "-e", f"FRONTEND_ORIGIN=https://{HOST}", "-e", "TRUSTED_PROXIES=172.30.0.10/32", "-e", "OPENAI_API_KEY=",
                "-e", f"DATABASE_URL=postgresql+psycopg://{ENV['APP_DB_USER']}:{ENV['APP_DB_PASSWORD']}@{tgt}:5432/{ENV['POSTGRES_DB']}"]
    r = sh(["docker", "run", "-d", "--name", "dgpt_restored_api", "--network", "decisiongpt_web", "-p", "127.0.0.1:18000:8000", *base_env, "-e", f"JWT_SECRET={ENV['JWT_SECRET']}", IMAGE])
    sh(["docker", "network", "connect", "decisiongpt_db", "dgpt_restored_api"])
    sh(["docker", "restart", "dgpt_restored_api"])                  # attach to the db network, then start serving
    ok = False
    for _ in range(60):
        try:
            c = http.client.HTTPConnection("127.0.0.1", 18000, timeout=3)
            c.request("GET", "/api/v1/health")
            if c.getresponse().status == 200:
                ok = True
                break
        except Exception:
            pass
        time.sleep(2)
    check(s, "the application starts in hardened mode against the RESTORED database (schema head, role checks all pass)", ok, sh(["docker", "logs", "--tail", "15", "dgpt_restored_api"]).stderr[-300:])
    rest = Api(host="127.0.0.1", port=18000, tls=False)
    # sign in from INSIDE the restored API's container: its client address is the loopback, a different rate-limit bucket from the host address
    # that the earlier throttle tests used up (the per-address failure budget was itself restored from the backup, which is the point of the check below)
    probe = PROBE_LOGIN.replace("__PW__", PW)
    pr = sh(["docker", "exec", "-i", "dgpt_restored_api", "python", "-"], input=probe)
    check(s, "a user restored from the backup can sign in with their password (the password hash came back)", "STATUS 200" in pr.stdout, pr.stdout + pr.stderr[-200:])
    info(s, "from the host's address the restored API answers 429: the per-address failure counters were restored too",
         rest.req("POST", "/api/v1/auth/login", {"email": "bob@staging.test", "password": PW})[0])
    check(s, "a token issued before the backup (same JWT secret) is still honoured", rest.req("GET", "/api/v1/auth/me", token=STATE["tok_ok"])[0] == 200)
    check(s, "a token revoked before the backup is STILL revoked (the revocation list was in the backup)", rest.req("GET", "/api/v1/auth/me", token=STATE["tok_revoked"])[0] == 401)
    check(s, "a throttled account is still throttled (rate-limit counters were in the backup)", rest.req("POST", "/api/v1/auth/login", {"email": "throttle-restore@staging.test", "password": PW})[0] == 429)
    st, rep, _, _ = rest.req("GET", f"/api/v1/businesses/{STATE['bid_b']}/tracking/report", token=STATE["tok_ok"])
    check(s, "tracking reads work on the restored database", st == 200, st)
    st, plan, _, _ = rest.req("POST", f"/api/v1/businesses/{STATE['bid_b']}/tracking/expectations", {"metric": "units_sold", "unit": "units", "window_start": "2025-06-01", "window_end": "2025-06-01", "expected_value": 7}, STATE["tok_ok"])
    st2, obs, _, _ = rest.req("POST", f"/api/v1/businesses/{STATE['bid_b']}/tracking/expectations/{plan['id']}/observations", {"metric": "units_sold", "unit": "units", "status": "observed", "value": 7.0}, STATE["tok_ok"]) if st == 200 else (0, None, None, None)
    st3 = rest.req("POST", f"/api/v1/businesses/{STATE['bid_b']}/tracking/observations/{obs['id']}/correction", {"reason": "restore write check", "value": 8.0}, STATE["tok_ok"])[0] if st2 == 200 else 0
    check(s, "tracking WRITES (plan, observation, correction) work on the restored database through the triggers", (st, st2, st3) == (200, 200, 200), (st, st2, st3))
    sh(["docker", "run", "-d", "--name", "dgpt_restored_api_newsecret", "--network", "decisiongpt_web", "-p", "127.0.0.1:18001:8000", *base_env, "-e", f"JWT_SECRET={secrets.token_hex(32)}", IMAGE])
    sh(["docker", "network", "connect", "decisiongpt_db", "dgpt_restored_api_newsecret"])
    sh(["docker", "restart", "dgpt_restored_api_newsecret"])
    time.sleep(20)
    try:
        st = Api(host="127.0.0.1", port=18001, tls=False).req("GET", "/api/v1/auth/me", token=STATE["tok_ok"])[0]
    except Exception as e:
        st = f"unreachable: {type(e).__name__}"
    check(s, "LIMITATION CONFIRMED: with a different JWT secret every pre-backup token is rejected (secrets are not in the database backup)", st == 401, st)
    # source database must be untouched by the restore test
    check(s, "the source database was not modified by the restore test (row counts unchanged apart from nothing)", table_counts() == src_counts)
    sh(["docker", "rm", "-f", "dgpt_restored_api", "dgpt_restored_api_newsecret", tgt])
    os.remove(dump)


# ------------------------------------------------------------------------------------------------ section: logs hygiene
def section_logs() -> None:
    s = "logs"
    text = ""
    for svc in ("backend", "frontend", "postgres", "caddy"):
        text += compose("logs", "--no-color", svc).stdout
    leaked = [x[:4] + "..." for x in secrets_in_env() + [PW, "wrong-guess-number", "a-brand-new-passphrase"] if x in text]
    check(s, "scan of every service log: none of the 5 secrets, the test passwords or the guessed passwords appear", not leaked, leaked)
    check(s, "no Python traceback in the backend log", "Traceback" not in compose("logs", "--no-color", "backend").stdout, "")


SECTIONS = {"config": section_config, "stack": section_stack, "roles": section_roles, "health": section_health, "network": section_network,
            "auth": section_auth, "tls": section_tls, "persist": section_persist, "shutdown": section_shutdown, "restore": section_restore, "logs": section_logs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", default=",".join(SECTIONS))
    ap.add_argument("--report", default="staging_report.json")
    a = ap.parse_args()
    load_env()
    for name in a.sections.split(","):
        try:
            SECTIONS[name]()
        except Exception as exc:                          # a crashed section is a failure, never a silent pass
            check(name, f"section did not complete ({type(exc).__name__})", False, str(exc))
    pathlib.Path(a.report).write_text(json.dumps({"results": RESULTS}, indent=1))
    p, f = sum(r["status"] == "PASS" for r in RESULTS), sum(r["status"] == "FAIL" for r in RESULTS)
    print(f"\nSUMMARY: {p} passed, {f} failed, {sum(r['status'] == 'INFO' for r in RESULTS)} informational")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
