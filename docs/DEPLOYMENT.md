# DecisionGPT — Deployment Specification

## 1. Development Target

The complete prototype must run locally using Docker Compose.

## 2. Services

- frontend
- backend
- postgres

Optional:
- worker

## 3. Environment

Copy:

```bash
cp .env.example .env
```

Fill only required secrets.

## 4. Launch

```bash
docker compose up --build
```

## 5. Database

PostgreSQL is initialized through environment variables and Alembic migrations.

Run migrations:

```bash
docker compose exec backend alembic upgrade head
```

## 6. Production Note

The capstone deployment is a research prototype.

Before real commercial deployment, add:
- managed database;
- object storage;
- secure authentication;
- rate limiting;
- monitoring;
- backups;
- secrets manager;
- privacy/compliance review.

## 7. Data

Do not commit private business data.

Only commit:
- synthetic sample data;
- public datasets where license permits;
- schema documentation.
