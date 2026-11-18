"""Startup security validation: unsafe production configuration must fail before serving, with a message that names the problem and never
prints a secret. The process-level tests start a real interpreter with a controlled environment."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.security_config import (
    SecurityConfigError, schema_problem, security_problems, security_warnings, validate_security_config,
)

ROOT = Path(__file__).resolve().parents[2]
GOOD = dict(
    environment="production", auth_enabled=True, jwt_secret="j" * 40, secret_key="s" * 40, research_console_enabled=True,
    research_console_token="t" * 30, database_url="postgresql+psycopg://svc:Zr7qLp2@db.internal:5432/decisiongpt",
    frontend_origin="https://app.example.com", trusted_proxies="10.0.0.0/8",
)


def make(**over) -> Settings:
    return Settings(_env_file=None, **{**GOOD, **over})


def test_a_correct_production_configuration_is_accepted():
    s = make()
    assert security_problems(s) == []
    validate_security_config(s, check_schema=False)


@pytest.mark.parametrize("over,needle", [
    ({"auth_enabled": False}, "AUTH_ENABLED must be true"),
    ({"jwt_secret": "change-me-jwt-secret"}, "JWT_SECRET"),
    ({"jwt_secret": "short"}, "JWT_SECRET"),
    ({"secret_key": "change-me-in-production"}, "SECRET_KEY"),
    ({"research_console_token": "change-me-research-console-token"}, "RESEARCH_CONSOLE_TOKEN"),
    ({"research_console_token": "tiny"}, "RESEARCH_CONSOLE_TOKEN"),
    ({"database_url": "sqlite:///./dev.db"}, "PostgreSQL"),
    ({"database_url": "postgresql+psycopg://decisiongpt:decisiongpt@db:5432/x"}, "default database credentials"),
    ({"frontend_origin": "http://localhost:3000"}, "FRONTEND_ORIGIN"),
    ({"frontend_origin": "http://app.example.com"}, "FRONTEND_ORIGIN"),
    ({"frontend_origin": "*"}, "FRONTEND_ORIGIN"),
    ({"environment": "prod"}, "ENVIRONMENT must be one of"),
    ({"environment": ""}, "ENVIRONMENT must be one of"),
    ({"rate_limit_enabled": False}, "RATE_LIMIT_ENABLED must be true"),
    ({"jwt_ttl_seconds": 90_000}, "JWT_TTL_SECONDS"),
    ({"jwt_ttl_seconds": 10}, "JWT_TTL_SECONDS"),
    ({"jwt_secret_previous": "short"}, "JWT_SECRET_PREVIOUS"),
    ({"jwt_secret_previous": "j" * 40}, "JWT_SECRET_PREVIOUS must differ"),
    ({"jwt_issuer": " "}, "JWT_ISSUER"),
    ({"trusted_proxies": "10.0.0.0/8, nonsense"}, "TRUSTED_PROXIES"),
])
def test_each_insecure_production_setting_is_reported_without_its_value(over, needle):
    s = make(**over)
    problems = security_problems(s)
    assert any(needle in p for p in problems), problems
    with pytest.raises(SecurityConfigError) as err:
        validate_security_config(s, check_schema=False)
    text = str(err.value)
    assert needle in text and "No secret values are printed" in text
    for secret in ("change-me-jwt-secret", "change-me-in-production", "change-me-research-console-token", "Zr7qLp2", "j" * 40):
        assert secret not in text


def test_the_research_token_may_be_absent_if_the_console_is_disabled():
    assert security_problems(make(research_console_enabled=False, research_console_token="change-me-research-console-token")) == []


def test_staging_is_hardened_like_production_and_development_and_test_are_not():
    assert security_problems(make(environment="staging", auth_enabled=False))
    for env in ("development", "test"):
        assert security_problems(make(environment=env, auth_enabled=False, jwt_secret="change-me-jwt-secret")) == []


def test_authentication_off_in_development_is_allowed_but_loudly_warned():
    s = make(environment="development", auth_enabled=False)
    (w,) = security_warnings(s)
    assert "AUTHENTICATION IS DISABLED" in w and "local development" in w and "never expose" in w
    assert security_warnings(make(environment="development", auth_enabled=True)) == []
    assert security_warnings(make()) == []


def test_an_empty_trusted_proxy_list_is_warned_about_in_hardened_environments_only():
    (w,) = security_warnings(make(trusted_proxies=""))
    assert "TRUSTED_PROXIES is empty" in w
    assert security_warnings(make(trusted_proxies="10.0.0.0/8")) == []
    assert security_warnings(make(environment="development", auth_enabled=True, trusted_proxies="")) == []


def test_a_previous_secret_is_accepted_during_a_rotation_when_it_is_a_real_secret():
    assert security_problems(make(jwt_secret_previous="p" * 40)) == []


def test_secrets_are_not_shown_in_a_settings_repr_or_traceback():
    text = repr(make())
    for secret in ("j" * 40, "s" * 40, "t" * 30, "Zr7qLp2"):
        assert secret not in text
    assert "p" * 40 not in repr(make(jwt_secret_previous="p" * 40))


def test_docs_are_off_in_hardened_environments_unless_requested():
    assert make().docs_active is False
    assert make(docs_enabled=True).docs_active is True
    assert make(environment="development", auth_enabled=False).docs_active is True


def test_the_schema_check_reports_an_unmigrated_database_without_connection_details(tmp_path):
    db = tmp_path / "old.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": str(ROOT)}
    assert subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0010"], cwd=ROOT / "backend", env=env, capture_output=True, timeout=300).returncode == 0
    msg = schema_problem(f"sqlite:///{db.as_posix()}")
    assert msg and "'0010'" in msg and "alembic upgrade head" in msg and str(tmp_path) not in msg
    assert subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=env, capture_output=True, timeout=300).returncode == 0
    assert schema_problem(f"sqlite:///{db.as_posix()}") is None


def _start(env_extra: dict, tmp_path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("AUTH_ENABLED", "ENVIRONMENT", "JWT_SECRET", "SECRET_KEY", "RESEARCH_CONSOLE_TOKEN",
                                                              "DATABASE_URL", "FRONTEND_ORIGIN", "DOCS_ENABLED", "OPENAI_API_KEY")}
    env.update({"PYTHONPATH": f"{ROOT / 'backend'}{os.pathsep}{ROOT}", "OPENAI_API_KEY": ""}, **env_extra)
    return subprocess.run([sys.executable, "-c", "import app.main; print('STARTED')"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=300)


def test_the_process_refuses_to_start_in_production_with_authentication_off(tmp_path):
    secret = "-".join(["Zk9", "marker", "value", "that", "must", "not", "appear", "1234"])   # built at runtime: the repository secret scan flags long assigned literals
    r = _start({"ENVIRONMENT": "production", "AUTH_ENABLED": "false", "JWT_SECRET": secret, "SECRET_KEY": secret + "x",
                "RESEARCH_CONSOLE_TOKEN": secret + "y", "DATABASE_URL": "postgresql+psycopg://svc:" + secret + "@db.internal/x",
                "FRONTEND_ORIGIN": "https://app.example.com"}, tmp_path)
    assert r.returncode != 0 and "STARTED" not in r.stdout
    err = r.stderr
    assert "will not start with this security configuration" in err and "AUTH_ENABLED must be true" in err
    assert secret not in err and secret not in r.stdout                   # nothing secret in the failure output


def test_the_process_refuses_to_start_with_default_secrets_and_a_typo_environment(tmp_path):
    r = _start({"ENVIRONMENT": "production", "AUTH_ENABLED": "true", "DATABASE_URL": "postgresql+psycopg://svc:x@db/x",
                "FRONTEND_ORIGIN": "https://a.example.com"}, tmp_path)
    assert r.returncode != 0 and "JWT_SECRET" in r.stderr and "SECRET_KEY" in r.stderr and "RESEARCH_CONSOLE_TOKEN" in r.stderr
    r = _start({"ENVIRONMENT": "prod", "AUTH_ENABLED": "false"}, tmp_path)
    assert r.returncode != 0 and "ENVIRONMENT must be one of" in r.stderr


def test_the_process_starts_in_development_and_warns_when_authentication_is_off(tmp_path):
    r = _start({"ENVIRONMENT": "development", "AUTH_ENABLED": "false", "DATABASE_URL": f"sqlite:///{(tmp_path / 'd.db').as_posix()}"}, tmp_path)
    assert r.returncode == 0 and "STARTED" in r.stdout
    assert "AUTHENTICATION IS DISABLED" in (r.stdout + r.stderr)
