-- Least-privilege runtime role for DecisionGPT.
--
-- Run ONCE per database (and again after a password rotation), connected to that database as an ADMINISTRATOR that may create roles (in the
-- Docker image POSTGRES_USER is a superuser; on a managed service use its admin role). owner_role is the role that OWNS the schema - the role
-- migrations run as (MIGRATION_DATABASE_URL):
--
--   psql -v ON_ERROR_STOP=1 -d decisiongpt -U <owner> \
--        -v owner_role=<owner> -v app_user=decisiongpt_app -v app_password='<generated secret>' -f deploy/postgres/app-role.sql
--
-- The application then connects as app_user (DATABASE_URL). That role can read and write rows and nothing else: it cannot create, alter or
-- drop tables, cannot disable or drop the append-only triggers, cannot TRUNCATE, and is not a superuser. A hardened start refuses a
-- connection role that is a superuser or owns the tables (app/core/security_config.py: database_role_problem).
--
-- Not covered here: a database superuser or the owner role can still do anything - protect those credentials like the keys to the data.

SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION', :'app_user')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec
-- always (re)set the password and the restrictive attributes, so this script is also the rotation step
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION', :'app_user', :'app_password') \gexec

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user') \gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_user";

-- tables and sequences that already exist ...
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
-- ... and every one a later migration (run by owner_role) creates
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";
-- TRUNCATE, REFERENCES and TRIGGER are deliberately NOT granted (TRUNCATE would bypass the append-only row triggers).
