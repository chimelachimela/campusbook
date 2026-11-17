# CampusBook

A university student records, course registration and results management system built as a client/server academic project.

## Live demonstration

- **Application:** https://campusbook-frontend.onrender.com
- **API documentation:** https://campusbook-api-live.onrender.com/docs
- **API health:** https://campusbook-api-live.onrender.com/api/health

The frontend is a Render Static Site. The free FastAPI service may sleep after 15 minutes without inbound traffic; the first request after idle can take about a minute. The Vercel deployment is currently a protected preview and is not the public live URL.

## Version 1 roles

- **Administrator:** manages student and academic records, course offerings, accounts, result approval and backups.
- **Lecturer:** views assigned class rosters, imports/enters marks, and submits results.
- **Student:** registers for eligible courses and views their own published results.

Public account sign-up is disabled. Student and lecturer accounts are provisioned by an administrator. Student email is not collected.

## Architecture

```text
React + TypeScript + Vite
        | HTTPS / JSON
        v
FastAPI application server
        | psycopg / TLS
        v
Neon PostgreSQL
        +-- faculties / departments
        +-- students / lecturers
        +-- academic sessions / semesters
        +-- courses / course offerings
        +-- student course registrations
        +-- course grades / approval state
        +-- accounts / sessions / activity log
        +-- versioned JSONB backup snapshots
```

See [docs/architecture.md](docs/architecture.md) for the complete architecture and API flow, and [docs/final-v1-scope.md](docs/final-v1-scope.md) for the agreed project boundary.

## Features

- Faculty → department → student organisation
- Student records with DE/year/four-digit matriculation format
- Course catalogue, academic sessions and semesters
- Student self-service course registration
- Lecturer assignment and class roster
- CSV and grid-based grade entry, submission and administrator approval
- Role-based sign-in for administrators, lecturers and students
- Application-level JSONB backup, validation and recovery
- Responsive role-specific interfaces

## Database setup

Database migrations are in `backend/migrations/`. Apply them in filename order as the database owner:

1. `001_initial_postgres.sql`
2. `002_academic_registration_auth.sql`

The production runtime role must not own the schema. Set `DATABASE_URL` to the restricted application role's connection string. Do not set `CAMPUSBOOK_AUTO_MIGRATE=true` in production.

The first administrator is created once through the bootstrap endpoint using `CAMPUSBOOK_BOOTSTRAP_SECRET`. Keep that secret private and remove/rotate it after the initial administrator is created.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
```

Set `DATABASE_URL` to a disposable PostgreSQL database. Apply the migrations as the database owner, then run:

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

Set `VITE_API_URL` to the API origin. The local default is `http://localhost:8000`.

## Tests

Backend integration tests require a disposable PostgreSQL database in `DATABASE_URL`. They apply migrations, reset test tables and exercise authentication, role restrictions, student CRUD, course registration, lecturer grade entry, approval, backup and recovery.

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

GitHub Actions runs both checks with PostgreSQL 17.

## Backup and recovery limitation

JSONB snapshots are stored in the same Neon database. They support the assignment's application-level backup/recovery demonstration, but they are not independent disaster recovery. Do not use real student records in this public academic demonstration project. Use an independent database backup/export before handling institutional data.
