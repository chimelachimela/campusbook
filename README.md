# CampusBook

A client/server Student Records Management System with database backup and recovery.

## Project status

**Stage:** Initial scaffold

CampusBook is being developed as an academic Data Communications project to demonstrate how a client communicates with an application server over HTTP, how the server manages persistent student records, and how an operator can back up and restore the database.

## Planned architecture

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
        +---- Restore service <--- selected verified snapshot
```

## Core scope

- Dashboard with student and department summaries
- Student records: create, view, update, delete, search
- Department records
- Results management
- Database backup: create timestamped snapshots and list available backups
- Database recovery: validate and restore a selected backup
- Activity log for important administrative actions

## Technology

| Layer | Technology |
| --- | --- |
| Client | React, TypeScript, Vite |
| API server | Python, FastAPI |
| Database | SQLite |
| API style | REST over HTTP with JSON |
| Validation | Pydantic |
| Tests | Pytest and FastAPI TestClient |

## Development

The repository will contain separate `frontend/` and `backend/` directories. See the setup instructions in each directory as they are added.

## Academic demonstration

The backup/recovery demonstration must use the actual SQLite database file. The operator should create records, create a backup, introduce a controlled data-loss scenario, restore the backup, and verify that the records return. A successful API response alone is not sufficient evidence of recovery.

## Important

This is an academic demonstration system. Do not use real student personal data or deploy it as a production student information system without authentication, authorization, secure deployment, audit hardening, and appropriate privacy controls.
