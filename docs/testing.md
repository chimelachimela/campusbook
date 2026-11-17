# CampusBook test plan and acceptance checks

## Automated PostgreSQL integration tests

The pytest suite runs against a disposable PostgreSQL 17 database. It applies all migrations and resets the test tables before each test.

| Test | Expected result |
|---|---|
| API health | Confirms API and PostgreSQL connectivity |
| Authentication | Bootstrap, login, session lookup and invalid credentials |
| Role enforcement | Unauthenticated requests return 401; disallowed roles return 403 |
| Student CRUD | Creates, searches, updates and deletes students |
| Matriculation validation | Rejects values outside DE/YYYY/NNNN |
| Email privacy | Student API responses do not contain an email field |
| Faculty/department | Students are associated with a department and faculty |
| Course setup | Creates lecturer, course, session, semester and offering |
| Student registration | Student registers for an eligible offering |
| Lecturer roster | Lecturer sees only the assigned course roster |
| Grade workflow | Lecturer saves and submits a complete roster; administrator approves it |
| Student result privacy | Student sees their own published result |
| Backup/recovery | Restores academic records and results from a V2 snapshot |
| Restore safety | Creates a pre-restore safety snapshot and revokes previous sessions |
| Activity log | Records important actions |

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

## Manual acceptance test: academic workflow

Use fictional student and lecturer details only.

1. Sign in as Administrator.
2. Confirm the Faculty → Department hierarchy.
3. Create a student using a DE/YYYY/NNNN matriculation number.
4. Create an academic session and semester.
5. Add a course to the department's course catalogue.
6. Create a lecturer record and provision their account.
7. Open a course offering and assign the lecturer.
8. Provision a student account.
9. Sign in as the student and register for the eligible offering.
10. Sign in as the lecturer and open the assigned class roster.
11. Enter marks or import a CSV with `matric_number,score` columns.
12. Review the roster, save draft grades and submit it.
13. Sign in as Administrator and approve/publish the submitted grades.
14. Sign in as the student and confirm only their published results are visible.

## Manual acceptance test: backup and recovery

1. Sign in as Administrator.
2. Create a backup before making a test change.
3. Delete a separate synthetic student with no active course registrations.
4. Confirm the student is absent.
5. Restore the snapshot.
6. Confirm the student and associated records return.
7. Confirm a pre-restore safety snapshot appears in backup history.
8. Confirm the activity log records the recovery sequence.
9. Sign in again because recovery revokes pre-restore sessions.

**Acceptance condition:** records must actually return from the stored snapshot. A successful HTTP response alone is not sufficient evidence.

## Evidence for the academic demonstration

Capture screenshots of:
- Administrator dashboard.
- Student directory filtered by faculty and department.
- Academic setup: session, semester, course, lecturer and offering.
- Student course registration.
- Lecturer class roster and CSV import/grade grid.
- Administrator grade-submission review and approval.
- Student published results.
- Backup history and recovery evidence.
- Activity log.
- Passing GitHub Actions checks.

## Important limitations

Logical JSONB snapshots live inside the same Neon database as the application data. They demonstrate application-level recovery but are not independent disaster-recovery backups. Do not use real student personal data in this public academic demonstration.
