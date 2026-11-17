from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
import psycopg

from app import main
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests.")
    main.initialize_database()
    with main.connect() as db:
        db.execute(
            "TRUNCATE TABLE results, students, activity_logs, backup_snapshots, departments RESTART IDENTITY CASCADE"
        )
        db.executemany(
            "INSERT INTO departments (name, code) VALUES (%s, %s)",
            [
                ("Computer Engineering", "CPE"),
                ("Computer Science", "CSC"),
                ("Electrical Engineering", "EEE"),
                ("Accountancy", "ACC"),
            ],
        )
    yield


client = TestClient(app)


def student_payload(matric: str = "RSU/2024/CPE/001"):
    return {
        "matric_number": matric,
        "first_name": "Ada",
        "last_name": "Okoro",
        "email": "ada@example.test",
        "department": "Computer Engineering",
        "level": "300",
        "status": "Active",
    }


def test_health_checks_database():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_student_crud_and_conflict():
    created = client.post("/api/students", json=student_payload())
    assert created.status_code == 201
    student_id = created.json()["id"]

    duplicate = client.post("/api/students", json=student_payload())
    assert duplicate.status_code == 409

    updated_payload = {**student_payload(), "first_name": "Adaeze", "status": "Inactive"}
    updated = client.put(f"/api/students/{student_id}", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Adaeze"

    assert len(client.get("/api/students?search=adaeze").json()) == 1
    deleted = client.delete(f"/api/students/{student_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/students?search=adaeze").json() == []
    assert client.delete(f"/api/students/{student_id}").status_code == 404


def test_departments_results_and_cascade():
    student = client.post("/api/students", json=student_payload("RSU/2024/CPE/002"))
    assert student.status_code == 201
    student_id = student.json()["id"]

    result = client.post("/api/results", json={
        "student_id": student_id,
        "course_code": "CPE 301",
        "course_title": "Data Communications",
        "score": 78.5,
        "semester": "First Semester 2026/2027",
    })
    assert result.status_code == 201
    assert result.json()["score"] == 78.5
    assert len(client.get("/api/results").json()) == 1

    department = client.post("/api/departments", json={"name": "Civil Engineering", "code": "CVE"})
    assert department.status_code == 201
    assert any(d["code"] == "CVE" for d in client.get("/api/departments").json())

    assert client.delete(f"/api/students/{student_id}").status_code == 200
    assert client.get("/api/results").json() == []


def test_backup_restore_round_trip_and_safety_snapshot():
    student = client.post("/api/students", json=student_payload("RSU/2024/CPE/003"))
    student_id = student.json()["id"]
    result = client.post("/api/results", json={
        "student_id": student_id,
        "course_code": "CPE 302",
        "course_title": "Digital Systems",
        "score": 82,
        "semester": "First Semester 2026/2027",
    })
    assert result.status_code == 201

    backup = client.post("/api/backups")
    assert backup.status_code == 200
    filename = backup.json()["filename"]
    assert filename.endswith(".json")

    assert client.delete(f"/api/students/{student_id}").status_code == 200
    assert client.get("/api/students").json() == []

    restored = client.post(f"/api/backups/{filename}/restore")
    assert restored.status_code == 200
    assert restored.json()["integrity"] == "ok"
    assert len(client.get("/api/students").json()) == 1
    assert len(client.get("/api/results").json()) == 1
    assert restored.json()["safety_backup"].endswith(".json")
    assert len(client.get("/api/backups").json()) == 2


def test_backup_validation_and_filename_guard():
    assert client.post("/api/backups/../../bad.json/restore").status_code == 400
    assert client.post("/api/backups/campusbook-20260101-000000-000000.json/restore").status_code == 404


def test_dashboard_and_activity():
    assert client.post("/api/students", json=student_payload("RSU/2024/CPE/004")).status_code == 201
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["total_students"] == 1
    assert dashboard["active_students"] == 1
    assert any(row["action"] == "Student created" for row in client.get("/api/activity").json())
