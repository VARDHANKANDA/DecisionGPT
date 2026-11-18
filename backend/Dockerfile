# Build context is the REPO ROOT (see docker-compose.yml's `build.context: .`),
# not backend/ — the runtime app imports `ml.*` (shared feature engineering
# between offline training and online inference, see AGENTS.md) which lives
# as a sibling of backend/, so both must land in the same image.
#
# Python 3.12: the pinned numpy / scipy / xgboost / shap releases require it (an earlier revision of this file used 3.11 and could not install
# them). The tests and the audits ran on 3.12.

# ---- stage 1: install the dependencies into a virtualenv. Wheels only: if a pinned package had no wheel the build FAILS instead of
# pulling a compiler into the image.
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY backend/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip install --only-binary=:all: -r /tmp/requirements-runtime.txt

# ---- stage 2: the runtime image. No pip cache, no compilers, no test tools.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/opt/venv/bin:$PATH

# libgomp: the OpenMP runtime that the xgboost / scikit-learn wheels load. `upgrade` picks up Debian security fixes published after the base
# image was built (the image is rebuilt from source, so this trades bit-for-bit reproducibility for fewer known vulnerabilities).
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY backend ./backend
COPY ml ./ml
COPY data/platform ./data/platform

# Run as an unprivileged user: a flaw in the application then does not hand an attacker root in the container. The model registry and the
# research upload folder are the only places the API writes; mount volumes there owned by uid 10001 (docs/DEPLOYMENT.md).
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/models /app/experiments/results /app/data/research_uploads /app/data/business_uploads \
    && chown -R app:app /app/models /app/experiments/results /app/data/research_uploads /app/data/business_uploads
# The application code must not be writable by the user that runs it (a checkout from a Windows or shared mount arrives with mode 777), and the
# base image's setuid/setgid binaries are not needed by a service that never switches user.
RUN chmod -R go-w /app/backend /app/ml /app/data/platform
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true
# A service has no use for a package manager at run time: remove pip (and the build helpers) from the virtualenv and from the base interpreter.
RUN /opt/venv/bin/python -m pip uninstall -y pip setuptools wheel \
    && /usr/local/bin/python -m pip uninstall -y pip setuptools wheel
USER app

WORKDIR /app/backend

EXPOSE 8000

# Liveness only: /api/v1/health returns {"status", "dependencies"} and discloses no configuration, version or host detail.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

# --no-proxy-headers: uvicorn must not rewrite the client address from X-Forwarded-For by itself. The application decides, and only for the
# proxies listed in TRUSTED_PROXIES (app/core/client_ip.py). --no-server-header: do not advertise the server software.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]
