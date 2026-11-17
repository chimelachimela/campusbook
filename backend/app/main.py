from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("CAMPUSBOOK_DATA_DIR", BASE_DIR / "data"))
BACKUP_DIR = Path(os.getenv("CAMPUSBOOK_BACKUP_DIR", BASE_DIR / "backups"))
DB_PATH = Path(os.getenv("CAMPUSBOOK_DB_PATH", DATA_DIR / "campusbook.db"))

app = FastAPI(
    title="CampusBook API",
    description="Student records management with database backup and recovery.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudentInput(BaseModel):
    matric_number: str = Field(min_length=2, max_length=40)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=160)
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


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def log_action(connection: sqlite3.Connection, action: str, details: str) -> None:
    connection.execute(
        "INSERT INTO activity_logs (action, details, created_at) VALUES (?, ?, ?)",
        (action, details, datetime.now(timezone.utc).isoformat()),
    )


def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matric_number TEXT NOT NULL UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL,
                department TEXT NOT NULL,
                level TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                course_code TEXT NOT NULL,
                course_title TEXT NOT NULL,
                score REAL NOT NULL CHECK(score >= 0 AND score <= 100),
                semester TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        count = db.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO departments (name, code) VALUES (?, ?)",
                [
                    ("Computer Engineering", "CPE"),
                    ("Computer Science", "CSC"),
                    ("Electrical Engineering", "EEE"),
                    ("Accountancy", "ACC"),
                ],
            )


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "CampusBook API"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        active = db.execute("SELECT COUNT(*) FROM students WHERE status='Active'").fetchone()[0]
        departments = db.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        backups = len(list(BACKUP_DIR.glob("campusbook-*.db"))) if BACKUP_DIR.exists() else 0
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
        "recent_activity": [row_dict(r) for r in recent],
        "students_by_department": [row_dict(r) for r in by_department],
    }


@app.get("/api/students")
def list_students(search: str = Query(default="", max_length=100)) -> list[dict[str, Any]]:
    term = f"%{search.strip()}%"
    with connect() as db:
        rows = db.execute(
            """SELECT * FROM students
            WHERE matric_number LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR department LIKE ?
            ORDER BY id DESC""",
            (term, term, term, term),
        ).fetchall()
    return [row_dict(r) for r in rows]


@app.post("/api/students", status_code=201)
def create_student(student: StudentInput) -> dict[str, Any]:
    with connect() as db:
        try:
            cursor = db.execute(
                """INSERT INTO students
                (matric_number, first_name, last_name, email, department, level, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    student.matric_number, student.first_name, student.last_name,
                    student.email, student.department, student.level, student.status,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Matriculation number already exists.") from exc
        log_action(db, "Student created", f"{student.first_name} {student.last_name} ({student.matric_number})")
        row = db.execute("SELECT * FROM students WHERE id=?", (cursor.lastrowid,)).fetchone()
    return row_dict(row)


@app.put("/api/students/{student_id}")
def update_student(student_id: int, student: StudentInput) -> dict[str, Any]:
    with connect() as db:
        exists = db.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Student not found.")
        try:
            db.execute(
                """UPDATE students SET matric_number=?, first_name=?, last_name=?, email=?,
                department=?, level=?, status=? WHERE id=?""",
                (student.matric_number, student.first_name, student.last_name, student.email,
                 student.department, student.level, student.status, student_id),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Matriculation number already exists.") from exc
        log_action(db, "Student updated", f"Student ID {student_id}")
        row = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    return row_dict(row)


@app.delete("/api/students/{student_id}")
def delete_student(student_id: int) -> dict[str, bool]:
    with connect() as db:
        cursor = db.execute("DELETE FROM students WHERE id=?", (student_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Student not found.")
        log_action(db, "Student deleted", f"Student ID {student_id}")
    return {"deleted": True}


@app.get("/api/departments")
def list_departments() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT d.*, COUNT(s.id) AS student_count FROM departments d "
            "LEFT JOIN students s ON s.department=d.name GROUP BY d.id ORDER BY d.name"
        ).fetchall()
    return [row_dict(r) for r in rows]


@app.post("/api/departments", status_code=201)
def create_department(department: DepartmentInput) -> dict[str, Any]:
    with connect() as db:
        try:
            cursor = db.execute(
                "INSERT INTO departments (name, code) VALUES (?, ?)",
                (department.name, department.code.upper()),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Department name or code already exists.") from exc
        log_action(db, "Department created", department.name)
        row = db.execute("SELECT * FROM departments WHERE id=?", (cursor.lastrowid,)).fetchone()
    return row_dict(row)


@app.get("/api/results")
def list_results() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT r.*, s.matric_number, s.first_name, s.last_name
            FROM results r JOIN students s ON s.id=r.student_id ORDER BY r.id DESC"""
        ).fetchall()
    return [row_dict(r) for r in rows]


@app.post("/api/results", status_code=201)
def create_result(result: ResultInput) -> dict[str, Any]:
    with connect() as db:
        student = db.execute("SELECT id FROM students WHERE id=?", (result.student_id,)).fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found.")
        cursor = db.execute(
            """INSERT INTO results (student_id, course_code, course_title, score, semester)
            VALUES (?, ?, ?, ?, ?)""",
            (result.student_id, result.course_code.upper(), result.course_title, result.score, result.semester),
        )
        log_action(db, "Result recorded", f"{result.course_code.upper()} for student ID {result.student_id}")
        row = db.execute(
            """SELECT r.*, s.matric_number, s.first_name, s.last_name
            FROM results r JOIN students s ON s.id=r.student_id WHERE r.id=?""",
            (cursor.lastrowid,),
        ).fetchone()
    return row_dict(row)


@app.delete("/api/results/{result_id}")
def delete_result(result_id: int) -> dict[str, bool]:
    with connect() as db:
        cursor = db.execute("DELETE FROM results WHERE id=?", (result_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Result not found.")
        log_action(db, "Result deleted", f"Result ID {result_id}")
    return {"deleted": True}


@app.post("/api/backups")
def create_backup() -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = BACKUP_DIR / f"campusbook-{timestamp}.db"
    # SQLite's backup API produces a consistent snapshot, even if the DB is in use.
    source = sqlite3.connect(DB_PATH)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        target.close()
        source.close()
    if integrity != "ok":
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Backup integrity check failed.")
    with connect() as db:
        log_action(db, "Backup created", destination.name)
    return {"filename": destination.name, "created_at": timestamp, "integrity": integrity}


@app.get("/api/backups")
def list_backups() -> list[dict[str, Any]]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for path in sorted(BACKUP_DIR.glob("campusbook-*.db"), reverse=True):
        backups.append({
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        })
    return backups


@app.post("/api/backups/{filename}/restore")
def restore_backup(filename: str) -> dict[str, Any]:
    # Accept only generated backup filenames; reject traversal and arbitrary paths.
    if Path(filename).name != filename or not filename.startswith("campusbook-") or not filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    source_path = BACKUP_DIR / filename
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found.")
    check = sqlite3.connect(source_path)
    try:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        required = {r[0] for r in check.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=422, detail="Backup is not a valid SQLite database.") from exc
    finally:
        check.close()
    if integrity != "ok" or not {"students", "departments", "activity_logs"}.issubset(required):
        raise HTTPException(status_code=422, detail="Backup validation failed; database was not changed.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Preserve the current database before replacing it, so a failed restore is recoverable.
    safety_copy = BACKUP_DIR / f"pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.db"
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, safety_copy)
    temp_path = DB_PATH.with_suffix(".restore.tmp")
    shutil.copy2(source_path, temp_path)
    os.replace(temp_path, DB_PATH)
    with connect() as db:
        log_action(db, "Database restored", filename)
    return {"restored": True, "filename": filename, "integrity": integrity}


@app.get("/api/activity")
def activity() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM activity_logs ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [row_dict(r) for r in rows]
