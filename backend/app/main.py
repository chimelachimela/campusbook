from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", "")
MIGRATION_FILE = BASE_DIR / "migrations" / "001_initial_postgres.sql"
BACKUP_VERSION = 1

app = FastAPI(
    title="CampusBook API",
    description="Student records management with PostgreSQL backup and recovery.",
    version="0.2.0",
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CAMPUSBOOK_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudentInput(BaseModel):
    matric_number: str = Field(min_length=2, max_length=40)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=100)
    level: str = Field(min_length=1, max_length=20)
    status: str = Field(default="Active", pattern="^(Active|Inactive)$")


class DepartmentInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=12)


class ResultInput(BaseModel):
    student_id: int = Field(gt=0)
    course_code: str = Field(min_length=2, max_length=20)
    course_title: str = Field(min_length=2, max_length=120)
    score: float = Field(ge=0, le=100)
    semester: str = Field(min_length=3, max_length=40)


@contextmanager
def connect():
    """Open a short-lived PostgreSQL connection and manage its transaction."""
    url = os.getenv("DATABASE_URL", DATABASE_URL)
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    with psycopg.connect(url, row_factory=dict_row) as db:
        yield db


def log_action(db: psycopg.Connection, action: str, details: str) -> None:
    db.execute(
        "INSERT INTO activity_logs (action, details, created_at) VALUES (%s, %s, %s)",
        (action, details, datetime.now(timezone.utc)),
    )


def initialize_database() -> None:
    """Apply the checked-in schema migration. Run as the Neon owner, not the app role."""
    if not MIGRATION_FILE.is_file():
        raise RuntimeError(f"Database migration not found: {MIGRATION_FILE}")
    statements = [part.strip() for part in MIGRATION_FILE.read_text().split(";") if part.strip()]
    with connect() as db:
        for statement in statements:
            db.execute(statement)
        with db.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO departments (name, code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                [
                    ("Computer Engineering", "CPE"),
                    ("Computer Science", "CSC"),
                    ("Electrical Engineering", "EEE"),
                    ("Accountancy", "ACC"),
                ],
            )


@app.on_event("startup")
def startup() -> None:
    # Production schema is provisioned once using the owner connection.
    # Enable this only in isolated tests/development environments.
    if os.getenv("CAMPUSBOOK_AUTO_MIGRATE", "").lower() == "true":
        initialize_database()


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return value


def _snapshot_tables(db: psycopg.Connection) -> dict[str, Any]:
    tables = {}
    for table in ("departments", "students", "results", "activity_logs"):
        rows = db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        tables[table] = [
            {key: _json_value(value) for key, value in row.items()}
            for row in rows
        ]
    return {"format_version": BACKUP_VERSION, "tables": tables}


def _store_snapshot(db: psycopg.Connection, snapshot: dict[str, Any]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    filename = f"campusbook-{timestamp}.json"
    db.execute(
        "INSERT INTO backup_snapshots (filename, snapshot, created_at) VALUES (%s, %s, %s)",
        (filename, Jsonb(snapshot), datetime.now(timezone.utc)),
    )
    return filename


def _validate_snapshot(snapshot: Any) -> dict[str, list[dict[str, Any]]]:
    required = {
        "departments": {"name", "code"},
        "students": {
            "id", "matric_number", "first_name", "last_name", "email",
            "department", "level", "status", "created_at",
        },
        "results": {"student_id", "course_code", "course_title", "score", "semester"},
        "activity_logs": {"action", "details", "created_at"},
    }
    if not isinstance(snapshot, dict) or snapshot.get("format_version") != BACKUP_VERSION:
        raise HTTPException(status_code=422, detail="Unsupported or invalid backup format.")
    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        raise HTTPException(status_code=422, detail="Backup tables are missing.")
    validated: dict[str, list[dict[str, Any]]] = {}
    for table, columns in required.items():
        rows = tables.get(table)
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not columns.issubset(row.keys()) for row in rows
        ):
            raise HTTPException(status_code=422, detail=f"Backup validation failed for {table}.")
        validated[table] = rows
    return validated


@app.get("/api/health")
def health() -> dict[str, str]:
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok", "service": "CampusBook API", "database": "connected"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    with connect() as db:
        total = db.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
        active = db.execute("SELECT COUNT(*) AS count FROM students WHERE status='Active'").fetchone()["count"]
        departments = db.execute("SELECT COUNT(*) AS count FROM departments").fetchone()["count"]
        backups = db.execute("SELECT COUNT(*) AS count FROM backup_snapshots").fetchone()["count"]
        recent = db.execute(
            "SELECT id, action, details, created_at FROM activity_logs ORDER BY id DESC LIMIT 6"
        ).fetchall()
        by_department = db.execute(
            "SELECT department AS name, COUNT(*) AS count FROM students GROUP BY department ORDER BY count DESC"
        ).fetchall()
    return {
        "total_students": total,
        "active_students": active,
        "departments": departments,
        "available_backups": backups,
        "recent_activity": recent,
        "students_by_department": by_department,
    }


@app.get("/api/students")
def list_students(search: str = Query(default="", max_length=100)) -> list[dict[str, Any]]:
    term = f"%{search.strip()}%"
    with connect() as db:
        rows = db.execute(
            """SELECT id, matric_number, first_name, last_name, department, level, status, created_at FROM students
            WHERE matric_number ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s
            OR department ILIKE %s
            ORDER BY id DESC""",
            (term, term, term, term),
        ).fetchall()
    return rows


@app.post("/api/students", status_code=201)
def create_student(student: StudentInput) -> dict[str, Any]:
    with connect() as db:
        try:
            row = db.execute(
                """INSERT INTO students
                (matric_number, first_name, last_name, email, department, level, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, matric_number, first_name, last_name, department, level, status, created_at""",
                (
                    student.matric_number, student.first_name, student.last_name,
                    'not-collected@invalid.example', student.department, student.level, student.status,
                    datetime.now(timezone.utc),
                ),
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Matriculation number already exists.") from exc
        log_action(db, "Student created", f"{student.first_name} {student.last_name} ({student.matric_number})")
    return row


@app.put("/api/students/{student_id}")
def update_student(student_id: int, student: StudentInput) -> dict[str, Any]:
    with connect() as db:
        try:
            row = db.execute(
                """UPDATE students SET matric_number=%s, first_name=%s, last_name=%s,
                email='not-collected@invalid.example', department=%s, level=%s, status=%s WHERE id=%s RETURNING id, matric_number, first_name, last_name, department, level, status, created_at""",
                (student.matric_number, student.first_name, student.last_name,
                 student.department, student.level, student.status, student_id),
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Matriculation number already exists.") from exc
        if not row:
            raise HTTPException(status_code=404, detail="Student not found.")
        log_action(db, "Student updated", f"Student ID {student_id}")
    return row


@app.delete("/api/students/{student_id}")
def delete_student(student_id: int) -> dict[str, bool]:
    with connect() as db:
        row = db.execute("DELETE FROM students WHERE id=%s RETURNING id", (student_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Student not found.")
        log_action(db, "Student deleted", f"Student ID {student_id}")
    return {"deleted": True}


@app.get("/api/departments")
def list_departments() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT d.*, COUNT(s.id)::int AS student_count FROM departments d
            LEFT JOIN students s ON s.department=d.name GROUP BY d.id ORDER BY d.name"""
        ).fetchall()
    return rows


@app.post("/api/departments", status_code=201)
def create_department(department: DepartmentInput) -> dict[str, Any]:
    with connect() as db:
        try:
            row = db.execute(
                "INSERT INTO departments (name, code) VALUES (%s, %s) RETURNING *",
                (department.name, department.code.upper()),
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Department name or code already exists.") from exc
        log_action(db, "Department created", department.name)
    return row


@app.get("/api/results")
def list_results() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT r.*, s.matric_number, s.first_name, s.last_name
            FROM results r JOIN students s ON s.id=r.student_id ORDER BY r.id DESC"""
        ).fetchall()
    return rows


@app.post("/api/results", status_code=201)
def create_result(result: ResultInput) -> dict[str, Any]:
    with connect() as db:
        try:
            row = db.execute(
                """INSERT INTO results (student_id, course_code, course_title, score, semester)
                VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (result.student_id, result.course_code.upper(), result.course_title, result.score, result.semester),
            ).fetchone()
        except psycopg.errors.ForeignKeyViolation as exc:
            raise HTTPException(status_code=404, detail="Student not found.") from exc
        log_action(db, "Result recorded", f"{result.course_code.upper()} for student ID {result.student_id}")
        joined = db.execute(
            """SELECT r.*, s.matric_number, s.first_name, s.last_name
            FROM results r JOIN students s ON s.id=r.student_id WHERE r.id=%s""",
            (row["id"],),
        ).fetchone()
    return joined


@app.delete("/api/results/{result_id}")
def delete_result(result_id: int) -> dict[str, bool]:
    with connect() as db:
        row = db.execute("DELETE FROM results WHERE id=%s RETURNING id", (result_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Result not found.")
        log_action(db, "Result deleted", f"Result ID {result_id}")
    return {"deleted": True}


@app.post("/api/backups")
def create_backup() -> dict[str, Any]:
    with connect() as db:
        snapshot = _snapshot_tables(db)
        filename = _store_snapshot(db, snapshot)
        log_action(db, "Backup created", filename)
        size_bytes = len(json.dumps(snapshot, separators=(",", ":")).encode("utf-8"))
    return {
        "filename": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": size_bytes,
        "integrity": "ok",
    }


@app.get("/api/backups")
def list_backups() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT filename, octet_length(snapshot::text) AS size_bytes, created_at AS modified_at
            FROM backup_snapshots ORDER BY created_at DESC"""
        ).fetchall()
    return rows


@app.post("/api/backups/{filename}/restore")
def restore_backup(filename: str) -> dict[str, Any]:
    if not re.fullmatch(r"campusbook-[0-9]{8}-[0-9]{6}-[0-9]{6}\.json", filename):
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    with connect() as db:
        backup = db.execute(
            "SELECT snapshot FROM backup_snapshots WHERE filename=%s", (filename,)
        ).fetchone()
        if not backup:
            raise HTTPException(status_code=404, detail="Backup not found.")
        tables = _validate_snapshot(backup["snapshot"])

        # Preserve the current state as a safety snapshot before changing any records.
        safety_snapshot = _snapshot_tables(db)
        safety_filename = _store_snapshot(db, safety_snapshot)

        db.execute("DELETE FROM results")
        db.execute("DELETE FROM students")
        db.execute("DELETE FROM departments")
        db.execute("DELETE FROM activity_logs")

        for row in tables["departments"]:
            db.execute(
                "INSERT INTO departments (name, code) VALUES (%s, %s)",
                (row["name"], row["code"]),
            )

        student_id_map: dict[int, int] = {}
        for row in tables["students"]:
            created_at = row["created_at"]
            new_row = db.execute(
                """INSERT INTO students
                (matric_number, first_name, last_name, email, department, level, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (row["matric_number"], row["first_name"], row["last_name"], row["email"],
                 row["department"], row["level"], row["status"], created_at),
            ).fetchone()
            student_id_map[int(row["id"])] = new_row["id"]

        for row in tables["results"]:
            old_student_id = int(row["student_id"])
            if old_student_id not in student_id_map:
                raise HTTPException(status_code=422, detail="Backup contains a result for a missing student.")
            db.execute(
                """INSERT INTO results (student_id, course_code, course_title, score, semester)
                VALUES (%s, %s, %s, %s, %s)""",
                (student_id_map[old_student_id], row["course_code"], row["course_title"],
                 row["score"], row["semester"]),
            )

        for row in tables["activity_logs"]:
            db.execute(
                "INSERT INTO activity_logs (action, details, created_at) VALUES (%s, %s, %s)",
                (row["action"], row["details"], row["created_at"]),
            )
        log_action(db, "Database restored", f"{filename}; safety snapshot: {safety_filename}")

    return {
        "restored": True,
        "filename": filename,
        "safety_backup": safety_filename,
        "integrity": "ok",
    }


@app.get("/api/activity")
def activity() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM activity_logs ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return rows
