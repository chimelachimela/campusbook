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
