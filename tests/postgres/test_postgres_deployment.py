"""The hardened deployment path against a real PostgreSQL: startup validation (role, schema head), then a real server process answering real HTTP
requests as the least-privilege role, surviving a restart with its data, isolating tenants, throttling sign-in and refusing forged proxy headers."""
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

from tests.pg_support import ROOT, run_alembic

BACKEND = ROOT / "backend"
_REAL_SEND = httpx.HTTPTransport.handle_request       # captured at import, before the suite's autouse fixture blocks outbound HTTP


def _hardened_env(database_url: str, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in (
        "AUTH_ENABLED", "ENVIRONMENT", "JWT_SECRET", "SECRET_KEY", "RESEARCH_CONSOLE_TOKEN", "DATABASE_URL", "MIGRATION_DATABASE_URL", "FRONTEND_ORIGIN",
        "DOCS_ENABLED", "OPENAI_API_KEY", "TRUSTED_PROXIES", "RATE_LIMIT_ENABLED", "DECISIONGPT_TEST_PG_APP_URL", "DECISIONGPT_TEST_PG_OWNER_URL")}
    env.update(ENVIRONMENT="production", AUTH_ENABLED="true", JWT_SECRET=secrets.token_urlsafe(40), SECRET_KEY=secrets.token_urlsafe(40),
               RESEARCH_CONSOLE_TOKEN=secrets.token_urlsafe(32), DATABASE_URL=database_url, FRONTEND_ORIGIN="https://app.example.com",
               TRUSTED_PROXIES="10.0.0.0/8", OPENAI_API_KEY="", PYTHONPATH=f"{BACKEND}{os.pathsep}{ROOT}", **extra)
    return env


def _import_app(env) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", "import app.main; print('STARTED')"], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300)


def test_a_hardened_start_succeeds_as_the_application_role_on_a_migrated_database(pg):
    r = _import_app(_hardened_env(pg.app_url))
    assert r.returncode == 0 and "STARTED" in r.stdout, r.stderr[-800:]


def test_a_hardened_start_refuses_a_role_that_owns_the_tables(pg):
    r = _import_app(_hardened_env(pg.owner_url))
    assert r.returncode != 0 and "owns tables" in r.stderr and "STARTED" not in r.stdout
    assert pg.owner_url.split("//")[1].split("@")[0].split(":")[1] not in r.stderr          # the password is not in the failure output


def test_a_hardened_start_refuses_a_superuser(pg):
    from sqlalchemy.engine import make_url

    admin_on_db = make_url(pg.admin).set(database=pg.database).render_as_string(hide_password=False)
    r = _import_app(_hardened_env(admin_on_db))
    assert r.returncode != 0 and "excessive privileges" in r.stderr and "superuser" in r.stderr


def test_a_hardened_start_refuses_a_database_that_is_not_at_the_current_revision(pg):
    run_alembic(pg.owner_url, "downgrade", "0014")
    try:
        r = _import_app(_hardened_env(pg.app_url))
        assert r.returncode != 0 and "0014" in r.stderr and "alembic upgrade head" in r.stderr
    finally:
        run_alembic(pg.owner_url, "upgrade", "head")
    assert _import_app(_hardened_env(pg.app_url)).returncode == 0                          # and starts again once migrated


# ------------------------------------------------------------------ a real server process
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, env, port):
        self.env, self.port, self.proc = env, port, None
        self.url = f"http://127.0.0.1:{port}"

    def start(self):
        # output goes to a file, never an undrained pipe: a full pipe blocks the server on its own logging and every request then hangs
        self.logfile = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
        self.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.port), "--no-proxy-headers"],
                                     cwd=BACKEND, env=self.env, stdout=self.logfile, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 120
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("server exited: " + Path(self.logfile.name).read_text(errors="replace")[-800:])
            try:
                if httpx.get(f"{self.url}/api/v1/health", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.5)
        raise RuntimeError("server did not become healthy")

    def stop(self) -> str:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.logfile.close()
        out = Path(self.logfile.name).read_text(errors="replace")
        Path(self.logfile.name).unlink(missing_ok=True)
        return out


PW = "orange-river-4271"


def test_a_real_server_on_postgresql_serves_isolates_throttles_and_survives_a_restart(pg, monkeypatch):
    from tests import pg_support

    # the suite blocks outbound HTTP; this test talks to a server it started itself, on the loopback interface only
    def loopback_only(self, request):
        assert request.url.host == "127.0.0.1", "only loopback traffic is allowed in this test"
        return _REAL_SEND(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", loopback_only)

    pg_support.reset_data(pg.owner_url)
    env = _hardened_env(pg.app_url)
    srv = Server(env, _free_port())
    srv.start()
    log = ""
    try:
        c = httpx.Client(base_url=srv.url + "/api/v1", timeout=60)
        # production posture visible over the wire
        h = c.get("/health")
        assert h.json() == {"status": "ok", "dependencies": {"database": "ok"}}                  # nothing but status
        assert httpx.get(f"{srv.url}/docs").status_code == 404 and httpx.get(f"{srv.url}/openapi.json").status_code == 404
        assert "max-age" in h.headers["strict-transport-security"] and h.headers["cache-control"] == "no-store" and h.headers["x-frame-options"] == "DENY"
        # accounts and tenants, as the least-privilege role
        a = c.post("/auth/register", json={"email": "a@example.com", "password": PW}).json()["access_token"]
        b = c.post("/auth/register", json={"email": "b@example.com", "password": PW}).json()["access_token"]
        ha, hb = {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}
        body = {"name": "Alpha Secret", "industry": "retail", "business_type": "D2C", "business_size": "small"}
        bid = c.post("/businesses", json=body, headers=ha).json()["id"]
        assert c.get(f"/businesses/{bid}", headers=ha).status_code == 200
        foreign = c.get(f"/businesses/{bid}", headers=hb)
        assert foreign.status_code == 404 and "Alpha" not in foreign.text
        assert c.get(f"/businesses/{bid}").status_code == 401                                    # anonymous
        assert c.get("/businesses/not-a-uuid/goals", headers=hb).status_code == 404 and c.get("/businesses/not-a-uuid/goals", headers=hb).json()["error"]["message"] == "Business not found."
        assert c.get(f"/businesses/{bid}/explain/answer/does-not-exist", headers=ha).status_code == 404       # malformed id inside a valid business
        assert c.post("/auth/register", json={"email": "evil@example.com", "password": PW, "role": "admin"}).status_code == 403
        assert c.get("/research/models", headers=ha).status_code == 403
        # tracking works end to end under the triggers
        assert c.get(f"/businesses/{bid}/tracking/report", headers=ha).status_code == 200
        # throttling over real HTTP, with forged forwarding headers from an untrusted peer having no effect
        codes = [c.post("/auth/login", json={"email": "a@example.com", "password": f"wrong-guess-{n}-x"}, headers={"X-Forwarded-For": f"203.0.113.{n}"}).status_code
                 for n in range(7)]
        assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
        r = c.post("/auth/login", json={"email": "a@example.com", "password": PW})
        assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
        # logout revokes this token in the shared database
        assert c.post("/auth/logout", headers=hb).status_code == 204
        assert c.get("/auth/me", headers=hb).status_code == 401
    finally:
        log += srv.stop()
    # restart: same database, same data, throttle state persisted in the database (not in the dead process)
    srv2 = Server(env, _free_port())
    srv2.start()
    try:
        c2 = httpx.Client(base_url=srv2.url + "/api/v1", timeout=60)
        assert c2.post("/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 429       # the pair bucket survived the restart
        ok = c2.post("/auth/login", json={"email": "b@example.com", "password": PW})
        assert ok.status_code == 200                                                              # another account is unaffected, data persisted
        assert c2.get("/auth/me", headers={"Authorization": f"Bearer {a}"}).status_code == 200      # a still-valid token still works after a restart
        assert c2.get("/auth/me", headers={"Authorization": f"Bearer {b}"}).status_code == 401      # a revoked one stays revoked
    finally:
        log += srv2.stop()
    for secret in (env["JWT_SECRET"], env["SECRET_KEY"], env["RESEARCH_CONSOLE_TOKEN"], PW, "wrong-guess"):
        assert secret not in log, "a secret or password appeared in the server log"


def test_two_server_processes_on_one_database_share_one_throttle_budget_and_one_revocation_list(pg, monkeypatch):
    """The supported multi-worker / multi-replica topology: separate OS processes, one PostgreSQL. An in-memory limiter would give each process
    its own budget; here the failures counted by one process throttle the other, and a logout in one is honoured by the other."""
    from tests import pg_support

    def loopback_only(self, request):
        assert request.url.host == "127.0.0.1"
        return _REAL_SEND(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", loopback_only)
    pg_support.reset_data(pg.owner_url)
    env = _hardened_env(pg.app_url)                       # the same secrets for both: replicas of one deployment
    s1, s2 = Server(env, _free_port()), Server(env, _free_port())
    s1.start()
    s2.start()
    try:
        c1, c2 = (httpx.Client(base_url=s.url + "/api/v1", timeout=60) for s in (s1, s2))
        assert c1.post("/auth/register", json={"email": "shared@example.com", "password": PW}).status_code == 201
        wrong = {"email": "shared@example.com", "password": "not-the-password-1"}
        codes = [(c1 if n % 2 == 0 else c2).post("/auth/login", json=wrong).status_code for n in range(7)]      # alternate between the two processes
        assert codes == [401] * 5 + [429] * 2, codes                                                              # ONE budget of 5, not 5 per process
        assert c2.post("/auth/login", json={"email": "shared@example.com", "password": PW}).status_code == 429
        # a different account is unaffected, and a token issued by one process works on the other and is revoked for both
        tok = c1.post("/auth/register", json={"email": "other@example.com", "password": PW}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        assert c2.get("/auth/me", headers=h).status_code == 200
        assert c1.post("/auth/logout", headers=h).status_code == 204
        assert c2.get("/auth/me", headers=h).status_code == 401
    finally:
        log = s1.stop() + s2.stop()
    for secret in (env["JWT_SECRET"], PW, "not-the-password"):
        assert secret not in log
