from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

BASE_DIR = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", "")
MIGRATION_FILE = BASE_DIR / "migrations" / "001_initial_postgres.sql"
BACKUP_VERSION = 3
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
SESSION_HOURS = 12
_DEMO_DATABASE_ACTIVE: ContextVar[bool] = ContextVar('campusbook_demo_database_active', default=False)

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


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=200)

class SignupInput(BaseModel):
    email: str = Field(min_length=6,max_length=160,pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8,max_length=200)
    role: str = Field(pattern="^(Student|Lecturer)$")
    identity_number: str = Field(min_length=2,max_length=40)


class DemoLoginInput(BaseModel):
    role: str = Field(pattern="^(Student|Lecturer)$")


class BulkCourseRegistrationInput(BaseModel):
    course_offering_ids: list[int] = Field(min_length=1,max_length=100)


class BootstrapInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=200)


class AccountProvisionInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=200)
    role: str = Field(pattern="^(Administrator|Lecturer|Student|ExamsOfficer)$")
    student_id: int | None = Field(default=None, gt=0)
    lecturer_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)


class AcademicSessionInput(BaseModel):
    name: str = Field(min_length=4,max_length=20)
    starts_on: date | None = None
    ends_on: date | None = None
    is_current: bool = False
    include_summer: bool = False


class SemesterInput(BaseModel):
    academic_session_id: int = Field(gt=0)
    name: str = Field(pattern="^(First Semester|Second Semester|Summer)$")
    registration_opens_at: datetime | None = None
    registration_closes_at: datetime | None = None
    is_published: bool = False


class LecturerInput(BaseModel):
    staff_number: str = Field(min_length=2,max_length=40)
    first_name: str = Field(min_length=1,max_length=80)
    last_name: str = Field(min_length=1,max_length=80)
    department_id: int = Field(gt=0)


class CourseInput(BaseModel):
    department_id: int = Field(gt=0)
    course_code: str = Field(min_length=2,max_length=20)
    title: str = Field(min_length=2,max_length=160)
    credit_units: int = Field(default=3,ge=1,le=10)
    level: str = Field(pattern="^(100|200|300|400|500|600)$")


class OfferingInput(BaseModel):
    course_id: int = Field(gt=0)
    semester_id: int = Field(gt=0)
    section: str = Field(default="A",min_length=1,max_length=20)
    lecturer_id: int | None = Field(default=None,gt=0)
    capacity: int | None = Field(default=None,gt=0)


class GradeEntry(BaseModel):
    student_id: int = Field(gt=0)
    score: float = Field(ge=0, le=100)


class GradeRosterInput(BaseModel):
    grades: list[GradeEntry] = Field(min_length=1, max_length=500)


class FacultyInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=16)


class DepartmentInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=12)
    faculty_id: int = Field(gt=0)


class LecturerAssignmentInput(BaseModel):
    lecturer_id: int | None = Field(default=None, gt=0)


class DepartmentSubmissionInput(BaseModel):
    semester_id: int = Field(gt=0)
    level: str = Field(pattern="^(100|200|300|400|500|600)$")


class ResultInput(BaseModel):
    student_id: int = Field(gt=0)
    course_code: str = Field(min_length=2, max_length=20)
    course_title: str = Field(min_length=2, max_length=120)
    score: float = Field(ge=0, le=100)
    semester: str = Field(min_length=3, max_length=40)


@contextmanager
def connect_primary():
    """Always connect to the institution's primary database."""
    url = os.getenv("DATABASE_URL", DATABASE_URL)
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    with psycopg.connect(url, row_factory=dict_row) as db:
        yield db


@contextmanager
def connect():
    """Use the isolated demo clone for authenticated demo administrator, student and lecturer sessions."""
    primary_url = os.getenv("DATABASE_URL", DATABASE_URL)
    demo_url = os.getenv("CAMPUSBOOK_DEMO_DATABASE_URL", "")
    url = demo_url if _DEMO_DATABASE_ACTIVE.get() and demo_url else primary_url
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
    migrations = sorted(MIGRATION_FILE.parent.glob("*.sql"))
    with connect() as db:
        for migration in migrations:
            source = "\n".join(line.split("--",1)[0] for line in migration.read_text().splitlines())
            statements = [part.strip() for part in source.split(";") if part.strip()]
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


def _session_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_session(db: psycopg.Connection, user_id: int, response: Response) -> None:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO user_sessions (user_id,token_hash,created_at,expires_at) VALUES (%s,%s,%s,%s)",
        (user_id,_session_digest(token),now,now+timedelta(hours=SESSION_HOURS)),
    )
    response.set_cookie("campusbook_session",token,httponly=True,secure=not bool(os.getenv("CAMPUSBOOK_TESTING")),samesite=os.getenv("CAMPUSBOOK_COOKIE_SAMESITE","lax").lower(),max_age=SESSION_HOURS*3600,path="/")


def get_current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get("campusbook_session")
    if not token:
        auth = request.headers.get("authorization","")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401,detail="Sign in to continue.")
    with connect() as db:
        user=db.execute(
            """SELECT u.id,u.username,u.role,u.student_id,u.lecturer_id,u.department_id
            FROM user_sessions s JOIN user_accounts u ON u.id=s.user_id
            WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>%s AND u.is_active=TRUE""",
            (_session_digest(token),datetime.now(timezone.utc)),
        ).fetchone()
    if not user:
        raise HTTPException(status_code=401,detail="Your session has expired. Sign in again.")
    return user


def require_roles(user: dict[str, Any], *roles: str) -> None:
    if user["role"] not in roles:
        raise HTTPException(status_code=403,detail="You do not have permission to perform this action.")


SNAPSHOT_TABLES = (
    "faculties","departments","students","lecturers","academic_sessions","semesters",
    "courses","course_offerings","course_registrations","user_accounts","course_grades",
    "department_result_submissions","department_result_submission_grades","results","activity_logs",
)


def _json_value(value: Any) -> Any:
    if isinstance(value,(datetime,date)):
        return value.isoformat()
    return value


def _snapshot_tables(db: psycopg.Connection) -> dict[str, Any]:
    tables={}
    for table in SNAPSHOT_TABLES:
        rows=db.execute(sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(table))).fetchall()
        tables[table]=[{key:_json_value(value) for key,value in row.items()} for row in rows]
    return {"format_version":BACKUP_VERSION,"tables":tables}


def _store_snapshot(db: psycopg.Connection,snapshot:dict[str,Any])->str:
    timestamp=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    filename=f"campusbook-{timestamp}.json"
    db.execute("INSERT INTO backup_snapshots (filename,snapshot,created_at) VALUES (%s,%s,%s)",(filename,Jsonb(snapshot),datetime.now(timezone.utc)))
    return filename


def _validate_snapshot(snapshot:Any)->dict[str,list[dict[str,Any]]]:
    legacy_required={
        "departments":{"name","code"},
        "students":{"id","matric_number","first_name","last_name","email","department","department_id","level","status","created_at"},
        "results":{"student_id","course_code","course_title","score","semester"},
        "activity_logs":{"action","details","created_at"},
    }
    v2_required={
        "faculties":{"id","name","code","created_at"},
        "departments":{"id","name","code","faculty_id"},
        "students":{"id","matric_number","first_name","last_name","email","department","level","status","created_at"},
        "lecturers":{"id","staff_number","first_name","last_name","department_id","status","created_at"},
        "academic_sessions":{"id","name","starts_on","ends_on","is_current"},
        "semesters":{"id","academic_session_id","name","registration_opens_at","registration_closes_at","is_published"},
        "courses":{"id","department_id","course_code","title","credit_units","level","is_active"},
        "course_offerings":{"id","course_id","semester_id","section","lecturer_id","capacity","status","created_at"},
        "course_registrations":{"id","course_offering_id","student_id","status","registered_at","dropped_at"},
        "user_accounts":{"id","username","password_hash","role","student_id","lecturer_id","is_active","must_change_password","created_at"},
        "course_grades":{"id","registration_id","score","letter_grade","status","entered_by","submitted_at","approved_at","updated_at"},
        "results":{"id","student_id","course_code","course_title","score","semester"},
        "activity_logs":{"id","action","details","created_at"},
    }
    v3_required={**v2_required,
        "semesters":v2_required["semesters"]|{"starts_on","ends_on"},
        "user_accounts":v2_required["user_accounts"]|{"department_id"},
        "department_result_submissions":{"id","department_id","semester_id","level","status","submitted_by","reviewed_by","submitted_at","reviewed_at","review_note"},
        "department_result_submission_grades":{"id","submission_id","grade_id"},
    }
    if not isinstance(snapshot,dict) or snapshot.get("format_version") not in (1,2,3):
        raise HTTPException(status_code=422,detail="Unsupported or invalid backup format.")
    required=v3_required if snapshot["format_version"]==3 else (v2_required if snapshot["format_version"]==2 else legacy_required)
    tables=snapshot.get("tables")
    if not isinstance(tables,dict):
        raise HTTPException(status_code=422,detail="Backup tables are missing.")
    validated={}
    for table,columns in required.items():
        rows=tables.get(table)
        if not isinstance(rows,list) or any(not isinstance(row,dict) or not columns.issubset(row.keys()) for row in rows):
            raise HTTPException(status_code=422,detail=f"Backup validation failed for {table}.")
        validated[table]=rows
    return validated


def _insert_snapshot_rows(db:psycopg.Connection,table:str,rows:list[dict[str,Any]])->None:
    if not rows:
        return
    allowed=set(SNAPSHOT_TABLES)
    if table not in allowed:
        raise HTTPException(status_code=422,detail="Backup contains an unsupported table.")
    for row in rows:
        columns=list(row.keys())
        query=sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table),
            sql.SQL(",").join(sql.Identifier(column) for column in columns),
            sql.SQL(",").join(sql.Placeholder() for _ in columns),
        )
        db.execute(query,tuple(row[column] for column in columns))


def _reset_snapshot_sequences(db:psycopg.Connection)->None:
    for table in SNAPSHOT_TABLES:
        db.execute(
            sql.SQL("SELECT setval(pg_get_serial_sequence({},'id'),COALESCE((SELECT MAX(id) FROM {}),1),true)").format(
                sql.Literal(table),sql.Identifier(table)
            )
        )


@app.get("/api/health")
def health() -> dict[str, str]:
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok", "service": "CampusBook API", "database": "connected"}


@app.get("/api/dashboard")
def dashboard(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_roles(user, 'Administrator')
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
def list_students(search: str = Query(default="", max_length=100), user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_roles(user, 'Administrator')
    term = f"%{search.strip()}%"
    with connect() as db:
        rows = db.execute(
            """SELECT s.id,s.matric_number,s.first_name,s.last_name,s.department,s.department_id,
            d.faculty_id,f.name AS faculty,s.level,s.status,s.created_at
            FROM students s JOIN departments d ON d.id=s.department_id
            JOIN faculties f ON f.id=d.faculty_id
            WHERE s.matric_number ILIKE %s OR s.first_name ILIKE %s OR s.last_name ILIKE %s
            OR s.department ILIKE %s OR f.name ILIKE %s
            ORDER BY s.id DESC""",
            (term, term, term, term, term),
        ).fetchall()
    return rows


@app.post("/api/students", status_code=201)
def create_student(student: StudentInput, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_roles(user, 'Administrator')
    if not re.fullmatch(r"DE/[0-9]{4}/[0-9]{4}",student.matric_number.strip().upper()):
        raise HTTPException(status_code=422,detail="Matriculation number must follow DE/YYYY/NNNN, for example DE/2023/0001.")
    with connect() as db:
        department = db.execute("SELECT id FROM departments WHERE name=%s",(student.department,)).fetchone()
        if not department:
            raise HTTPException(status_code=404,detail="Department not found.")
        try:
            row = db.execute(
                """INSERT INTO students
                (matric_number,first_name,last_name,email,department,department_id,level,status,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id,matric_number,first_name,last_name,department,department_id,level,status,created_at""",
                (student.matric_number,student.first_name,student.last_name,'not-collected@invalid.example',
                 student.department,department["id"],student.level,student.status,datetime.now(timezone.utc)),
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Matriculation number already exists.") from exc
        log_action(db, "Student created", f"{student.first_name} {student.last_name} ({student.matric_number})")
    return row


@app.put("/api/students/{student_id}")
def update_student(student_id: int, student: StudentInput, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_roles(user, 'Administrator')
    with connect() as db:
        existing_student=db.execute("SELECT matric_number FROM students WHERE id=%s",(student_id,)).fetchone()
        if not existing_student:
            raise HTTPException(status_code=404,detail="Student not found.")
        if student.matric_number.strip().upper()!=existing_student["matric_number"] and not re.fullmatch(r"DE/[0-9]{4}/[0-9]{4}",student.matric_number.strip().upper()):
            raise HTTPException(status_code=422,detail="Matriculation number must follow DE/YYYY/NNNN, for example DE/2023/0001.")
        department = db.execute("SELECT id FROM departments WHERE name=%s",(student.department,)).fetchone()
        if not department:
            raise HTTPException(status_code=404,detail="Department not found.")
        try:
            row = db.execute(
                """UPDATE students SET matric_number=%s,first_name=%s,last_name=%s,
                email='not-collected@invalid.example',department=%s,department_id=%s,level=%s,status=%s
                WHERE id=%s RETURNING id,matric_number,first_name,last_name,department,department_id,level,status,created_at""",
                (student.matric_number,student.first_name,student.last_name,student.department,
                 department["id"],student.level,student.status,student_id),
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Matriculation number already exists.") from exc
        if not row:
            raise HTTPException(status_code=404, detail="Student not found.")
        log_action(db, "Student updated", f"Student ID {student_id}")
    return row


@app.delete("/api/students/{student_id}")
def delete_student(student_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, bool]:
    require_roles(user, 'Administrator')
    with connect() as db:
        row = db.execute("DELETE FROM students WHERE id=%s RETURNING id", (student_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Student not found.")
        log_action(db, "Student deleted", f"Student ID {student_id}")
    return {"deleted": True}


@app.get("/api/departments")
def list_departments(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_roles(user, 'Administrator', 'Lecturer', 'Student')
    with connect() as db:
        rows = db.execute(
            """SELECT d.*,f.name AS faculty_name,COUNT(s.id)::int AS student_count
            FROM departments d JOIN faculties f ON f.id=d.faculty_id
            LEFT JOIN students s ON s.department_id=d.id
            GROUP BY d.id,f.name ORDER BY f.name,d.name"""
        ).fetchall()
    return rows


@app.post("/api/departments", status_code=201)
def create_department(department: DepartmentInput, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_roles(user, 'Administrator')
    with connect() as db:
        try:
            row = db.execute(
                "INSERT INTO departments (name, code, faculty_id) VALUES (%s, %s, %s) RETURNING *",
                (department.name, department.code.upper(), department.faculty_id),
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Department name or code already exists.") from exc
        log_action(db, "Department created", department.name)
    return row


@app.get("/api/results")
def list_results(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_roles(user, 'Administrator')
    with connect() as db:
        rows = db.execute(
            """SELECT r.*, s.matric_number, s.first_name, s.last_name
            FROM results r JOIN students s ON s.id=r.student_id ORDER BY r.id DESC"""
        ).fetchall()
    return rows


@app.post("/api/results", status_code=201)
def create_result(result: ResultInput, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_roles(user, 'Administrator')
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
def delete_result(result_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, bool]:
    require_roles(user, 'Administrator')
    with connect() as db:
        row = db.execute("DELETE FROM results WHERE id=%s RETURNING id", (result_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Result not found.")
        log_action(db, "Result deleted", f"Result ID {result_id}")
    return {"deleted": True}


@app.post("/api/backups")
def create_backup(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_roles(user, 'Administrator')
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
def list_backups(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_roles(user, 'Administrator')
    with connect() as db:
        rows = db.execute(
            """SELECT filename, octet_length(snapshot::text) AS size_bytes, created_at AS modified_at
            FROM backup_snapshots ORDER BY created_at DESC"""
        ).fetchall()
    return rows


@app.post("/api/backups/{filename}/restore")
def restore_backup(filename:str,user:dict[str,Any]=Depends(get_current_user))->dict[str,Any]:
    require_roles(user,"Administrator")
    if not re.fullmatch(r"campusbook-[0-9]{8}-[0-9]{6}-[0-9]{6}\.json",filename):
        raise HTTPException(status_code=400,detail="Invalid backup filename.")
    with connect() as db:
        backup=db.execute("SELECT snapshot FROM backup_snapshots WHERE filename=%s",(filename,)).fetchone()
        if not backup: raise HTTPException(status_code=404,detail="Backup not found.")
        snapshot=backup["snapshot"]
        tables=_validate_snapshot(snapshot)
        safety=_store_snapshot(db,_snapshot_tables(db))
        if snapshot["format_version"]==1:
            new_rows=db.execute(
                """SELECT
                (SELECT COUNT(*) FROM course_registrations) +
                (SELECT COUNT(*) FROM user_accounts) +
                (SELECT COUNT(*) FROM course_offerings) +
                (SELECT COUNT(*) FROM courses) +
                (SELECT COUNT(*) FROM lecturers) +
                (SELECT COUNT(*) FROM academic_sessions) +
                (SELECT COUNT(*) FROM faculties) AS count"""
            ).fetchone()["count"]
            if new_rows:
                raise HTTPException(status_code=409,detail="This is a legacy backup. Restore it only before V1 academic accounts and registrations exist.")
            db.execute("DELETE FROM results")
            db.execute("DELETE FROM students")
            db.execute("DELETE FROM departments")
            db.execute("DELETE FROM activity_logs")
            for row in tables["departments"]:
                db.execute("INSERT INTO departments (name,code) VALUES (%s,%s)",(row["name"],row["code"]))
            student_map={}
            for row in tables["students"]:
                dept=db.execute("SELECT id FROM departments WHERE name=%s",(row["department"],)).fetchone()
                if not dept: raise HTTPException(status_code=422,detail="Legacy backup refers to a missing department.")
                inserted=db.execute(
                    """INSERT INTO students (matric_number,first_name,last_name,email,department,department_id,level,status,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (row["matric_number"],row["first_name"],row["last_name"],row["email"],row["department"],dept["id"],row["level"],row["status"],row["created_at"])
                ).fetchone()
                student_map[int(row["id"])]=inserted["id"]
            for row in tables["results"]:
                if int(row["student_id"]) not in student_map:
                    raise HTTPException(status_code=422,detail="Backup contains a result for a missing student.")
                db.execute("INSERT INTO results (student_id,course_code,course_title,score,semester) VALUES (%s,%s,%s,%s,%s)",
                    (student_map[int(row["student_id"])],row["course_code"],row["course_title"],row["score"],row["semester"]))
            for row in tables["activity_logs"]:
                db.execute("INSERT INTO activity_logs (action,details,created_at) VALUES (%s,%s,%s)",(row["action"],row["details"],row["created_at"]))
        else:
            for table in ("department_result_submission_grades","department_result_submissions","course_grades","course_registrations","course_offerings","courses","semesters","academic_sessions","user_sessions","user_accounts","lecturers","results","students","departments","faculties","activity_logs"):
                db.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
            restore_order=("faculties","departments","students","lecturers","academic_sessions","semesters","courses","course_offerings","course_registrations","user_accounts","course_grades")
            if snapshot["format_version"]==3:
                restore_order+=("department_result_submissions","department_result_submission_grades")
            restore_order+=("results","activity_logs")
            for table in restore_order:
                _insert_snapshot_rows(db,table,tables[table])
            _reset_snapshot_sequences(db)
            db.execute("UPDATE user_sessions SET revoked_at=NOW() WHERE revoked_at IS NULL")
        log_action(db,"Database restored",f"{filename}; safety snapshot: {safety}")
    return {"restored":True,"filename":filename,"safety_backup":safety,"integrity":"ok"}

@app.get("/api/activity")
def activity(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_roles(user, 'Administrator')
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM activity_logs ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return rows


@app.post("/api/auth/bootstrap",status_code=201)
def bootstrap_admin(payload:BootstrapInput,response:Response,x_bootstrap_secret:str|None=Header(default=None,alias="X-CampusBook-Bootstrap-Secret")):
    expected=os.getenv("CAMPUSBOOK_BOOTSTRAP_SECRET","")
    if not expected or not x_bootstrap_secret or not secrets.compare_digest(expected,x_bootstrap_secret):
        raise HTTPException(status_code=404,detail="Bootstrap is unavailable.")
    with connect() as db:
        count=db.execute("SELECT COUNT(*) AS count FROM user_accounts WHERE role='Administrator'").fetchone()["count"]
        if count: raise HTTPException(status_code=409,detail="The initial administrator has already been created.")
        user=db.execute("INSERT INTO user_accounts (username,password_hash,role) VALUES (%s,%s,'Administrator') RETURNING id,username,role",(payload.username.strip(),PASSWORD_HASHER.hash(payload.password))).fetchone()
        _issue_session(db,user["id"],response)
    return user


@app.post("/api/auth/login")
def login(payload:LoginInput,response:Response):
    with connect() as db:
        user=db.execute("SELECT id,username,password_hash,role,student_id,lecturer_id,is_active FROM user_accounts WHERE username=%s",(payload.username.strip(),)).fetchone()
        if not user or not user["is_active"]: raise HTTPException(status_code=401,detail="Username or password is incorrect.")
        try: PASSWORD_HASHER.verify(user["password_hash"],payload.password)
        except (VerifyMismatchError,VerificationError,InvalidHashError): raise HTTPException(status_code=401,detail="Username or password is incorrect.")
        _issue_session(db,user["id"],response)
    return {k:user[k] for k in ("id","username","role","student_id","lecturer_id")}


@app.post("/api/auth/signup",status_code=201)
def signup(payload:SignupInput,response:Response):
    email=payload.email.strip().lower()
    identity=payload.identity_number.strip()
    with connect() as db:
        if payload.role=="Student":
            record=db.execute("SELECT id FROM students WHERE regexp_replace(UPPER(matric_number),'[^A-Z0-9]','','g')=regexp_replace(UPPER(%s),'[^A-Z0-9]','','g') AND status='Active'",(identity,)).fetchone()
            if not record: raise HTTPException(status_code=404,detail="No active student record matches that matriculation number. Ask the administrator to create your student record first.")
            student_id=record["id"]; lecturer_id=None
        else:
            record=db.execute("SELECT id FROM lecturers WHERE regexp_replace(UPPER(staff_number),'[^A-Z0-9]','','g')=regexp_replace(UPPER(%s),'[^A-Z0-9]','','g') AND status='Active'",(identity,)).fetchone()
            if not record: raise HTTPException(status_code=404,detail="No active lecturer record matches that staff number. Ask the administrator to create your lecturer profile and assign your department first.")
            lecturer_id=record["id"]; student_id=None
        try:
            account=db.execute(
                "INSERT INTO user_accounts (username,password_hash,role,student_id,lecturer_id) VALUES (%s,%s,%s,%s,%s) RETURNING id,username,role,student_id,lecturer_id",
                (email,PASSWORD_HASHER.hash(payload.password),payload.role,student_id,lecturer_id)
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="An account already exists for this email or academic record. Sign in instead.") from exc
        _issue_session(db,account["id"],response)
        log_action(db,"Self-service account created",f"{payload.role} account {email}")
    return account


def _issue_demo_session(username:str,role:str,response:Response):
    demo_url=os.getenv("CAMPUSBOOK_DEMO_DATABASE_URL","")
    if os.getenv("CAMPUSBOOK_DEMO_ADMIN_ENABLED","").lower()!="true" or not demo_url:
        raise HTTPException(status_code=404,detail="Demo access is not configured.")
    token=secrets.token_urlsafe(48);now=datetime.now(timezone.utc);token_hash=_session_digest(token)
    with connect_primary() as primary:
        user=primary.execute("SELECT id,username,role,student_id,lecturer_id,department_id FROM user_accounts WHERE username=%s AND role=%s AND is_active=TRUE",(username,role)).fetchone()
        if not user:raise HTTPException(status_code=503,detail="The requested demo account is not configured.")
        primary.execute("INSERT INTO user_sessions (user_id,token_hash,created_at,expires_at) VALUES (%s,%s,%s,%s)",(user["id"],token_hash,now,now+timedelta(hours=SESSION_HOURS)))
    if demo_url != os.getenv("DATABASE_URL",DATABASE_URL):
        with psycopg.connect(demo_url,row_factory=dict_row) as demo:
            demo_user=demo.execute("SELECT id FROM user_accounts WHERE username=%s AND role=%s AND is_active=TRUE",(username,role)).fetchone()
            if not demo_user:raise HTTPException(status_code=503,detail="The matching account is missing from the isolated demo copy.")
            demo.execute("INSERT INTO user_sessions (user_id,token_hash,created_at,expires_at) VALUES (%s,%s,%s,%s)",(demo_user["id"],token_hash,now,now+timedelta(hours=SESSION_HOURS)))
    response.set_cookie("campusbook_session",token,httponly=True,secure=not bool(os.getenv("CAMPUSBOOK_TESTING")),samesite=os.getenv("CAMPUSBOOK_COOKIE_SAMESITE","lax").lower(),max_age=SESSION_HOURS*3600,path="/")
    return {k:user[k] for k in ("id","username","role","student_id","lecturer_id")}


@app.post("/api/auth/demo-admin")
def demo_admin_login(response:Response):
    return _issue_demo_session("demo.admin","Administrator",response)


@app.post("/api/auth/demo-login")
def demo_role_login(payload:DemoLoginInput,response:Response):
    username="demo.student" if payload.role=="Student" else "demo.lecturer"
    return _issue_demo_session(username,payload.role,response)


@app.middleware("http")
async def isolate_demo_accounts(request:Request,call_next):
    token=request.cookies.get("campusbook_session")
    is_demo=False
    if token and request.url.path!="/api/auth/demo-admin":
        try:
            with connect_primary() as primary:
                is_demo=bool(primary.execute(
                    """SELECT 1 FROM user_sessions s JOIN user_accounts u ON u.id=s.user_id
                    WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>%s
                    AND u.username IN ('demo.admin','demo.student','demo.lecturer') AND u.is_active=TRUE""",
                    (_session_digest(token),datetime.now(timezone.utc))
                ).fetchone())
        except Exception:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=503,content={"detail":"Could not verify the demo session. Please retry."})
    if not is_demo:
        return await call_next(request)
    if not os.getenv("CAMPUSBOOK_DEMO_DATABASE_URL"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503,content={"detail":"The isolated demo workspace is not configured."})
    marker=_DEMO_DATABASE_ACTIVE.set(True)
    try:
        response=await call_next(request)
        # Demo users operate only on CAMPUSBOOK_DEMO_DATABASE_URL. Their writes are
        # deliberately not copied to the institution database or an approval queue.
        return response
    finally:
        _DEMO_DATABASE_ACTIVE.reset(marker)



@app.get("/api/admin/demo-change-requests")
def list_demo_change_requests(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    if user.get("username")=="demo.admin": raise HTTPException(status_code=403,detail="The demo workspace cannot review its own change requests.")
    with connect_primary() as db:
        return db.execute("SELECT id,method,path,payload,status,created_at,reviewed_at,review_note FROM demo_change_requests WHERE status IN ('Pending','Approved','Rejected') ORDER BY created_at ASC LIMIT 200").fetchall()


class DemoChangeReviewInput(BaseModel):
    decision:str=Field(pattern="^(Approved|Rejected)$")
    note:str=Field(default="",max_length=500)


@app.post("/api/admin/demo-change-requests/{request_id}/review")
def review_demo_change_request(request_id:int,payload:DemoChangeReviewInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    if user.get("username")=="demo.admin": raise HTTPException(status_code=403,detail="The demo workspace cannot review its own change requests.")
    with connect_primary() as db:
        change=db.execute("SELECT id,method,path,payload FROM demo_change_requests WHERE id=%s AND status='Pending'",(request_id,)).fetchone()
    if not change: raise HTTPException(status_code=404,detail="Pending demo change request not found.")
    if payload.decision=="Approved":
        body=change["payload"] or {}
        method,path=change["method"],change["path"]
        try:
            if method=="POST" and path=="/api/faculties": create_faculty(FacultyInput(**body),user)
            elif method=="POST" and path=="/api/departments": create_department(DepartmentInput(**body),user)
            elif method=="POST" and path=="/api/students": create_student(StudentInput(**body),user)
            elif method=="PUT" and re.fullmatch(r"/api/students/\d+",path):
                demo_id=int(path.rsplit("/",1)[1])
                with connect_primary() as db:
                    target=db.execute("SELECT id FROM students WHERE id=%s",(demo_id,)).fetchone()
                    if not target: target=db.execute("SELECT id FROM students WHERE matric_number=%s",(body.get("matric_number"),)).fetchone()
                if target: update_student(target["id"],StudentInput(**body),user)
                else: create_student(StudentInput(**body),user)
            elif method=="DELETE" and re.fullmatch(r"/api/students/\d+",path):
                record=body.get("_deleted_student") or {}
                if not record.get("matric_number"): raise HTTPException(status_code=422,detail="Deleted student details were not captured; this change cannot be applied.")
                with connect_primary() as db:
                    deleted=db.execute("DELETE FROM students WHERE matric_number=%s RETURNING id",(record["matric_number"],)).fetchone()
                    if not deleted: raise HTTPException(status_code=404,detail="The student to delete no longer exists in the institution database.")
                    log_action(db,"Student deleted by approved demo request",record["matric_number"])
            elif method=="POST" and path=="/api/admin/lecturers": create_lecturer(LecturerInput(**body),user)
            elif method=="POST" and path=="/api/admin/courses": create_course(CourseInput(**body),user)
            elif method=="POST" and path=="/api/admin/course-offerings": create_course_offering(OfferingInput(**body),user)
            elif method=="POST" and path=="/api/admin/academic-sessions": create_academic_session(AcademicSessionInput(**body),user)
            elif method=="PATCH" and re.fullmatch(r"/api/admin/course-offerings/\d+/lecturer",path):
                assign_offering_lecturer(int(path.split("/")[4]),LecturerAssignmentInput(**body),user)
            else: raise HTTPException(status_code=422,detail="This demo change type is not eligible for automatic application. Reject it or make the change directly in the institution workspace.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=409,detail=f"The change could not be applied safely: {type(exc).__name__}. The request remains pending.") from exc
    with connect_primary() as db:
        row=db.execute("UPDATE demo_change_requests SET status=%s,reviewed_at=%s,reviewed_by=%s,review_note=%s WHERE id=%s AND status='Pending' RETURNING id,status,reviewed_at,review_note",(payload.decision,datetime.now(timezone.utc),user["id"],payload.note.strip(),request_id)).fetchone()
        if not row: raise HTTPException(status_code=409,detail="This request was already reviewed.")
        log_action(db,"Demo change "+payload.decision.lower(),f"Request #{request_id}: {payload.note.strip()}")
    return row

@app.post("/api/auth/logout")
def logout(request:Request,response:Response):
    token=request.cookies.get("campusbook_session")
    if token:
        with connect() as db: db.execute("UPDATE user_sessions SET revoked_at=%s WHERE token_hash=%s AND revoked_at IS NULL",(datetime.now(timezone.utc),_session_digest(token)))
        if _DEMO_DATABASE_ACTIVE.get():
            with connect_primary() as primary: primary.execute("UPDATE user_sessions SET revoked_at=%s WHERE token_hash=%s AND revoked_at IS NULL",(datetime.now(timezone.utc),_session_digest(token)))
    response.delete_cookie("campusbook_session",path="/",secure=not bool(os.getenv("CAMPUSBOOK_TESTING")),httponly=True,samesite=os.getenv("CAMPUSBOOK_COOKIE_SAMESITE","lax").lower())
    return {"logged_out":True}


@app.get("/api/auth/me")
def auth_me(user:dict[str,Any]=Depends(get_current_user)): return user


@app.post("/api/admin/accounts",status_code=201)
def provision_account(payload:AccountProvisionInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    if payload.role=="Student" and (payload.student_id is None or payload.lecturer_id is not None or payload.department_id is not None): raise HTTPException(status_code=422,detail="A student account must link only to one student record.")
    if payload.role=="Lecturer" and (payload.lecturer_id is None or payload.student_id is not None or payload.department_id is not None): raise HTTPException(status_code=422,detail="A lecturer account must link only to one lecturer record.")
    if payload.role=="ExamsOfficer" and (payload.department_id is None or payload.student_id is not None or payload.lecturer_id is not None): raise HTTPException(status_code=422,detail="An examination officer account must be assigned to one department.")
    if payload.role=="Administrator" and (payload.student_id is not None or payload.lecturer_id is not None or payload.department_id is not None): raise HTTPException(status_code=422,detail="Administrator accounts cannot link to academic records.")
    with connect() as db:
        try:
            row=db.execute("INSERT INTO user_accounts (username,password_hash,role,student_id,lecturer_id,department_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,username,role,student_id,lecturer_id,department_id,is_active",(payload.username.strip(),PASSWORD_HASHER.hash(payload.password),payload.role,payload.student_id,payload.lecturer_id,payload.department_id)).fetchone()
        except psycopg.errors.UniqueViolation as exc: raise HTTPException(status_code=409,detail="Username or linked account already exists.") from exc
        log_action(db,"Account provisioned",f"{payload.role} account {payload.username.strip()}")
    return row


@app.post("/api/faculties",status_code=201)
def create_faculty(payload:FacultyInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        try:
            row=db.execute("INSERT INTO faculties (name,code) VALUES (%s,%s) RETURNING id,name,code",(payload.name.strip(),payload.code.strip().upper())).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="Faculty name or code already exists.") from exc
        log_action(db,"Faculty created",payload.name.strip())
    return row


@app.get("/api/faculties")
def list_faculties(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator","Lecturer","Student")
    with connect() as db:
        return db.execute("SELECT f.id,f.name,f.code,COUNT(DISTINCT d.id)::int AS department_count FROM faculties f LEFT JOIN departments d ON d.faculty_id=f.id GROUP BY f.id ORDER BY f.name").fetchall()


@app.get("/api/course-offerings")
def browse_course_offerings(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator","Lecturer","Student")
    with connect() as db:
        if user["role"]=="Student":
            return db.execute(
                """SELECT o.id,o.section,o.status,c.course_code,c.title AS course_title,c.credit_units,c.level,
                d.name AS department,s.name AS semester,a.name AS academic_session,
                l.first_name AS lecturer_first_name,l.last_name AS lecturer_last_name
                FROM course_offerings o JOIN courses c ON c.id=o.course_id JOIN departments d ON d.id=c.department_id
                JOIN semesters s ON s.id=o.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
                LEFT JOIN lecturers l ON l.id=o.lecturer_id
                JOIN students st ON st.id=%s AND st.department=d.name AND st.level=c.level
                WHERE o.status='Open' AND st.status='Active'
                AND (s.registration_opens_at IS NULL OR s.registration_opens_at<=NOW())
                AND (s.registration_closes_at IS NULL OR s.registration_closes_at>=NOW())
                ORDER BY a.name DESC,s.name,c.course_code""",(user["student_id"],)).fetchall()
        if user["role"]=="Lecturer":
            return db.execute(
                """SELECT o.id,o.section,o.status,c.course_code,c.title AS course_title,c.credit_units,c.level,d.name AS department,
                s.name AS semester,a.name AS academic_session FROM course_offerings o
                JOIN courses c ON c.id=o.course_id JOIN departments d ON d.id=c.department_id
                JOIN semesters s ON s.id=o.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
                WHERE o.lecturer_id=%s ORDER BY a.name DESC,s.name,c.course_code""",(user["lecturer_id"],)).fetchall()
        return db.execute(
            """SELECT o.id,o.section,o.status,c.course_code,c.title AS course_title,c.credit_units,c.level,d.name AS department,
            s.name AS semester,a.name AS academic_session,o.lecturer_id FROM course_offerings o
            JOIN courses c ON c.id=o.course_id JOIN departments d ON d.id=c.department_id
            JOIN semesters s ON s.id=o.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
            ORDER BY a.name DESC,s.name,c.course_code""").fetchall()


@app.post("/api/student/course-offerings/register",status_code=200)
def register_selected_courses(payload:BulkCourseRegistrationInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Student")
    ids=list(dict.fromkeys(payload.course_offering_ids))
    if len(ids)!=len(payload.course_offering_ids):
        raise HTTPException(status_code=422,detail="The selected course list contains duplicates.")
    registered=0
    already_registered=0
    with connect() as db:
        for offering_id in ids:
            offering=db.execute(
                """SELECT o.id,o.capacity,o.status,c.level,d.name AS department,
                st.department AS student_department,st.level AS student_level,st.status AS student_status,
                s.registration_opens_at,s.registration_closes_at
                FROM course_offerings o JOIN courses c ON c.id=o.course_id
                JOIN departments d ON d.id=c.department_id JOIN semesters s ON s.id=o.semester_id
                JOIN students st ON st.id=%s WHERE o.id=%s FOR UPDATE OF o""",
                (user["student_id"],offering_id)
            ).fetchone()
            if not offering: raise HTTPException(status_code=404,detail=f"Course offering {offering_id} was not found.")
            now=datetime.now(timezone.utc)
            if offering["status"]!="Open" or offering["student_status"]!="Active":
                raise HTTPException(status_code=409,detail="One or more selected courses are not open for registration.")
            if offering["department"]!=offering["student_department"] or offering["level"]!=offering["student_level"]:
                raise HTTPException(status_code=403,detail="One or more selected courses are not available for your department or level.")
            if offering["registration_opens_at"] and offering["registration_opens_at"]>now:
                raise HTTPException(status_code=409,detail="Registration has not opened for one or more selected courses.")
            if offering["registration_closes_at"] and offering["registration_closes_at"]<now:
                raise HTTPException(status_code=409,detail="Registration has closed for one or more selected courses.")
            existing=db.execute("SELECT id,status FROM course_registrations WHERE course_offering_id=%s AND student_id=%s",(offering_id,user["student_id"])).fetchone()
            if existing and existing["status"]=="Registered":
                already_registered+=1
                continue
            count=db.execute("SELECT COUNT(*) AS count FROM course_registrations WHERE course_offering_id=%s AND status='Registered'",(offering_id,)).fetchone()["count"]
            if offering["capacity"] is not None and count>=offering["capacity"]:
                raise HTTPException(status_code=409,detail="One or more selected courses have reached capacity.")
            if existing:
                db.execute("UPDATE course_registrations SET status='Registered',registered_at=NOW(),dropped_at=NULL WHERE id=%s",(existing["id"],))
            else:
                db.execute("INSERT INTO course_registrations (course_offering_id,student_id,status) VALUES (%s,%s,'Registered')",(offering_id,user["student_id"]))
            registered+=1
        log_action(db,"Bulk course registration",f"Student ID {user['student_id']} registered for {registered} courses")
    return {"registered":registered,"already_registered":already_registered}


@app.post("/api/student/course-offerings/{offering_id}/register",status_code=201)
def register_for_course(offering_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Student")
    with connect() as db:
        offering=db.execute(
            """SELECT o.id,o.capacity,o.status,c.level,d.name AS department,
            st.department AS student_department,st.level AS student_level,st.status AS student_status,
            s.registration_opens_at,s.registration_closes_at FROM course_offerings o
            JOIN courses c ON c.id=o.course_id JOIN departments d ON d.id=c.department_id
            JOIN semesters s ON s.id=o.semester_id JOIN students st ON st.id=%s WHERE o.id=%s""",
            (user["student_id"],offering_id)).fetchone()
        if not offering: raise HTTPException(status_code=404,detail="Course offering not found.")
        now=datetime.now(timezone.utc)
        if offering["status"]!="Open" or offering["student_status"]!="Active": raise HTTPException(status_code=409,detail="This course is not open for registration.")
        if offering["department"]!=offering["student_department"] or offering["level"]!=offering["student_level"]: raise HTTPException(status_code=403,detail="This course is not available for your department or level.")
        if offering["registration_opens_at"] and offering["registration_opens_at"]>now: raise HTTPException(status_code=409,detail="Registration has not opened.")
        if offering["registration_closes_at"] and offering["registration_closes_at"]<now: raise HTTPException(status_code=409,detail="Registration has closed.")
        count=db.execute("SELECT COUNT(*) AS count FROM course_registrations WHERE course_offering_id=%s AND status='Registered'",(offering_id,)).fetchone()["count"]
        if offering["capacity"] is not None and count>=offering["capacity"]: raise HTTPException(status_code=409,detail="This course offering is full.")
        try: row=db.execute("INSERT INTO course_registrations (course_offering_id,student_id,status) VALUES (%s,%s,'Registered') RETURNING id,course_offering_id,student_id,status,registered_at",(offering_id,user["student_id"])).fetchone()
        except psycopg.errors.UniqueViolation as exc: raise HTTPException(status_code=409,detail="You are already registered for this course.") from exc
        log_action(db,"Course registered",f"Student ID {user['student_id']} registered for offering {offering_id}")
    return row


@app.delete("/api/student/course-offerings/{offering_id}/register")
def drop_course(offering_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Student")
    with connect() as db:
        row=db.execute(
            """UPDATE course_registrations cr SET status='Dropped',dropped_at=NOW()
            FROM course_offerings o JOIN semesters s ON s.id=o.semester_id
            WHERE cr.course_offering_id=o.id AND cr.student_id=%s AND o.id=%s AND cr.status='Registered'
            AND (s.registration_closes_at IS NULL OR s.registration_closes_at>=NOW()) RETURNING cr.id""",
            (user["student_id"],offering_id)).fetchone()
        if not row: raise HTTPException(status_code=409,detail="This registration cannot be dropped now.")
        log_action(db,"Course dropped",f"Student ID {user['student_id']} dropped offering {offering_id}")
    return {"dropped":True}


@app.get("/api/student/registrations")
def student_registrations(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Student")
    with connect() as db:
        return db.execute(
            """SELECT cr.id,cr.course_offering_id,cr.status,cr.registered_at,c.course_code,c.title AS course_title,c.credit_units,
            s.name AS semester,a.name AS academic_session,o.section FROM course_registrations cr
            JOIN course_offerings o ON o.id=cr.course_offering_id JOIN courses c ON c.id=o.course_id
            JOIN semesters s ON s.id=o.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
            WHERE cr.student_id=%s ORDER BY a.name DESC,s.name,c.course_code""",(user["student_id"],)).fetchall()


@app.get("/api/lecturer/offerings/{offering_id}/roster")
def lecturer_roster(offering_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Lecturer")
    with connect() as db:
        assigned=db.execute("SELECT id FROM course_offerings WHERE id=%s AND lecturer_id=%s",(offering_id,user["lecturer_id"])).fetchone()
        if not assigned: raise HTTPException(status_code=404,detail="Assigned course offering not found.")
        return db.execute(
            """SELECT st.id AS student_id,st.matric_number,st.first_name,st.last_name,cr.id AS registration_id,
            cr.status AS registration_status,g.score,g.status AS grade_status FROM course_registrations cr
            JOIN students st ON st.id=cr.student_id LEFT JOIN course_grades g ON g.registration_id=cr.id
            WHERE cr.course_offering_id=%s AND cr.status='Registered' ORDER BY st.matric_number""",(offering_id,)).fetchall()


@app.put("/api/lecturer/offerings/{offering_id}/grades")
def save_grade_roster(offering_id:int,payload:GradeRosterInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    ids=[g.student_id for g in payload.grades]
    if len(ids)!=len(set(ids)): raise HTTPException(status_code=422,detail="Uploaded roster contains duplicate students.")
    with connect() as db:
        assigned=db.execute("SELECT id FROM course_offerings WHERE id=%s AND lecturer_id=%s",(offering_id,user["lecturer_id"])).fetchone()
        if not assigned: raise HTTPException(status_code=404,detail="Assigned course offering not found.")
        rows=db.execute("SELECT id,student_id FROM course_registrations WHERE course_offering_id=%s AND status='Registered' AND student_id=ANY(%s)",(offering_id,ids)).fetchall()
        mapping={r["student_id"]:r["id"] for r in rows}
        if len(mapping)!=len(ids): raise HTTPException(status_code=422,detail="One or more students are not on this course roster.")
        for grade in payload.grades:
            rid=mapping[grade.student_id]
            existing=db.execute("SELECT status FROM course_grades WHERE registration_id=%s",(rid,)).fetchone()
            if existing and existing["status"] in ("Submitted","Approved","Published"): raise HTTPException(status_code=409,detail="Submitted or approved grades cannot be edited.")
            db.execute(
                """INSERT INTO course_grades (registration_id,score,status,entered_by,updated_at) VALUES (%s,%s,'Draft',%s,NOW())
                ON CONFLICT (registration_id) DO UPDATE SET score=EXCLUDED.score,status='Draft',entered_by=EXCLUDED.entered_by,updated_at=NOW()""",
                (rid,grade.score,user["id"]))
        log_action(db,"Grade roster saved",f"Lecturer ID {user['lecturer_id']} saved {len(ids)} grades for offering {offering_id}")
    return {"saved":len(ids),"status":"Draft"}


@app.post("/api/lecturer/offerings/{offering_id}/submit")
def submit_grade_roster(offering_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        assigned=db.execute("SELECT id FROM course_offerings WHERE id=%s AND lecturer_id=%s",(offering_id,user["lecturer_id"])).fetchone()
        if not assigned: raise HTTPException(status_code=404,detail="Assigned course offering not found.")
        counts=db.execute(
            """SELECT COUNT(*) FILTER (WHERE cr.status='Registered') AS roster_count,
            COUNT(g.id) FILTER (WHERE cr.status='Registered' AND g.status='Draft') AS draft_count
            FROM course_registrations cr LEFT JOIN course_grades g ON g.registration_id=cr.id WHERE cr.course_offering_id=%s""",
            (offering_id,)).fetchone()
        if counts["roster_count"]==0 or counts["roster_count"]!=counts["draft_count"]: raise HTTPException(status_code=409,detail="Every registered student needs a draft grade before submission.")
        db.execute("UPDATE course_grades g SET status='Submitted',submitted_at=NOW(),updated_at=NOW() FROM course_registrations cr WHERE cr.id=g.registration_id AND cr.course_offering_id=%s AND g.status='Draft'",(offering_id,))
        log_action(db,"Grade roster submitted",f"Lecturer ID {user['lecturer_id']} submitted offering {offering_id}")
    return {"submitted":True,"status":"Submitted"}


@app.post("/api/admin/offerings/{offering_id}/approve")
def approve_grade_roster(offering_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        result=db.execute("UPDATE course_grades g SET status='Published',approved_at=NOW(),updated_at=NOW() FROM course_registrations cr WHERE cr.id=g.registration_id AND cr.course_offering_id=%s AND g.status='Submitted'",(offering_id,))
        if result.rowcount==0: raise HTTPException(status_code=409,detail="No submitted grades are available for approval.")
        log_action(db,"Grade roster published",f"Administrator published offering {offering_id}")
    return {"published":True,"grades_published":result.rowcount}


@app.get("/api/student/results")
def student_results(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Student")
    with connect() as db:
        return db.execute(
            """SELECT c.course_code,c.title AS course_title,c.credit_units,g.score,
            CASE WHEN g.score>=70 THEN 'A' WHEN g.score>=60 THEN 'B' WHEN g.score>=50 THEN 'C'
                 WHEN g.score>=45 THEN 'D' WHEN g.score>=40 THEN 'E' ELSE 'F' END AS letter_grade,g.status,
            s.name AS semester,a.name AS academic_session FROM course_grades g
            JOIN course_registrations cr ON cr.id=g.registration_id JOIN course_offerings o ON o.id=cr.course_offering_id
            JOIN courses c ON c.id=o.course_id JOIN semesters s ON s.id=o.semester_id
            JOIN academic_sessions a ON a.id=s.academic_session_id
            WHERE cr.student_id=%s AND g.status='Published' ORDER BY a.name DESC,s.name,c.course_code""",
            (user["student_id"],)).fetchall()


@app.get("/api/admin/lecturers")
def list_lecturers(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute(
            """SELECT l.id,l.staff_number,l.first_name,l.last_name,l.status,d.name AS department
            FROM lecturers l JOIN departments d ON d.id=l.department_id ORDER BY l.last_name,l.first_name"""
        ).fetchall()


@app.post("/api/admin/lecturers",status_code=201)
def create_lecturer(payload:LecturerInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        try:
            row=db.execute(
                """INSERT INTO lecturers (staff_number,first_name,last_name,department_id)
                VALUES (%s,%s,%s,%s) RETURNING id,staff_number,first_name,last_name,department_id,status""",
                (payload.staff_number.strip(),payload.first_name.strip(),payload.last_name.strip(),payload.department_id)
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="Staff number already exists.") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise HTTPException(status_code=404,detail="Department not found.") from exc
        log_action(db,"Lecturer created",f"Lecturer record {payload.staff_number}")
    return row


@app.get("/api/admin/courses")
def list_courses(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute(
            """SELECT c.id,c.course_code,c.title,c.credit_units,c.level,c.is_active,d.id AS department_id,d.name AS department
            FROM courses c JOIN departments d ON d.id=c.department_id ORDER BY d.name,c.level,c.course_code"""
        ).fetchall()


@app.post("/api/admin/courses",status_code=201)
def create_course(payload:CourseInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        try:
            row=db.execute(
                """INSERT INTO courses (department_id,course_code,title,credit_units,level)
                VALUES (%s,%s,%s,%s,%s) RETURNING *""",
                (payload.department_id,payload.course_code.strip().upper(),payload.title.strip(),payload.credit_units,payload.level)
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="This course code already exists in the department.") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise HTTPException(status_code=404,detail="Department not found.") from exc
        log_action(db,"Course created",payload.course_code.strip().upper())
    return row


@app.post("/api/admin/course-offerings",status_code=201)
def create_course_offering(payload:OfferingInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        try:
            row=db.execute(
                """INSERT INTO course_offerings (course_id,semester_id,section,lecturer_id,capacity,status)
                VALUES (%s,%s,%s,%s,%s,'Open') RETURNING *""",
                (payload.course_id,payload.semester_id,payload.section.strip().upper(),payload.lecturer_id,payload.capacity)
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="This course offering section already exists for the semester.") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise HTTPException(status_code=404,detail="Course, semester, or lecturer not found.") from exc
        log_action(db,"Course offering opened",f"Offering ID {row['id']}")
    return row


@app.get("/api/admin/course-offerings")
def list_admin_course_offerings(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute(
            """SELECT o.id AS offering_id,o.lecturer_id,o.status,o.section,c.id AS course_id,
            c.course_code,c.title AS course_title,c.level,c.credit_units,d.name AS department,
            s.name AS semester,a.name AS academic_session,l.first_name AS lecturer_first_name,
            l.last_name AS lecturer_last_name
            FROM course_offerings o JOIN courses c ON c.id=o.course_id
            JOIN departments d ON d.id=c.department_id JOIN semesters s ON s.id=o.semester_id
            JOIN academic_sessions a ON a.id=s.academic_session_id
            LEFT JOIN lecturers l ON l.id=o.lecturer_id
            ORDER BY a.name DESC,s.name,d.name,c.level,c.course_code"""
        ).fetchall()


@app.patch("/api/admin/course-offerings/{offering_id}/lecturer")
def assign_offering_lecturer(offering_id:int,payload:LecturerAssignmentInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        row=db.execute(
            """UPDATE course_offerings SET lecturer_id=%s WHERE id=%s
            RETURNING id,course_id,semester_id,lecturer_id,status""",
            (payload.lecturer_id,offering_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404,detail="Course offering not found.")
        log_action(db,"Course lecturer assignment changed",f"Offering {offering_id}; lecturer {payload.lecturer_id or 'unassigned'}")
    return row



@app.get("/api/exams-officer/ready-results")
def exams_officer_ready_results(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"ExamsOfficer")
    with connect() as db:
        return db.execute(
            """SELECT s.id AS semester_id,s.name AS semester,a.name AS academic_session,c.level,
            COUNT(DISTINCT o.id)::int AS courses,
            COUNT(DISTINCT cr.student_id)::int AS students,
            COUNT(DISTINCT g.id) FILTER (WHERE g.status='Draft')::int AS entered_scores,
            x.status AS submission_status
            FROM course_offerings o JOIN courses c ON c.id=o.course_id
            JOIN semesters s ON s.id=o.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
            LEFT JOIN course_registrations cr ON cr.course_offering_id=o.id AND cr.status='Registered'
            LEFT JOIN course_grades g ON g.registration_id=cr.id
            LEFT JOIN department_result_submissions x ON x.department_id=c.department_id AND x.semester_id=s.id AND x.level=c.level
            WHERE c.department_id=%s AND o.status IN ('Open','Closed','Completed')
            GROUP BY s.id,s.name,a.name,c.level,x.status
            ORDER BY a.name DESC,s.name,c.level""",(user["department_id"],)
        ).fetchall()


@app.get("/api/exams-officer/gradebook")
def exams_officer_gradebook(semester_id:int=Query(gt=0),level:str=Query(pattern="^(100|200|300|400|500|600)$"),user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"ExamsOfficer")
    with connect() as db:
        department=db.execute("SELECT id,name FROM departments WHERE id=%s",(user["department_id"],)).fetchone()
        semester=db.execute("SELECT s.id,s.name,a.name AS academic_session FROM semesters s JOIN academic_sessions a ON a.id=s.academic_session_id WHERE s.id=%s",(semester_id,)).fetchone()
        if not department or not semester:raise HTTPException(status_code=404,detail="Department or semester not found.")
        students=db.execute(
            """SELECT id AS student_id,matric_number,first_name,last_name,level
            FROM students WHERE department_id=%s AND level=%s AND status='Active' ORDER BY matric_number""",
            (user["department_id"],level)
        ).fetchall()
        offerings=db.execute(
            """SELECT o.id AS offering_id,c.course_code,c.title AS course_title,c.credit_units,c.level,
            o.section,l.first_name AS lecturer_first_name,l.last_name AS lecturer_last_name
            FROM course_offerings o JOIN courses c ON c.id=o.course_id
            LEFT JOIN lecturers l ON l.id=o.lecturer_id
            WHERE c.department_id=%s AND c.level=%s AND o.semester_id=%s
            AND o.status IN ('Open','Closed','Completed') ORDER BY c.course_code,o.section""",
            (user["department_id"],level,semester_id)
        ).fetchall()
        courses=[]
        for offering in offerings:
            roster=db.execute(
                """SELECT st.id AS student_id,st.matric_number,st.first_name,st.last_name,
                cr.id AS registration_id,cr.status AS registration_status,g.score,g.status AS grade_status
                FROM students st LEFT JOIN course_registrations cr
                  ON cr.student_id=st.id AND cr.course_offering_id=%s AND cr.status='Registered'
                LEFT JOIN course_grades g ON g.registration_id=cr.id
                WHERE st.department_id=%s AND st.level=%s AND st.status='Active'
                ORDER BY st.matric_number""",
                (offering["offering_id"],user["department_id"],level)
            ).fetchall()
            courses.append({**offering,"roster":roster})
        submission=db.execute("SELECT id,status FROM department_result_submissions WHERE department_id=%s AND semester_id=%s AND level=%s",(user["department_id"],semester_id,level)).fetchone()
    return {"department":department["name"],"semester_id":semester_id,"semester":semester["name"],"academic_session":semester["academic_session"],"level":level,"students":students,"courses":courses,"submission":submission}


@app.put("/api/exams-officer/offerings/{offering_id}/grades")
def save_officer_grade_roster(offering_id:int,payload:GradeRosterInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"ExamsOfficer")
    ids=[g.student_id for g in payload.grades]
    if len(ids)!=len(set(ids)):raise HTTPException(status_code=422,detail="The grade sheet contains duplicate students.")
    with connect() as db:
        offering=db.execute(
            """SELECT o.id,o.semester_id,c.level,c.department_id FROM course_offerings o
            JOIN courses c ON c.id=o.course_id WHERE o.id=%s AND c.department_id=%s""",
            (offering_id,user["department_id"])
        ).fetchone()
        if not offering:raise HTTPException(status_code=404,detail="This course does not belong to your assigned department.")
        submission=db.execute("SELECT status FROM department_result_submissions WHERE department_id=%s AND semester_id=%s AND level=%s",(user["department_id"],offering["semester_id"],offering["level"])).fetchone()
        if submission and submission["status"] in ("Submitted","Approved"):raise HTTPException(status_code=409,detail="This departmental result package is locked. Ask the administrator to reject it before making corrections.")
        registrations=db.execute(
            """SELECT id,student_id FROM course_registrations
            WHERE course_offering_id=%s AND status='Registered' AND student_id=ANY(%s)""",
            (offering_id,ids)
        ).fetchall()
        mapping={r["student_id"]:r["id"] for r in registrations}
        if len(mapping)!=len(ids):raise HTTPException(status_code=422,detail="A score was entered for a student who is not registered for this course.")
        for grade in payload.grades:
            registration_id=mapping[grade.student_id]
            existing=db.execute("SELECT status FROM course_grades WHERE registration_id=%s",(registration_id,)).fetchone()
            if existing and existing["status"] in ("Submitted","Approved","Published"):raise HTTPException(status_code=409,detail="A submitted or published grade cannot be edited.")
            db.execute(
                """INSERT INTO course_grades (registration_id,score,status,entered_by,updated_at)
                VALUES (%s,%s,'Draft',%s,NOW())
                ON CONFLICT (registration_id) DO UPDATE SET score=EXCLUDED.score,status='Draft',entered_by=EXCLUDED.entered_by,updated_at=NOW()""",
                (registration_id,grade.score,user["id"])
            )
        log_action(db,"Examination officer saved course grade sheet",f"Department {user['department_id']}; offering {offering_id}; {len(ids)} scores")
    return {"saved":len(ids),"status":"Draft"}


@app.post("/api/exams-officer/submissions",status_code=201)
def submit_department_results(payload:DepartmentSubmissionInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"ExamsOfficer")
    with connect() as db:
        expected=db.execute(
            """SELECT COUNT(*)::int AS total FROM course_registrations cr
            JOIN course_offerings o ON o.id=cr.course_offering_id JOIN courses c ON c.id=o.course_id
            WHERE c.department_id=%s AND o.semester_id=%s AND c.level=%s
            AND o.status IN ('Open','Closed','Completed') AND cr.status='Registered'""",
            (user["department_id"],payload.semester_id,payload.level)
        ).fetchone()["total"]
        grades=db.execute(
            """SELECT g.id FROM course_grades g JOIN course_registrations cr ON cr.id=g.registration_id
            JOIN course_offerings o ON o.id=cr.course_offering_id JOIN courses c ON c.id=o.course_id
            WHERE c.department_id=%s AND o.semester_id=%s AND c.level=%s
            AND o.status IN ('Open','Closed','Completed') AND cr.status='Registered' AND g.status='Draft'
            ORDER BY g.id""",(user["department_id"],payload.semester_id,payload.level)
        ).fetchall()
        if expected==0:raise HTTPException(status_code=409,detail="There are no registered course places for this department, semester and level.")
        if len(grades)!=expected:raise HTTPException(status_code=409,detail=f"Complete every registered student score before submission. {len(grades)} of {expected} scores are entered.")
        existing=db.execute("SELECT id,status FROM department_result_submissions WHERE department_id=%s AND semester_id=%s AND level=%s FOR UPDATE",(user["department_id"],payload.semester_id,payload.level)).fetchone()
        if existing and existing["status"]!="Rejected":raise HTTPException(status_code=409,detail="A departmental result package already exists for this semester and level.")
        if existing:
            submission=db.execute(
                """UPDATE department_result_submissions SET status='Submitted',submitted_by=%s,
                reviewed_by=NULL,reviewed_at=NULL,review_note=NULL,submitted_at=NOW()
                WHERE id=%s RETURNING id""",(user["id"],existing["id"])
            ).fetchone()
            db.execute("DELETE FROM department_result_submission_grades WHERE submission_id=%s",(submission["id"],))
        else:
            submission=db.execute(
                """INSERT INTO department_result_submissions (department_id,semester_id,level,submitted_by)
                VALUES (%s,%s,%s,%s) RETURNING id""",(user["department_id"],payload.semester_id,payload.level,user["id"])
            ).fetchone()
        db.execute("UPDATE course_grades SET status='Submitted',submitted_at=NOW(),updated_at=NOW() WHERE id=ANY(%s)",([g["id"] for g in grades],))
        with db.cursor() as cursor:
            cursor.executemany("INSERT INTO department_result_submission_grades (submission_id,grade_id) VALUES (%s,%s)",[(submission["id"],g["id"]) for g in grades])
        log_action(db,"Departmental results submitted",f"Department {user['department_id']}; semester {payload.semester_id}; level {payload.level}; {len(grades)} scores")
    return {"submission_id":submission["id"],"grades_submitted":len(grades),"status":"Submitted"}


@app.get("/api/admin/department-submissions")
def list_department_submissions(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute(
            """SELECT x.id AS submission_id,f.name AS faculty_name,d.name AS department_name,
            s.name AS semester,a.name AS academic_session,x.level,x.status,x.submitted_at,
            COUNT(DISTINCT sg.grade_id)::int AS grades_count,
            COUNT(DISTINCT cr.student_id)::int AS students_count,
            COUNT(DISTINCT o.id)::int AS courses_count
            FROM department_result_submissions x
            JOIN departments d ON d.id=x.department_id JOIN faculties f ON f.id=d.faculty_id
            JOIN semesters s ON s.id=x.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
            LEFT JOIN department_result_submission_grades sg ON sg.submission_id=x.id
            LEFT JOIN course_grades g ON g.id=sg.grade_id
            LEFT JOIN course_registrations cr ON cr.id=g.registration_id
            LEFT JOIN course_offerings o ON o.id=cr.course_offering_id
            GROUP BY x.id,f.name,d.name,s.name,a.name
            ORDER BY f.name,d.name,x.level,a.name DESC,s.name"""
        ).fetchall()


@app.post("/api/admin/department-submissions/{submission_id}/approve")
def approve_department_submission(submission_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        submission=db.execute("SELECT id,status FROM department_result_submissions WHERE id=%s FOR UPDATE",(submission_id,)).fetchone()
        if not submission:raise HTTPException(status_code=404,detail="Departmental submission not found.")
        if submission["status"]!="Submitted":raise HTTPException(status_code=409,detail="Only submitted departmental results can be approved.")
        changed=db.execute(
            """UPDATE course_grades SET status='Published',approved_at=NOW(),updated_at=NOW()
            WHERE id IN (SELECT grade_id FROM department_result_submission_grades WHERE submission_id=%s)
            AND status='Submitted'""",(submission_id,)
        ).rowcount
        db.execute("UPDATE department_result_submissions SET status='Approved',reviewed_by=%s,reviewed_at=NOW() WHERE id=%s",(user["id"],submission_id))
        log_action(db,"Departmental results approved",f"Submission {submission_id}; {changed} grades published")
    return {"approved":True,"grades_published":changed}


@app.post("/api/admin/department-submissions/{submission_id}/reject")
def reject_department_submission(submission_id:int,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        submission=db.execute("SELECT id,status FROM department_result_submissions WHERE id=%s FOR UPDATE",(submission_id,)).fetchone()
        if not submission:raise HTTPException(status_code=404,detail="Departmental submission not found.")
        if submission["status"]!="Submitted":raise HTTPException(status_code=409,detail="Only submitted departmental results can be rejected.")
        db.execute(
            """UPDATE course_grades SET status='Draft',submitted_at=NULL,updated_at=NOW()
            WHERE id IN (SELECT grade_id FROM department_result_submission_grades WHERE submission_id=%s)
            AND status='Submitted'""",(submission_id,)
        )
        db.execute("UPDATE department_result_submissions SET status='Rejected',reviewed_by=%s,reviewed_at=NOW() WHERE id=%s",(user["id"],submission_id))
        log_action(db,"Departmental results rejected",f"Submission {submission_id}")
    return {"rejected":True}


@app.get("/api/admin/department-results")
def department_results(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute(
            """SELECT f.id AS faculty_id,f.name AS faculty_name,
            d.id AS department_id,d.name AS department_name,
            c.level,st.id AS student_id,st.matric_number,st.first_name,st.last_name,
            c.course_code,c.title AS course_title,c.credit_units,g.score,g.letter_grade,g.status AS grade_status,
            a.name AS academic_session,s.name AS semester,
            l.first_name AS lecturer_first_name,l.last_name AS lecturer_last_name,
            o.id AS offering_id
            FROM course_grades g
            JOIN course_registrations cr ON cr.id=g.registration_id
            JOIN students st ON st.id=cr.student_id
            JOIN course_offerings o ON o.id=cr.course_offering_id
            JOIN courses c ON c.id=o.course_id
            JOIN departments d ON d.id=c.department_id
            JOIN faculties f ON f.id=d.faculty_id
            JOIN semesters s ON s.id=o.semester_id
            JOIN academic_sessions a ON a.id=s.academic_session_id
            LEFT JOIN lecturers l ON l.id=o.lecturer_id
            WHERE g.status IN ('Submitted','Published')
            ORDER BY f.name,d.name,c.level,st.last_name,st.first_name,c.course_code"""
        ).fetchall()


@app.get("/api/admin/grade-submissions")
def grade_submissions(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute(
            """SELECT o.id AS offering_id,c.course_code,c.title AS course_title,o.section,
            c.level,d.name AS department_name,f.name AS faculty_name,
            s.name AS semester,a.name AS academic_session,
            l.first_name AS lecturer_first_name,l.last_name AS lecturer_last_name,
            COUNT(cr.id) FILTER (WHERE cr.status='Registered')::int AS roster_count,
            COUNT(g.id) FILTER (WHERE g.status='Submitted')::int AS submitted_count,
            COUNT(g.id) FILTER (WHERE g.status='Published')::int AS published_count
            FROM course_offerings o JOIN courses c ON c.id=o.course_id
            JOIN departments d ON d.id=c.department_id JOIN faculties f ON f.id=d.faculty_id
            JOIN semesters s ON s.id=o.semester_id JOIN academic_sessions a ON a.id=s.academic_session_id
            LEFT JOIN lecturers l ON l.id=o.lecturer_id
            LEFT JOIN course_registrations cr ON cr.course_offering_id=o.id
            LEFT JOIN course_grades g ON g.registration_id=cr.id
            GROUP BY o.id,c.course_code,c.title,o.section,c.level,d.name,f.name,s.name,a.name,l.first_name,l.last_name
            ORDER BY f.name,d.name,c.level,a.name DESC,s.name,c.course_code"""
        ).fetchall()


@app.get("/api/admin/academic-sessions")
def list_academic_sessions(user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        return db.execute("SELECT id,name,starts_on,ends_on,is_current FROM academic_sessions ORDER BY name DESC").fetchall()


@app.post("/api/admin/academic-sessions",status_code=201)
def create_academic_session(payload:AcademicSessionInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    if payload.starts_on and payload.ends_on and payload.starts_on>payload.ends_on:
        raise HTTPException(status_code=422,detail="Session start date must be before its end date.")
    with connect() as db:
        if payload.is_current:
            db.execute("UPDATE academic_sessions SET is_current=FALSE WHERE is_current=TRUE")
        if not payload.starts_on or not payload.ends_on:
            raise HTTPException(status_code=422,detail="Session start and end dates are required to generate the semester calendar.")
        try:
            row=db.execute("INSERT INTO academic_sessions (name,starts_on,ends_on,is_current) VALUES (%s,%s,%s,%s) RETURNING *",(payload.name.strip(),payload.starts_on,payload.ends_on,payload.is_current)).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="Academic session already exists.") from exc
        total_days=(payload.ends_on-payload.starts_on).days+1
        if payload.include_summer:
            if total_days<3:
                raise HTTPException(status_code=422,detail="The session must span at least three days to generate three semesters.")
            first_days=total_days//3
            second_days=total_days//3
            first_end=payload.starts_on+timedelta(days=first_days-1)
            second_start=first_end+timedelta(days=1)
            second_end=second_start+timedelta(days=second_days-1)
            calendar=[
                ("First Semester",payload.starts_on,first_end),
                ("Second Semester",second_start,second_end),
                ("Summer",second_end+timedelta(days=1),payload.ends_on),
            ]
        else:
            midpoint=payload.starts_on+timedelta(days=total_days//2)
            calendar=[
                ("First Semester",payload.starts_on,midpoint),
                ("Second Semester",midpoint+timedelta(days=1),payload.ends_on),
            ]
        for semester_name,semester_start,semester_end in calendar:
            registration_opens=datetime.combine(semester_start-timedelta(days=14),datetime.min.time(),tzinfo=timezone.utc)
            registration_closes=datetime.combine(semester_start+timedelta(days=14),datetime.min.time(),tzinfo=timezone.utc)
            db.execute(
                """INSERT INTO semesters
                (academic_session_id,name,starts_on,ends_on,registration_opens_at,registration_closes_at,is_published)
                VALUES (%s,%s,%s,%s,%s,%s,TRUE)""",
                (row["id"],semester_name,semester_start,semester_end,registration_opens,registration_closes),
            )
        log_action(db,"Academic session created",f"{row['name']} with First and Second Semester calendars")
    return row


@app.get("/api/admin/semesters")
def list_semesters(session_id:int|None=Query(default=None,gt=0),user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    with connect() as db:
        if session_id:
            return db.execute("SELECT id,academic_session_id,name,starts_on,ends_on,registration_opens_at,registration_closes_at,is_published FROM semesters WHERE academic_session_id=%s ORDER BY id",(session_id,)).fetchall()
        return db.execute("SELECT id,academic_session_id,name,starts_on,ends_on,registration_opens_at,registration_closes_at,is_published FROM semesters ORDER BY academic_session_id DESC,id").fetchall()


@app.post("/api/admin/semesters",status_code=201)
def create_semester(payload:SemesterInput,user:dict[str,Any]=Depends(get_current_user)):
    require_roles(user,"Administrator")
    if payload.registration_opens_at and payload.registration_closes_at and payload.registration_opens_at>payload.registration_closes_at:
        raise HTTPException(status_code=422,detail="Registration opening time must be before its closing time.")
    with connect() as db:
        try:
            row=db.execute(
                """INSERT INTO semesters (academic_session_id,name,registration_opens_at,registration_closes_at,is_published)
                VALUES (%s,%s,%s,%s,%s) RETURNING *""",
                (payload.academic_session_id,payload.name,payload.registration_opens_at,payload.registration_closes_at,payload.is_published)
            ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409,detail="This semester already exists for the academic session.") from exc
        except psycopg.errors.ForeignKeyViolation as exc:
            raise HTTPException(status_code=404,detail="Academic session not found.") from exc
    return row
