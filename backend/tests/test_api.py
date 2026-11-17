from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database(monkeypatch):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests.")
    monkeypatch.setenv("CAMPUSBOOK_BOOTSTRAP_SECRET", "test-only-bootstrap-secret")
    monkeypatch.setenv("CAMPUSBOOK_TESTING", "1")
    main.initialize_database()
    client.cookies.clear()
    with main.connect() as db:
        db.execute("""TRUNCATE TABLE
            course_grades,course_registrations,course_offerings,courses,semesters,academic_sessions,
            user_sessions,user_accounts,lecturers,results,students,activity_logs,backup_snapshots,
            departments,faculties RESTART IDENTITY CASCADE""")
        faculties = [
            ("Faculty of Engineering","ENG"),
            ("Faculty of Science","SCI"),
            ("Faculty of Administration and Management","MGS"),
        ]
        faculty_ids = {}
        for name, code in faculties:
            row = db.execute("INSERT INTO faculties (name,code) VALUES (%s,%s) RETURNING id",(name,code)).fetchone()
            faculty_ids[code] = row["id"]
        departments = [
            ("Computer Engineering","CPE",faculty_ids["ENG"]),
            ("Computer Science","CSC",faculty_ids["SCI"]),
            ("Electrical Engineering","EEE",faculty_ids["ENG"]),
            ("Accountancy","ACC",faculty_ids["MGS"]),
        ]
        for name, code, faculty_id in departments:
            db.execute("INSERT INTO departments (name,code,faculty_id) VALUES (%s,%s,%s)",(name,code,faculty_id))
    boot=client.post(
        "/api/auth/bootstrap",
        json={"username":"admin","password":"test-admin-password-123"},
        headers={"X-CampusBook-Bootstrap-Secret":"test-only-bootstrap-secret"},
    )
    assert boot.status_code == 201


def login(username="admin",password="test-admin-password-123"):
    client.post("/api/auth/logout")
    return client.post("/api/auth/login",json={"username":username,"password":password})


def student_payload(matric="DE/2023/0001"):
    return {
        "matric_number":matric,
        "first_name":"Ada",
        "last_name":"Okoro",
        "department":"Computer Engineering",
        "level":"300",
        "status":"Active",
    }


def test_health_and_authentication():
    assert client.get("/api/health").status_code == 200
    client.cookies.clear()
    assert client.get("/api/students").status_code == 401
    assert client.post("/api/auth/login",json={"username":"admin","password":"wrong-password"}).status_code == 401
    assert login().status_code == 200
    assert client.get("/api/auth/me").json()["role"] == "Administrator"


def test_student_crud_and_conflict():
    created=client.post("/api/students",json=student_payload())
    assert created.status_code == 201
    student_id=created.json()["id"]
    assert "email" not in created.json()
    assert created.json()["department_id"] > 0
    assert client.post("/api/students",json=student_payload()).status_code == 409
    updated=client.put(f"/api/students/{student_id}",json={**student_payload(),"first_name":"Adaeze","status":"Inactive"})
    assert updated.status_code == 200 and updated.json()["first_name"] == "Adaeze"
    assert len(client.get("/api/students?search=adaeze").json()) == 1
    assert client.delete(f"/api/students/{student_id}").status_code == 200
    assert client.get("/api/students?search=adaeze").json() == []
    assert client.delete(f"/api/students/{student_id}").status_code == 404
    assert client.post("/api/students",json={**student_payload(),"matric_number":"BAD-001"}).status_code == 422


def test_faculty_department_results_and_cascade():
    student=client.post("/api/students",json=student_payload("DE/2023/0002")).json()
    result=client.post("/api/results",json={
        "student_id":student["id"],"course_code":"CPE301","course_title":"Data Communications",
        "score":78.5,"semester":"First Semester 2026/2027",
    })
    assert result.status_code == 201
    assert len(client.get("/api/results").json()) == 1
    with main.connect() as db:
        mgs=db.execute("SELECT id FROM faculties WHERE code='MGS'").fetchone()["id"]
    department=client.post("/api/departments",json={"name":"Marketing","code":"MKT","faculty_id":mgs})
    assert department.status_code == 201 and department.json()["faculty_id"] == mgs
    assert client.delete(f"/api/students/{student['id']}").status_code == 200
    assert client.get("/api/results").json() == []


def test_student_course_registration_and_lecturer_grade_workflow():
    student=client.post("/api/students",json=student_payload("DE/2023/0003")).json()
    with main.connect() as db:
        department_id=db.execute("SELECT id FROM departments WHERE code='CPE'").fetchone()["id"]
        session_id=db.execute("INSERT INTO academic_sessions (name,is_current) VALUES ('2026/2027',TRUE) RETURNING id").fetchone()["id"]
        semester_id=db.execute("INSERT INTO semesters (academic_session_id,name,is_published) VALUES (%s,'First Semester',TRUE) RETURNING id",(session_id,)).fetchone()["id"]
    lecturer=client.post("/api/admin/lecturers",json={"staff_number":"STAFF-001","first_name":"Grace","last_name":"Eze","department_id":department_id})
    assert lecturer.status_code == 201
    lecturer_id=lecturer.json()["id"]
    course=client.post("/api/admin/courses",json={"department_id":department_id,"course_code":"CPE301","title":"Data Communications","credit_units":3,"level":"300"})
    assert course.status_code == 201
    offering=client.post("/api/admin/course-offerings",json={"course_id":course.json()["id"],"semester_id":semester_id,"section":"A","lecturer_id":lecturer_id,"capacity":40})
    assert offering.status_code == 201
    offering_id=offering.json()["id"]
    assert client.post("/api/admin/accounts",json={"username":"student001","password":"test-student-password-123","role":"Student","student_id":student["id"]}).status_code == 201
    assert client.post("/api/admin/accounts",json={"username":"lecturer001","password":"test-lecturer-password-123","role":"Lecturer","lecturer_id":lecturer_id}).status_code == 201
    assert login("student001","test-student-password-123").status_code == 200
    assert client.get("/api/students").status_code == 403
    assert client.post(f"/api/student/course-offerings/{offering_id}/register").status_code == 201
    assert len(client.get("/api/student/registrations").json()) == 1
    assert login("lecturer001","test-lecturer-password-123").status_code == 200
    roster=client.get(f"/api/lecturer/offerings/{offering_id}/roster")
    assert roster.status_code == 200 and len(roster.json()) == 1
    saved=client.put(f"/api/lecturer/offerings/{offering_id}/grades",json={"grades":[{"student_id":student["id"],"score":85}]})
    assert saved.status_code == 200 and saved.json()["saved"] == 1
    assert client.post(f"/api/lecturer/offerings/{offering_id}/submit").status_code == 200
    assert client.post(f"/api/admin/offerings/{offering_id}/approve").status_code == 403
    assert login().status_code == 200
    approved=client.post(f"/api/admin/offerings/{offering_id}/approve")
    assert approved.status_code == 200 and approved.json()["grades_published"] == 1
    assert login("student001","test-student-password-123").status_code == 200
    results=client.get("/api/student/results")
    assert results.status_code == 200 and results.json()[0]["score"] == 85


def test_backup_restore_round_trip_and_safety_snapshot():
    student=client.post("/api/students",json=student_payload("DE/2023/0004")).json()
    assert client.post("/api/results",json={"student_id":student["id"],"course_code":"CPE302","course_title":"Digital Systems","score":82,"semester":"First Semester 2026/2027"}).status_code == 201
    backup=client.post("/api/backups")
    assert backup.status_code == 200
    filename=backup.json()["filename"]
    assert client.delete(f"/api/students/{student['id']}").status_code == 200
    assert client.get("/api/students").json() == []
    restored=client.post(f"/api/backups/{filename}/restore")
    assert restored.status_code == 200 and restored.json()["integrity"] == "ok"
    assert login().status_code == 200
    assert len(client.get("/api/students").json()) == 1
    assert len(client.get("/api/results").json()) == 1
    assert restored.json()["safety_backup"].endswith(".json")
    assert len(client.get("/api/backups").json()) == 2


def test_backup_validation_and_filename_guard():
    assert client.post("/api/backups/not-a-campusbook-backup.json/restore").status_code == 400
    assert client.post("/api/backups/campusbook-20260101-000000-000000.json/restore").status_code == 404


def test_dashboard_and_activity():
    assert client.post("/api/students",json=student_payload("DE/2023/0005")).status_code == 201
    dashboard=client.get("/api/dashboard").json()
    assert dashboard["total_students"] == 1 and dashboard["active_students"] == 1
    assert any(row["action"]=="Student created" for row in client.get("/api/activity").json())
