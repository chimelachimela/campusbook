# CampusBook test plan and acceptance checks

## Automated tests

The repository includes pytest tests for:

| Test | Expected result |
| --- | --- |
| API health | Returns HTTP 200 and service status |
| Student creation | Persists a student and returns the new record |
| Backup and recovery | A deleted student reappears after restoring a valid snapshot |
| Result management | A valid course result can be recorded, listed, and deleted |
| Department management | A new department is stored and appears in the directory |
| Restore path validation | An unsafe or missing backup path is rejected |

Run from the `backend/` directory after installing `requirements.txt`:

```bash
pytest -v
```

GitHub Actions runs this suite on pushes to the project branch and pull requests targeting `main`.

## Frontend build check

From `frontend/`:

```bash
npm install
npm run build
```

The build check is also part of the GitHub Actions workflow.

## Manual acceptance test: backup and recovery

Use synthetic student details only.

1. Start the FastAPI server and React development server.
2. Add a test student through the Students page.
3. Confirm the new record appears in the list and dashboard count.
4. Open Backup & Recovery and create a backup.
5. Delete the test student.
6. Confirm the record is no longer listed.
7. Restore the snapshot created in step 4.
8. Confirm the student record has returned.
9. Confirm a pre-restore safety copy exists in the backend backup directory.
10. Confirm the activity log records the create, delete, backup, and restore operations.

**Acceptance condition:** the student record must actually return from the database snapshot. A successful restore response alone is not sufficient evidence.

## Manual checks for other modules

- Create a department and confirm it appears in the department directory.
- Add a student using the new department and confirm the department student count updates.
- Record a course result for a student and confirm the score and letter grade display.
- Try a score below 0 or above 100 using the API docs; the API should reject it.
- Edit a student and confirm the changes persist after refreshing the page.
- Delete a student and confirm their associated results are removed by the foreign-key cascade.

## Evidence to capture for the academic demonstration

Capture screenshots of:
- Dashboard with student and department summary cards.
- Student directory with at least two synthetic student records.
- Department directory and student counts.
- Results table with one or more course results.
- Backup history showing a created snapshot.
- Student record before deletion, after deletion, and after restoration.
- Activity log showing the backup/recovery sequence.
- GitHub Actions passing checks.

Do not use actual student personal data in the public repository or screenshots.
