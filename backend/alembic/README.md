# Alembic Migrations

This directory contains the database migration scripts for JobHunt AI.

## Setup

1. Install Alembic:
   ```bash
   pip install alembic
   ```

2. Initialize the migration directory:
   ```bash
   alembic init alembic
   ```

## Usage

### Create a new migration:
```bash
alembic revision -m "message"
alembic upgrade head
```

### Generate a migration from the current schema:
```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

### Downgrade:
```bash
alembic downgrade -1
```

## Configuration

The migration environment uses the application's own SQLAlchemy models and
reads the connection URL from the application settings, so the same pipeline
works against SQLite and PostgreSQL.

The migration scripts are written in Python and use the application's models.
The ``env.py`` file is configured to use the application's settings and models.

## Notes

- The migrations are designed to work with both SQLite and PostgreSQL.
- Always test migrations in a development environment before applying them to production.