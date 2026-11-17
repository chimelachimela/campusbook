# CampusBook test plan and acceptance checks

## Automated PostgreSQL integration tests

The pytest suite runs against a disposable PostgreSQL database and covers:

| Test | Expected result |
| --- | --- |
| API health | Confirms API and PostgreSQL connectivity |
| Student CRUD | Creates, searches, updates, and deletes a student |
| Duplicate matriculation number | Returns HTTP 409 |
| Backup and recovery | Restores a deleted student and its course results |
| Restore safety | Creates a pre-restore safety snapshot |
| Department management | Creates a department and lists student counts |
| Result management | Records and lists results; student deletion cascades |
| Filename validation | Rejects invalid and missing backup names |
| Activity log | Records important system actions |

Run against a disposable PostgreSQL database:

```bash
cd backend
export DATABASE_URL="postgresql://..."
export CAMPUSBOOK_AUTO_MIGRATE=true
pytest -v
```

GitHub Actions provisions PostgreSQL 17 for every CI run. Do not point the test suite at a database containing data you need: tests truncate the test tables.

## Frontend production build

From `frontend/`:

```bash
npm install
npm run build
```

## Manual acceptance test: backup and recovery

Use synthetic student details only.

1. Open the deployed CampusBook frontend.
2. Add a test student and record a course result for that student.
3. Create a backup in Backup & Recovery.
4. Delete the test student.
5. Confirm the student and associated result are gone.
6. Restore the snapshot created in step 3.
7. Confirm the student and result have returned.
8. Confirm a pre-restore safety snapshot appears in backup history.
9. Confirm the activity log records the create, delete, backup, and restore operations.

**Acceptance condition:** the student and associated result must actually return from the stored snapshot. A successful HTTP response alone is not sufficient evidence.

## Evidence for the academic demonstration

Capture screenshots of:
- Dashboard with student and department summary cards.
- Student directory with synthetic records.
- Department directory and student counts.
- Results table with a course result.
- Backup history showing a created snapshot.
- Student and result before deletion, after deletion, and after restoration.
- Activity log showing the recovery sequence.
- Passing GitHub Actions checks.

## Important limitations

Logical JSONB snapshots live inside the same Neon database as the application data. They demonstrate application-level recovery but are not independent disaster-recovery backups. Do not use real student personal data in this public academic demonstration.
