# DecisionGPT — Deployment

This is the operator's runbook. It states what the repository provides, what you must supply, and what was and was not verified. The evidence
and the release decisions are in [`PRODUCTION_SECURITY_REVIEW.md`](PRODUCTION_SECURITY_REVIEW.md); read its sections 9–11 before exposing
anything to a network.

## 1. Environments

`ENVIRONMENT` selects how strict the application is about its own configuration.

| Value | Intended use | Authentication | Startup |
|---|---|---|---|
| `development` (default) | one developer's machine | may be off (`AUTH_ENABLED=false`, a loud warning is logged) or on | starts |
| `test` | automated tests | may be off | starts |
| `staging`, `production` ("hardened") | any shared or networked deployment | **must be on** | **refuses to start** unless every check in section 2 passes |
| anything else (for example `prod`) | — | — | refuses to start (a typo must not silently disable protections) |

`AUTH_ENABLED=false` is never a deployment mode. With it off, any caller who can reach the process can read and write every business.

## 2. What a hardened start checks (`backend/app/core/security_config.py`)

The process exits with a list of problems (names and rules only; no secret value is ever printed) unless all of these hold:

* authentication is on; `JWT_SECRET`, `SECRET_KEY` and (while the Research Console is enabled) `RESEARCH_CONSOLE_TOKEN` are real random values of
  at least 32 / 32 / 24 characters, not placeholders;
* `JWT_TTL_SECONDS` is between 60 and 86 400; `JWT_ISSUER` / `JWT_AUDIENCE` are not empty; `JWT_SECRET_PREVIOUS`, when set, is a real, different secret;
* `RATE_LIMIT_ENABLED` is true; `TRUSTED_PROXIES`, when set, contains only valid addresses or CIDR ranges;
* `DATABASE_URL` is PostgreSQL with non-default credentials; `FRONTEND_ORIGIN` is an `https://` origin, not localhost or a wildcard;
* the database is at the migration head (the application never migrates on startup);
* the database role the API connects as is **not** a superuser, cannot create roles or databases or bypass row security, and **owns no tables**.

The interactive API documentation (`/docs`, `/redoc`, `/openapi.json`) is off in hardened environments unless `DOCS_ENABLED=true`.

## 3. Topology the repository supports

```
internet ──TLS──► reverse proxy (you provide) ──► backend (uvicorn, 1..N processes/replicas) ──► PostgreSQL 15
                                              └──► frontend (Next.js standalone)
```

* The application provides **no TLS**. A TLS-terminating proxy must serve both the web application and the API over https (`deploy/Caddyfile.example`
  is an unverified starting point). HSTS is sent by the API and the web server in production, and browsers honour it only over https.
* Any number of API processes or replicas may run against one PostgreSQL: the rate-limit counters, the revoked-token list and all data live in the
  database (verified with two separate server processes, section 7).
* Run PostgreSQL where only the API and the migration job can reach it. `docker-compose.yml` publishes **no** database port and puts the database on an
  **internal** network shared only with the API and the migration job; the web server and any proxy are on a separate `web` network (verified at run time:
  the frontend and the proxy cannot reach the database).
* The compose file does **not** pass the schema owner's credentials to the API: `.env` is shared with Compose, so the backend service blanks
  `POSTGRES_USER`, `POSTGRES_PASSWORD` and `MIGRATION_DATABASE_URL` (in the official postgres image that owner is a **superuser**). If you add your own
  variables that hold owner credentials, blank them for the backend too.
* The images: `backend/Dockerfile` (Python 3.12, multi-stage, wheels only, runtime requirements from `backend/requirements-runtime.txt` which uses the CPU-only
  `xgboost-cpu` build of the same release, no compilers or package manager, code not writable by the service user, uid 10001) and `frontend/Dockerfile`
  (Node 24, root-owned code, no `npm`, no source maps, uid 1000). `NEXT_PUBLIC_API_BASE_URL` is baked into the web bundle **at build time** and also fixes its
  Content-Security-Policy, so build the frontend with the final public API URL (`.env` is read by Compose for this).
* A staging overlay with a TLS proxy and the full verification script are in `deploy/staging/` (section 10).

## 4. Database roles, migrations and secrets

Two roles, created by `deploy/postgres/app-role.sql` (the compose file runs it for you on first initialisation):

| Role | Setting | Can | Cannot |
|---|---|---|---|
| owner (`POSTGRES_USER`) | `MIGRATION_DATABASE_URL`, used only by `alembic` and the `migrate` job | create and alter the schema | — |
| application (`APP_DB_USER`) | `DATABASE_URL`, used by the API | `SELECT`/`INSERT`/`UPDATE`/`DELETE` | create, alter or drop tables; disable or drop the append-only triggers; `TRUNCATE`; be a superuser |

The append-only triggers on saved forecasts, responses and observations (migration 0014) stop the application role from editing history. They do
**not** stop the owner role or a superuser: keep those credentials out of the application and the runtime environment.

Migrations are an explicit step, never automatic:

```bash
docker compose --profile tools run --rm migrate        # alembic upgrade head as the owner role
```

Outside compose: set `MIGRATION_DATABASE_URL` to the owner's URL and run `alembic upgrade head` from `backend/`. Never run a migration against a live
production database without a current backup (section 6) and a staging rehearsal. Downgrades (`alembic downgrade -1`) were verified on a scratch
database, including down to the first revision and back, but a downgrade discards the data of the dropped tables and columns.

Secrets: generate each with `openssl rand -hex 24` (hex needs no URL escaping). They come from `.env` (git-ignored and excluded from images) or the
process environment, or from your platform's secret store. `docker-compose.yml` requires both database passwords and has no default for either. Never
commit them, put them in the frontend, or paste them into logs or tickets.

**Rotating `JWT_SECRET`:** put the current value in `JWT_SECRET_PREVIOUS`, set a new `JWT_SECRET`, restart. Tokens signed with the old secret keep
verifying (nothing is ever signed with it). Remove `JWT_SECRET_PREVIOUS` after one `JWT_TTL_SECONDS` (default 12 hours) and restart again. To end every
session at once instead, rotate without setting `JWT_SECRET_PREVIOUS`.

**Rotating the application database password:** set the new password, re-run `deploy/postgres/app-role.sql` as an administrator (it is idempotent and
resets the password), update `DATABASE_URL`, restart.

## 5. Reverse proxy and client addresses

Sign-in throttling is keyed on the caller's address, so the application must know it correctly.

* `TRUSTED_PROXIES` (comma-separated IPs or CIDR ranges) lists the proxies whose `X-Forwarded-For` header may be believed. **Empty means no header is ever
  read** and the address is the TCP peer. The header is read from the right, skipping trusted proxies; everything to the left of the first untrusted
  address is ignored, so a forged `X-Forwarded-For` cannot pick a bucket.
* Behind a proxy you operate, set `TRUSTED_PROXIES` to that proxy. Left empty, every caller shares the proxy's address and the per-address limits apply
  to all users together (a hardened start logs a warning for this).
* The backend image starts uvicorn with `--no-proxy-headers` so only the application interprets forwarding headers.
* Have the proxy limit request bodies (the API bounds uploads and individual fields, not every request body).

## 6. Backups and restore

Verified on PostgreSQL 15.17 with `pg_dump` / `pg_restore` (data, the three triggers, the schema version and the privileges survived; the append-only
triggers still refused edits; a hardened start succeeded on the restored database):

```bash
# backup (custom format), as the owner role
pg_dump -Fc -h <host> -U <owner> -d decisiongpt -f decisiongpt-$(date +%F).dump

# restore into a NEW database, then point DATABASE_URL at it
createdb -h <host> -U <owner> decisiongpt_restored
pg_restore -h <host> -U <owner> -d decisiongpt_restored --no-owner --role <owner> decisiongpt-<date>.dump
```

Store backups under the same access control as the database, test a restore on a schedule, and keep the dump's retention in line with your privacy
obligations. Not verified here: scheduled backups, off-site copies, point-in-time recovery, and restoring onto your actual infrastructure.

**Uploaded files are not in the database dump.** The unchanged original of every uploaded business file is kept under `BUSINESS_UPLOAD_PATH` (compose: the `business-uploads` volume, `/app/data/business_uploads`, writable by the service user only). It is customer data. Back it up and restore it together with the database; a restore without it still works, but a mapping that was waiting for confirmation can then no longer be resumed (the person is asked to upload the file again). See `docs/DATA_UPLOADS_AND_EVALUATION.md`.

## 7. Authentication behaviour in each environment

| | development | test (suite) | staging / production |
|---|---|---|---|
| authentication | optional | off by fixture, on in security tests | required |
| rate limiting | **on** (defaults below) | off by fixture; its own tests turn it on | **required on**; startup refuses otherwise |
| counters kept in | the application database | in-memory SQLite or a file | PostgreSQL, shared by every process |
| forwarded headers | never trusted unless `TRUSTED_PROXIES` is set | n/a | trusted only from `TRUSTED_PROXIES` |

Defaults (each is a setting; the window is `RATE_LIMIT_WINDOW_SECONDS`, 15 minutes): 5 failed sign-ins per account and address, 20 per address
(any account), 40 per account (any address); 10 sign-ups per address per hour; 5 failed current-password checks per user. Nothing locks an account: a
limit only delays further attempts until its window ends, and is answered with HTTP 429 and `Retry-After` before the password is examined. Fixed
windows allow a burst of up to about twice a limit across a boundary.

Operator recovery (there is no self-service reset: it needs a verified email channel the product does not have):

```bash
python backend/scripts/create_admin.py   --email admin@example.com          # create or promote an administrator (prompts for the password)
python backend/scripts/reset_password.py --email owner@example.com          # new password; ends every session of the account
python backend/scripts/reset_password.py --email owner@example.com --deactivate
```

## 8. Local development

```bash
cp .env.example .env            # then set POSTGRES_PASSWORD and APP_DB_PASSWORD (required by compose), or use SQLite without compose
docker compose up --build       # ports are bound to 127.0.0.1 only; the database publishes none
docker compose --profile tools run --rm migrate
```

Without Docker: `DATABASE_URL=sqlite:///./backend/dev.db`, `alembic upgrade head` from `backend/`, `uvicorn app.main:app` and `npm run dev` in `frontend/`.
For a database shell: `docker compose exec postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"`.

The API container runs as uid 10001. The bind-mounted `models/` and `experiments/results/` folders must be writable by that user
(`chown 10001:10001 models experiments/results`), or the Research Console cannot save models.

## 9. Verification status of this file's claims

| Claim | Status |
|---|---|
| Hardened start refusals (settings, role, schema head) | Verified, including against a real PostgreSQL |
| Roles script, triggers, privileges, backup/restore | Verified on PostgreSQL 15.17 (Windows build) and, through the containers, on 15.19 (Linux, Alpine) |
| Shared throttle state across two server processes | Verified on PostgreSQL 15.17 |
| `docker-compose.yml`, both Dockerfiles, the compose init-script role bootstrap | **Verified 2026-10-21**: built, inspected, scanned and run on a Linux container engine (`STAGING_VERIFICATION.md`, 136 checks) |
| `deploy/staging/Caddyfile.staging`: TLS (private CA), redirect, HSTS, headers, CORS, client addressing through the proxy | **Verified** against a running proxy; public-CA issuance, a real domain, renewal and browser-level TLS: **Not tested** |
| `deploy/Caddyfile.example` (public certificates) | **Not tested** (differs from the verified staging file only in certificate handling) |
| `.github/workflows/ci.yml` | **Not executed** on a hosted runner; the same commands were run locally |
| Backups on a schedule, monitoring and alerting | **Not provided** |

## 10. Staging overlay and verification

```bash
sh deploy/staging/make_env.sh                                   # throwaway .env with fresh random secrets; refuses to overwrite one
echo "127.0.0.1 staging.example.test" | sudo tee -a /etc/hosts
docker compose -f docker-compose.yml -f deploy/staging/docker-compose.staging.yml --profile tools build
python3 deploy/staging/verify_staging.py --report staging_report.json
docker compose -f docker-compose.yml -f deploy/staging/docker-compose.staging.yml --profile tools down -v
```

The overlay adds Caddy (local CA, `tls internal`), unpublishes the backend and frontend ports, and gives Caddy a fixed address that `TRUSTED_PROXIES`
lists as a `/32`. The script runs about 135 checks in 7 minutes and exits non-zero on any failure. Never run it against a real database or with real secrets.
Details and results: `STAGING_VERIFICATION.md`.
