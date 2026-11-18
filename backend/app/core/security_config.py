"""Security configuration validation: fail at startup, with a clear non-secret message, when the effective configuration is unsafe.

Environments (``ENVIRONMENT``):
* ``development`` and ``test``: local or isolated use. Authentication may be off (``AUTH_ENABLED=false``, the default); a loud warning is logged
  because with it off ANY caller can read and write ANY business.
* ``staging`` and ``production`` ("hardened"): authentication must be on, secrets must be real, the database must be PostgreSQL with
  non-default credentials, the browser origin must be an https origin, the API documentation is off unless asked for, and the database schema must
  be at the revision the code expects.

Messages never contain a secret value: they name the setting and the rule that failed.
"""
from __future__ import annotations

import logging
from pathlib import Path

ENVIRONMENTS = ("development", "test", "staging", "production")
HARDENED = ("staging", "production")
MIN_SECRET_CHARS = 32
MIN_TOKEN_CHARS = 24
_PLACEHOLDER_MARKERS = ("change-me", "changeme", "replace-me", "example", "secret-key-here")
_BACKEND_DIR = Path(__file__).resolve().parents[2]

logger = logging.getLogger("decisiongpt.security")


class SecurityConfigError(RuntimeError):
    """The effective configuration is not safe to serve requests with. The message lists problems, never values."""


def _placeholder(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return (not v) or any(m in v for m in _PLACEHOLDER_MARKERS)


def hardened(settings) -> bool:
    return str(settings.environment).strip().lower() in HARDENED


def security_problems(settings) -> list[str]:
    """Everything that makes this configuration unsafe to start with, as plain statements (no secret values)."""
    env = str(settings.environment).strip().lower()
    problems: list[str] = []
    if env not in ENVIRONMENTS:
        problems.append(f"ENVIRONMENT must be one of {', '.join(ENVIRONMENTS)} (got {env[:24]!r}); an unrecognised value would silently run "
                        "without production protections.")
        return problems
    if env not in HARDENED:
        return problems
    if not settings.auth_enabled:
        problems.append(f"AUTH_ENABLED must be true when ENVIRONMENT={env}: with authentication off any caller can read and write every business.")
    if _placeholder(settings.jwt_secret) or len(settings.jwt_secret) < MIN_SECRET_CHARS:
        problems.append(f"JWT_SECRET must be set to a random value of at least {MIN_SECRET_CHARS} characters (it is missing, a placeholder or too short).")
    if _placeholder(settings.secret_key) or len(settings.secret_key) < MIN_SECRET_CHARS:
        problems.append(f"SECRET_KEY must be set to a random value of at least {MIN_SECRET_CHARS} characters (it is missing, a placeholder or too short).")
    if settings.research_console_enabled and (_placeholder(settings.research_console_token) or len(settings.research_console_token) < MIN_TOKEN_CHARS):
        problems.append(f"RESEARCH_CONSOLE_TOKEN must be a random value of at least {MIN_TOKEN_CHARS} characters, or RESEARCH_CONSOLE_ENABLED=false "
                        "(the token is missing, a placeholder or too short).")
    url = str(settings.database_url)
    if url.startswith("sqlite"):
        problems.append(f"DATABASE_URL must point to PostgreSQL when ENVIRONMENT={env} (SQLite is for local development and tests).")
    elif "decisiongpt:decisiongpt@" in url:
        problems.append("DATABASE_URL still uses the default database credentials; set POSTGRES_PASSWORD and DATABASE_URL to real values.")
    if settings.jwt_secret_previous is not None and settings.jwt_secret_previous != "":
        if _placeholder(settings.jwt_secret_previous) or len(settings.jwt_secret_previous) < MIN_SECRET_CHARS:
            problems.append(f"JWT_SECRET_PREVIOUS, when set, must be a real random value of at least {MIN_SECRET_CHARS} characters (it is a placeholder or too short).")
        elif settings.jwt_secret_previous == settings.jwt_secret:
            problems.append("JWT_SECRET_PREVIOUS must differ from JWT_SECRET (remove it once the rotation has drained).")
    if not (60 <= int(settings.jwt_ttl_seconds) <= 24 * 3600):
        problems.append("JWT_TTL_SECONDS must be between 60 and 86400 (a session token may not live longer than a day).")
    if not str(settings.jwt_issuer).strip() or not str(settings.jwt_audience).strip():
        problems.append("JWT_ISSUER and JWT_AUDIENCE must not be empty.")
    if not settings.rate_limit_enabled:
        problems.append(f"RATE_LIMIT_ENABLED must be true when ENVIRONMENT={env}: sign-in and sign-up would be open to unlimited guessing.")
    if str(settings.trusted_proxies).strip() and not _valid_proxy_list(str(settings.trusted_proxies)):
        problems.append("TRUSTED_PROXIES contains an entry that is not an IP address or CIDR range.")
    origin = str(settings.frontend_origin).strip().lower()
    if not origin.startswith("https://") or any(x in origin for x in ("localhost", "127.0.0.1", "*")):
        problems.append("FRONTEND_ORIGIN must be the https origin of the web application (not localhost, not a wildcard).")
    return problems


def _valid_proxy_list(spec: str) -> bool:
    import ipaddress

    try:
        for part in spec.split(","):
            if part.strip():
                ipaddress.ip_network(part.strip(), strict=False)
    except ValueError:
        return False
    return True


def security_warnings(settings) -> list[str]:
    out: list[str] = []
    if hardened(settings) and not str(settings.trusted_proxies).strip():
        out.append("TRUSTED_PROXIES is empty: the client address is the TCP peer. Behind a reverse proxy every caller then shares the proxy's address "
                   "and the per-address sign-in and sign-up limits apply to everyone together. Set TRUSTED_PROXIES to the proxy's address or network.")
    if not hardened(settings) and not settings.auth_enabled:
        out.append("AUTHENTICATION IS DISABLED (AUTH_ENABLED=false): any caller can read and write any business. This is for local development and "
                   "isolated tests only; never expose this process to a network. Set AUTH_ENABLED=true to sign in.")
    return out


def schema_problem(database_url: str) -> str | None:
    """None when the database is at the revision the code expects; otherwise a plain statement of the mismatch."""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except Exception as exc:  # noqa: BLE001 - the reason is reported without connection details
        return f"the database could not be reached to verify its schema ({type(exc).__name__})."
    finally:
        engine.dispose()
    if current != head:
        return (f"the database schema is at revision {current!r} but this version needs {head!r}. Apply migrations first with "
                "`alembic upgrade head`; the application does not migrate on startup.")
    return None


def database_role_problem(database_url: str) -> str | None:
    """PostgreSQL only: the role the application connects as must not be a superuser, must not be able to bypass row security, and must not
    own the application tables. An owner (and any superuser) can disable or drop the append-only triggers, alter history and change schema;
    the runtime role should hold only the data privileges it needs. Migrations run under a separate owner role (MIGRATION_DATABASE_URL)."""
    if not database_url.startswith("postgresql"):
        return None
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user")).first()
            owns = conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname = current_schema() AND tableowner = current_user")).scalar()
    except Exception as exc:  # noqa: BLE001
        return f"the database role could not be inspected ({type(exc).__name__})."
    finally:
        engine.dispose()
    if row is None:
        return "the database role could not be inspected."
    bad = [n for n, v in zip(("superuser", "bypass row security", "create roles", "create databases"), row) if v]
    if bad:
        return "the application's database role has excessive privileges (" + ", ".join(bad) + "); connect as a plain role limited to data access."
    if owns:
        return ("the application's database role owns tables, so it could drop the append-only triggers or alter the schema; "
                "run migrations as a separate owner role and give the application role only SELECT/INSERT/UPDATE/DELETE (docs/DEPLOYMENT.md).")
    return None


def validate_security_config(settings, *, check_schema: bool = True) -> None:
    """Raise ``SecurityConfigError`` listing every problem, or log the development-mode warnings and return."""
    problems = security_problems(settings)
    if not problems and hardened(settings) and check_schema:
        for p in (schema_problem(str(settings.database_url)), database_role_problem(str(settings.database_url))):
            if p:
                problems.append(p[0].upper() + p[1:])
    if problems:
        raise SecurityConfigError(
            "DecisionGPT will not start with this security configuration:\n  - " + "\n  - ".join(problems)
            + "\nNo secret values are printed here. See docs/PRODUCTION_SECURITY_REVIEW.md."
        )
    for w in security_warnings(settings):
        logger.warning(w)
