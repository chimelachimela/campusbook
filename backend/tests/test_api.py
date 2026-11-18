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
            demo_change_requests,department_result_submission_grades,department_result_submissions,course_grades,course_registrations,course_offerings,courses,semesters,academic_sessions,
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




def test_academic_session_generates_semester_calendar_and_registration_windows():
    response=client.post("/api/admin/academic-sessions",json={
        "name":"2028/2029","starts_on":"2028-09-01","ends_on":"2029-06-30",
        "is_current":True,"include_summer":True,
    })
    assert response.status_code==201
    semesters=client.get("/api/admin/semesters").json()
    generated=[x for x in semesters if x["academic_session_id"]==response.json()["id"]]
    assert [x["name"] for x in generated]==["First Semester","Second Semester","Summer"]
    assert all(x["starts_on"] and x["ends_on"] and x["registration_opens_at"] and x["registration_closes_at"] for x in generated)


def test_department_examination_officer_submits_and_admin_approves_department_results():
    student=client.post("/api/students",json=student_payload("DE/2023/0201")).json()
    with main.connect() as db:
        department_id=db.execute("SELECT id FROM departments WHERE code='CPE'").fetchone()["id"]
        session_id=db.execute("INSERT INTO academic_sessions (name,is_current) VALUES ('2027/2028',TRUE) RETURNING id").fetchone()["id"]
        semester_id=db.execute("INSERT INTO semesters (academic_session_id,name,is_published) VALUES (%s,'First Semester',TRUE) RETURNING id",(session_id,)).fetchone()["id"]
    lecturer=client.post("/api/admin/lecturers",json={"staff_number":"STAFF-EXAM-001","first_name":"Grace","last_name":"Eze","department_id":department_id}).json()
    course=client.post("/api/admin/courses",json={"department_id":department_id,"course_code":"CPE401","title":"Networks","credit_units":3,"level":"300"}).json()
    offering=client.post("/api/admin/course-offerings",json={"course_id":course["id"],"semester_id":semester_id,"lecturer_id":lecturer["id"]}).json()
    client.post("/api/admin/accounts",json={"username":"examstudent","password":"test-student-password-123","role":"Student","student_id":student["id"]})
    client.post("/api/admin/accounts",json={"username":"examlecturer","password":"test-lecturer-password-123","role":"Lecturer","lecturer_id":lecturer["id"]})
    officer=client.post("/api/admin/accounts",json={"username":"examofficer","password":"test-officer-password-123","role":"ExamsOfficer","department_id":department_id})
    assert officer.status_code==201 and officer.json()["role"]=="ExamsOfficer"
    assert login("examstudent","test-student-password-123").status_code==200
    assert client.post(f"/api/student/course-offerings/{offering['id']}/register").status_code==201
    assert login("examlecturer","test-lecturer-password-123").status_code==200
    assert client.put(f"/api/lecturer/offerings/{offering['id']}/grades",json={"grades":[{"student_id":student["id"],"score":91}]}).status_code==200
    assert client.post(f"/api/lecturer/offerings/{offering['id']}/submit").status_code==200
    assert login("examofficer","test-officer-password-123").status_code==200
    ready=client.get("/api/exams-officer/ready-results")
    assert ready.status_code==200 and ready.json()[0]["submitted_grades"]==1
    submitted=client.post("/api/exams-officer/submissions",json={"semester_id":semester_id,"level":"300"})
    assert submitted.status_code==201 and submitted.json()["grades_submitted"]==1
    assert client.get("/api/admin/department-submissions").status_code==403
    assert login().status_code==200
    queue=client.get("/api/admin/department-submissions")
    assert queue.status_code==200 and queue.json()[0]["status"]=="Submitted"
    approved=client.post(f"/api/admin/department-submissions/{submitted.json()['submission_id']}/approve")
    assert approved.status_code==200 and approved.json()["grades_published"]==1
    assert client.get("/api/admin/department-results").status_code==200
    assert login("examstudent","test-student-password-123").status_code==200
    assert client.get("/api/student/results").json()[0]["score"]==91


def test_backup_validation_and_filename_guard():
    assert client.post("/api/backups/not-a-campusbook-backup.json/restore").status_code == 400
    assert client.post("/api/backups/campusbook-20260101-000000-000000.json/restore").status_code == 404


def test_dashboard_and_activity():
    assert client.post("/api/students",json=student_payload("DE/2023/0005")).status_code == 201
    dashboard=client.get("/api/dashboard").json()
    assert dashboard["total_students"] == 1 and dashboard["active_students"] == 1
    assert any(row["action"]=="Student created" for row in client.get("/api/activity").json())


def test_self_service_signup_and_bulk_course_registration():
    student=client.post("/api/students",json=student_payload("DE/2023/0101")).json()
    with main.connect() as db:
        department_id=db.execute("SELECT id FROM departments WHERE code='CPE'").fetchone()["id"]
        session_id=db.execute("INSERT INTO academic_sessions (name,is_current) VALUES ('2026/2027',TRUE) RETURNING id").fetchone()["id"]
        semester_id=db.execute("INSERT INTO semesters (academic_session_id,name,is_published) VALUES (%s,'First Semester',TRUE) RETURNING id",(session_id,)).fetchone()["id"]
    lecturer=client.post("/api/admin/lecturers",json={"staff_number":"STAFF-SELF-001","first_name":"Ada","last_name":"Okoro","department_id":department_id}).json()
    course_ids=[]
    for code in ("CPE301","CPE302","CPE303"):
        course=client.post("/api/admin/courses",json={"department_id":department_id,"course_code":code,"title":code+" Course","credit_units":3,"level":"300"}).json()
        offering=client.post("/api/admin/course-offerings",json={"course_id":course["id"],"semester_id":semester_id,"section":"A","lecturer_id":lecturer["id"],"capacity":40})
        assert offering.status_code==201
        course_ids.append(offering.json()["id"])
    signup=client.post("/api/auth/signup",json={"email":"student@example.edu","password":"student-password-123","role":"Student","identity_number":"DE/2023/0101"})
    assert signup.status_code==201 and signup.json()["role"]=="Student"
    bulk=client.post("/api/student/course-offerings/register",json={"course_offering_ids":course_ids})
    assert bulk.status_code==200 and bulk.json()["registered"]==3
    assert len(client.get("/api/student/registrations").json())==3
    assert client.post("/api/student/course-offerings/register",json={"course_offering_ids":[course_ids[0],course_ids[0]]}).status_code==422
    client.post("/api/auth/logout")
    lecturer_signup=client.post("/api/auth/signup",json={"email":"lecturer@example.edu","password":"lecturer-password-123","role":"Lecturer","identity_number":"STAFF-SELF-001"})
    assert lecturer_signup.status_code==201 and lecturer_signup.json()["role"]=="Lecturer"
    assert len(client.get("/api/course-offerings").json())==3


def test_self_service_signup_requires_admin_created_academic_record():
    response=client.post("/api/auth/signup",json={"email":"unknown@example.edu","password":"student-password-123","role":"Student","identity_number":"DE/2099/9999"})
    assert response.status_code==404


def test_public_demo_administrator_writes_to_isolated_database_and_admin_can_apply_change(monkeypatch):
    primary_url=os.getenv("DATABASE_URL","")
    demo_url=os.getenv("CAMPUSBOOK_DEMO_DATABASE_URL","")
    assert demo_url and demo_url!=primary_url
    monkeypatch.setenv("CAMPUSBOOK_DEMO_ADMIN_ENABLED","true")
    monkeypatch.setenv("CAMPUSBOOK_DEMO_DATABASE_URL",demo_url)
    monkeypatch.setenv("DATABASE_URL",demo_url)
    main.initialize_database()
    with main.connect() as demo_db:
        demo_db.execute("INSERT INTO user_accounts (username,password_hash,role) VALUES ('demo.admin',%s,'Administrator')",(main.PASSWORD_HASHER.hash("demo-admin-password-123"),))
    monkeypatch.setenv("DATABASE_URL",primary_url)
    with main.connect() as db:
        db.execute("INSERT INTO user_accounts (username,password_hash,role) VALUES ('demo.admin',%s,'Administrator')",(main.PASSWORD_HASHER.hash("demo-admin-password-123"),))
        db.execute("INSERT INTO user_accounts (username,password_hash,role) VALUES ('institution.admin',%s,'Administrator')",(main.PASSWORD_HASHER.hash("institution-admin-password-123"),))
    demo=client.post("/api/auth/demo-admin")
    assert demo.status_code==200 and demo.json()["username"]=="demo.admin"
    assert client.get("/api/dashboard").status_code==200
    created=client.post("/api/students",json=student_payload("DE/2023/0999"))
    assert created.status_code==201
    with main.connect() as db:
        request=db.execute("SELECT id,method,path,payload,status FROM demo_change_requests WHERE method='POST' AND path='/api/students' ORDER BY id DESC LIMIT 1").fetchone()
        assert request["payload"]["matric_number"]=="DE/2023/0999"
        assert request["status"]=="Pending"
        assert db.execute("SELECT 1 FROM students WHERE matric_number='DE/2023/0999'").fetchone() is None
    assert client.post("/api/auth/logout").status_code==200
    login=client.post("/api/auth/login",json={"username":"institution.admin","password":"institution-admin-password-123"})
    assert login.status_code==200
    approved=client.post(f"/api/admin/demo-change-requests/{request['id']}/review",json={"decision":"Approved","note":"Verified in demo"})
    assert approved.status_code==200 and approved.json()["status"]=="Approved"
    with main.connect() as db:
        assert db.execute("SELECT 1 FROM students WHERE matric_number='DE/2023/0999'").fetchone() is not None
