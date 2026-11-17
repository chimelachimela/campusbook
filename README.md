# CampusBook

A client/server Student Records Management System with database backup and recovery.

## Project status

**Stage:** Initial MVP implementation on `feature/campusbook-mvp`.

CampusBook demonstrates how a browser client communicates with an application server over HTTP, how the server manages persistent student records, and how an operator can back up and restore the database.

## Architecture

```text
React + TypeScript client
        |
        | HTTP / JSON (REST)
        v
FastAPI application server
        |
        | SQL
        v
SQLite database
        |
        +---- Backup service ----> timestamped database snapshots
        |
        +---- Restore service <--- validated snapshot
```

## Implemented in this branch

- Dashboard with live student, department, and backup counts
- Student records: create, list, and search
- Department list and student counts
- Backup creation using SQLite's online backup API
- Backup history with file sizes and timestamps
- Restore flow with integrity validation and a pre-restore safety copy
- Activity log entries for student and backup operations
- Responsive React administration interface
- API test covering student creation, deletion, backup, and restore

## Technology

| Layer | Technology |
| --- | --- |
| Client | React, TypeScript, Vite |
| API server | Python, FastAPI |
| Database | SQLite |
| API style | REST over HTTP with JSON |
| Validation | Pydantic |
| Tests | Pytest and FastAPI TestClient |

## Run locally

### 1. Start the backend

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment, then install dependencies:

**Windows PowerShell**
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**macOS / Linux**
```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

### 2. Start the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`).

### 3. Run backend tests

From the repository root, with the backend virtual environment active:

```bash
cd backend
pytest
```

## Backup and recovery demonstration

1. Start both the API and frontend.
2. Add a student record.
3. Open **Backup & Recovery** and create a snapshot.
4. Delete the student record through the API docs at `/docs` (or the student delete endpoint).
5. Confirm the record is gone.
6. Restore the earlier snapshot from the Backup & Recovery page.
7. Confirm the student record returns.

A successful HTTP response alone is not proof of recovery: verify that the data itself has returned.

## Current limitations

This is an academic demonstration system, not a production student information system. Student creation and listing/search are implemented; editing/deletion are currently API-only. Results are a planned module and are not yet implemented. Authentication, role-based authorization, production deployment hardening, backup retention, and off-site backup copies are also outside this initial MVP.

Do not use real student personal data in this public academic demonstration repository.
