#!/bin/sh
# Writes ./.env for the DISPOSABLE staging stack, with fresh random throwaway secrets. Nothing is printed. Never run this where a real .env exists:
# it refuses to overwrite one. The values are for a stack that is destroyed afterwards (docker compose ... down -v).
set -eu
if [ -e .env ] && [ "${FORCE:-}" != "1" ]; then
  echo ".env already exists; refusing to overwrite (set FORCE=1 on a disposable checkout)" >&2
  exit 1
fi
rand() { openssl rand -hex "$1"; }
umask 077
cat > .env <<EOF
ENVIRONMENT=production
LOG_LEVEL=INFO
AUTH_ENABLED=true
JWT_SECRET=$(rand 32)
SECRET_KEY=$(rand 32)
RESEARCH_CONSOLE_ENABLED=true
RESEARCH_CONSOLE_TOKEN=$(rand 24)
FRONTEND_ORIGIN=https://staging.example.test
TRUSTED_PROXIES=172.30.0.10/32
NEXT_PUBLIC_API_BASE_URL=https://staging.example.test/api/v1
POSTGRES_USER=decisiongpt_owner
POSTGRES_PASSWORD=$(rand 24)
POSTGRES_DB=decisiongpt
APP_DB_USER=decisiongpt_app
APP_DB_PASSWORD=$(rand 24)
OPENAI_API_KEY=
EOF
echo ".env written (mode 600); $(wc -l < .env) lines"
