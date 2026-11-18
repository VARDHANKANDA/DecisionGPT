"""Static checks of the deployment files. Docker is not run by this suite, so these only pin the security-relevant properties of the files
themselves (they cannot show the containers behave: that is stated as NOT TESTED in docs/PRODUCTION_SECURITY_REVIEW.md)."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
DOCKERFILE = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
SERVICES = COMPOSE["services"]


def test_postgres_publishes_no_host_port():
    assert "ports" not in SERVICES["postgres"], "the database must be reachable only over the compose network"


def test_backend_and_frontend_ports_are_bound_to_loopback_only():
    for name in ("backend", "frontend"):
        for mapping in SERVICES[name]["ports"]:
            assert str(mapping).startswith("127.0.0.1:"), f"{name} publishes {mapping} on every interface; TLS is terminated by a proxy in front"


def test_database_passwords_are_required_and_have_no_default():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for var in ("POSTGRES_PASSWORD", "APP_DB_PASSWORD"):
        uses = re.findall(r"\$\{" + var + r"([^}]*)\}", text)
        assert uses and all(u.startswith(":?") for u in uses), f"{var} must be required (':?'), never defaulted: {uses}"


def test_the_api_connects_as_the_application_role_and_migrations_as_the_owner():
    api = SERVICES["backend"]["environment"]["DATABASE_URL"]
    assert "APP_DB_USER" in api and "POSTGRES_USER" not in api
    mig = SERVICES["migrate"]["environment"]["MIGRATION_DATABASE_URL"]
    assert "POSTGRES_USER" in mig and SERVICES["migrate"]["profiles"] == ["tools"]     # an explicit operator step, not automatic on start


def test_the_api_container_is_not_given_the_schema_owners_credentials():
    env = SERVICES["backend"]["environment"]
    # env_file (.env) is shared with compose, so the owner's password would reach the API unless it is blanked here
    assert env["POSTGRES_PASSWORD"] == "" and env["POSTGRES_USER"] == "" and env["MIGRATION_DATABASE_URL"] == ""
    assert "env_file" not in SERVICES["frontend"] and "env_file" not in SERVICES["postgres"]


def test_the_database_sits_on_an_internal_network_that_the_web_tier_cannot_join():
    nets = COMPOSE["networks"]
    assert nets["db"]["internal"] is True, "the database network must have no route to the outside"
    assert SERVICES["postgres"]["networks"] == ["db"] and SERVICES["migrate"]["networks"] == ["db"]
    assert "db" not in SERVICES["frontend"]["networks"] and SERVICES["frontend"]["networks"] == ["web"]
    assert set(SERVICES["backend"]["networks"]) == {"db", "web"}, "the API is the only service on both networks"


def test_the_staging_overlay_trusts_exactly_one_proxy_address_and_publishes_only_loopback():
    class Loader(yaml.SafeLoader):                       # Compose's `!reset` tag clears an inherited value
        pass

    Loader.add_constructor("!reset", lambda loader, node: [])
    over = yaml.load((ROOT / "deploy" / "staging" / "docker-compose.staging.yml").read_text(encoding="utf-8"), Loader=Loader)
    ip = over["services"]["caddy"]["networks"]["web"]["ipv4_address"]
    env = (ROOT / "deploy" / "staging" / "make_env.sh").read_text(encoding="utf-8")
    assert f"TRUSTED_PROXIES={ip}/32" in env, "TRUSTED_PROXIES must be the proxy's own fixed address as a /32, never the subnet or the gateway"
    assert all(str(p).startswith("127.0.0.1:") for p in over["services"]["caddy"]["ports"])
    assert (over["services"]["backend"]["ports"] in ([], None)) and (over["services"]["frontend"]["ports"] in ([], None))


def test_the_role_script_is_mounted_into_the_database_container():
    mounts = " ".join(SERVICES["postgres"]["volumes"])
    assert "app-role.sql" in mounts and "docker-entrypoint-initdb.d" in mounts
    assert (ROOT / "deploy" / "postgres" / "app-role.sql").exists() and (ROOT / "deploy" / "postgres" / "initdb-app-role.sh").exists()


def test_containers_drop_privileges():
    for name in ("postgres", "backend", "frontend", "migrate"):
        assert "no-new-privileges:true" in SERVICES[name]["security_opt"]
    for name in ("backend", "frontend"):
        assert SERVICES[name]["cap_drop"] == ["ALL"]


def test_the_backend_image_runs_unprivileged_with_a_health_check_and_without_trusting_forwarded_headers():
    assert re.search(r"^USER\s+app\s*$", DOCKERFILE, re.M), "the API must not run as root"
    assert "HEALTHCHECK" in DOCKERFILE and "/api/v1/health" in DOCKERFILE
    cmd = DOCKERFILE.split("CMD", 1)[1]
    assert "--no-proxy-headers" in cmd and "--no-server-header" in cmd, "client addresses are decided by the application (TRUSTED_PROXIES), not uvicorn"


def test_the_role_script_never_grants_truncate_or_ownership():
    raw = (ROOT / "deploy" / "postgres" / "app-role.sql").read_text(encoding="utf-8")
    sql = " ".join(ln for ln in raw.splitlines() if not ln.strip().startswith("--")).upper()       # statements only, not the explanatory comments
    grants = " ".join(re.findall(r"GRANT[^;]*;", sql))
    assert "TRUNCATE" not in sql and "ALL PRIVILEGES" not in grants and "REFERENCES" not in grants and "TRIGGER" not in grants
    assert "NOSUPERUSER" in sql and "SUPERUSER" not in sql.replace("NOSUPERUSER", "")


def test_the_ci_workflow_runs_the_postgres_and_scanning_jobs():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert {"backend-sqlite", "backend-postgres", "frontend", "dependency-and-secret-scans"} <= set(ci["jobs"])
    assert ci["jobs"]["backend-postgres"]["services"]["postgres"]["image"].startswith("postgres:15")


def test_env_example_has_no_real_looking_secret_and_no_default_database_password():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^POSTGRES_PASSWORD=\s*$", env, re.M) and re.search(r"^APP_DB_PASSWORD=\s*$", env, re.M)
    assert re.search(r"^TRUSTED_PROXIES=\s*$", env, re.M)                                      # empty = trust no forwarded header


# ------------------------------------------------------------------ image contents (static; the images themselves are built and inspected in docs/STAGING_VERIFICATION.md)
FRONTEND_DOCKERFILE = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")


def test_the_backend_image_uses_the_python_the_pinned_scientific_stack_requires():
    # numpy 2.5 / scipy 1.18 / xgboost 3.4 / shap 0.52 (requirements.txt) need Python >= 3.12; a 3.11 base image cannot install them
    froms = re.findall(r"^FROM\s+(\S+)", DOCKERFILE, re.M)
    assert froms and all(f.startswith("python:3.12") for f in froms), froms


def test_the_backend_image_ships_no_compiler_and_installs_only_wheels():
    assert "build-essential" not in DOCKERFILE and "gcc" not in DOCKERFILE
    assert "--only-binary=:all:" in DOCKERFILE, "a package without a wheel must fail the build, not pull a compiler in"
    assert "chmod -R go-w /app/backend" in DOCKERFILE and "-perm /6000" in DOCKERFILE      # code not writable by the service user; setuid bits stripped
    assert "pip uninstall -y pip" in DOCKERFILE, "no package manager in the runtime image"
    assert "pip uninstall -y pip" in DOCKERFILE, "no package manager in the runtime image"
    assert "requirements-runtime.txt" in DOCKERFILE and "requirements.txt" not in DOCKERFILE.replace("requirements-runtime.txt", "")


def test_the_runtime_requirements_are_the_full_requirements_without_the_test_tools():
    full = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    runtime = (ROOT / "backend" / "requirements-runtime.txt").read_text(encoding="utf-8")

    def pins(text):
        return [ln.split("#")[0].strip() for ln in text.splitlines() if ln.split("#")[0].strip()]

    # the one deliberate difference: the image uses the CPU-only build of the SAME xgboost release (no CUDA libraries)
    expected = [p.replace("xgboost==", "xgboost-cpu==") for p in pins(full.split("# testing")[0])]
    assert pins(runtime) == expected
    assert "xgboost-cpu==3.4.0" in pins(runtime) and "xgboost==3.4.0" in pins(full)
    assert not any(p.lower().startswith(("pytest", "coverage")) for p in pins(runtime))


def test_the_frontend_image_runs_unprivileged_and_listens_on_every_interface():
    assert all(f.startswith("node:24") for f in re.findall(r"^FROM\s+(\S+)", FRONTEND_DOCKERFILE, re.M)), "node 20 reached end of life in April 2026"
    assert all(f.startswith("node:24") for f in re.findall(r"^FROM\s+(\S+)", FRONTEND_DOCKERFILE, re.M)), "node 20 reached end of life in April 2026"
    assert re.search(r"^USER\s+node\s*$", FRONTEND_DOCKERFILE, re.M), "the web server must not run as root"
    assert "HOSTNAME=0.0.0.0" in FRONTEND_DOCKERFILE and "HEALTHCHECK" in FRONTEND_DOCKERFILE
    assert "--chown=node" not in FRONTEND_DOCKERFILE, "the server's code must stay root-owned (not writable by the user that runs it)"
    assert "-perm /6000" in FRONTEND_DOCKERFILE and "rm -rf /usr/local/lib/node_modules/npm" in FRONTEND_DOCKERFILE and "-name '*.map' -delete" in FRONTEND_DOCKERFILE


def test_the_docker_build_context_is_an_allowlist_that_excludes_env_files_and_databases():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    rules = [ln.strip() for ln in ignore if ln.strip() and not ln.strip().startswith("#")]
    assert rules[0] == "*", "everything is excluded unless named"
    allowed = {r[1:] for r in rules if r.startswith("!") and not r.endswith(".env.example")}
    assert allowed == {"backend", "ml", "data/platform"}, allowed
    assert "**/.env" in rules and "**/.env.*" in rules and "**/*.db" in rules


def test_the_ci_misconfiguration_scan_passes_one_path_per_trivy_invocation():
    """`trivy config` takes a single path: two paths is a usage error that fails every run (found by running the workflow's commands)."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "trivy:latest config" in line:
            args = line.split("trivy:latest config", 1)[1]                       # what follows the subcommand: options and paths only
            assert len(re.findall(r'(?:^|\s)"?/src[^\s"]*"?', args)) == 1, line


def test_uploaded_originals_live_on_a_named_volume_the_service_user_can_write():
    assert any(str(v).endswith(":/app/data/business_uploads") and not str(v).startswith(".") for v in SERVICES["backend"]["volumes"])
    assert "business-uploads" in COMPOSE["volumes"]
    assert "/app/data/business_uploads" in DOCKERFILE and "chown -R app:app" in DOCKERFILE
