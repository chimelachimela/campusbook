from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_student_crud_and_backup_restore(tmp_path, monkeypatch):
    # Isolate the test database and backup directory from a developer's data.
    from app import main
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "data" / "test.db")
    main.initialize_database()

    payload = {
        "matric_number": "RSU/2024/CPE/001",
        "first_name": "Ada",
        "last_name": "Okoro",
        "email": "ada@example.test",
        "department": "Computer Engineering",
        "level": "300",
        "status": "Active",
    }
    created = client.post("/api/students", json=payload)
    assert created.status_code == 201
    student_id = created.json()["id"]

    backup = client.post("/api/backups")
    assert backup.status_code == 200
    filename = backup.json()["filename"]

    deleted = client.delete(f"/api/students/{student_id}")
    assert deleted.status_code == 200
    assert len(client.get("/api/students").json()) == 0

    restored = client.post(f"/api/backups/{filename}/restore")
    assert restored.status_code == 200
    students = client.get("/api/students").json()
    assert len(students) == 1
    assert students[0]["matric_number"] == payload["matric_number"]


def test_results_and_department_management(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "data" / "test.db")
    main.initialize_database()

    student = client.post("/api/students", json={
        "matric_number": "RSU/2024/CPE/002",
        "first_name": "Tomi",
        "last_name": "Adele",
        "email": "tomi@example.test",
        "department": "Computer Engineering",
        "level": "300",
    })
    assert student.status_code == 201

    result = client.post("/api/results", json={
        "student_id": student.json()["id"],
        "course_code": "CPE 301",
        "course_title": "Data Communications",
        "score": 78.5,
        "semester": "First Semester 2026/2027",
    })
    assert result.status_code == 201
    assert result.json()["score"] == 78.5
    assert len(client.get("/api/results").json()) == 1

    deleted = client.delete(f"/api/results/{result.json()['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/results").json() == []

    department = client.post("/api/departments", json={"name": "Civil Engineering", "code": "CVE"})
    assert department.status_code == 201
    assert any(d["code"] == "CVE" for d in client.get("/api/departments").json())


def test_restore_rejects_path_traversal(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "data" / "test.db")
    main.initialize_database()

    response = client.post("/api/backups/..%2Foutside.db/restore")
    assert response.status_code in (400, 404)
