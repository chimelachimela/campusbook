# CampusBook

A React + FastAPI student records management system backed by PostgreSQL.

## Architecture

```text
React + TypeScript + Vite
        | HTTPS / JSON
        v
FastAPI application on Render
        | psycopg / TLS
        v
Neon PostgreSQL
        +-- departments
        +-- students
        +-- results
        +-- activity log
        +-- logical JSON backup snapshots
```

## Features

- Dashboard with student, active-record, department, and backup counts
- Student create, search, update, and delete
- Department directory and student counts
- Course result recording, listing, and deletion
- Activity log
- Logical JSONB database snapshots with validation and transactional restore
- A pre-restore safety snapshot
- Responsive React administration interface

## Database setup

The production database schema is in `backend/migrations/001_initial_postgres.sql`.

1. Create a Neon PostgreSQL project and database.
2. Create a restricted runtime role (the deployment role should not own the schema).
3. Connect as the database owner and apply the migration SQL once.
4. Set `DATABASE_URL` on the API service to the runtime role's connection string.
5. Do not set `CAMPUSBOOK_AUTO_MIGRATE=true` in production. The app role intentionally does not have schema-owner privileges.

The application uses `psycopg` and PostgreSQL. SQLite is no longer used by the deployed backend.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
```

Set `DATABASE_URL` to a local PostgreSQL database and apply `migrations/001_initial_postgres.sql` as its owner. Then run:

```bash
uvicorn app.main:app --reload
```

API documentation: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` to the API origin when building for deployment. The local default is `http://localhost:8000`.

## Tests

Backend integration tests require a disposable PostgreSQL database in `DATABASE_URL`. They apply the schema migration, reset test tables, and exercise CRUD, department/result relationships, backup/restore, and activity logging.

```bash
cd backend
pytest -v
```

Frontend production build:

```bash
cd frontend
npm install
npm run build
```

GitHub Actions runs both checks, using a PostgreSQL 17 service for backend integration tests.

## Backups and recovery

The application stores logical JSONB snapshots in the same Neon database. Restores validate the snapshot, remap student IDs so foreign-key relationships remain correct, and create a pre-restore safety snapshot in the same transaction.

**Important limitation:** these in-database snapshots are for application-level recovery demonstrations, not independent disaster recovery. They do not protect against loss or deletion of the entire Neon project. Configure Neon-managed backups/restore or export snapshots to independent storage before using real institutional data.

## Deployment

The API and frontend are deployed as separate Render services. The API requires `DATABASE_URL` and `CAMPUSBOOK_CORS_ORIGINS`. The frontend requires `VITE_API_URL` at build time. Both services can use Render's free plan; free API services may sleep after inactivity.

Do not use real student personal data in this public academic demonstration project.
