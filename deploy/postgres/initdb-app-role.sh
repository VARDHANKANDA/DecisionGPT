#!/bin/sh
# Runs once, when the PostgreSQL container first initialises its data directory (mounted into /docker-entrypoint-initdb.d).
# POSTGRES_USER is the schema OWNER (migrations); APP_DB_USER / APP_DB_PASSWORD is the runtime role the API connects as.
set -eu
: "${APP_DB_USER:?APP_DB_USER is required}" "${APP_DB_PASSWORD:?APP_DB_PASSWORD is required}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v owner_role="$POSTGRES_USER" -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" \
  -f /deploy/app-role.sql
