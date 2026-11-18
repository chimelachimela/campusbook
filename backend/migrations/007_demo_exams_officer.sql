-- Provision the demo examination officer in both the primary auth database
-- and the isolated demo database. The demo account is scoped to Computer Engineering.
-- Its password hash is copied from the existing demo student account because quick
-- demo access uses the server-issued demo session, not password authentication.
INSERT INTO user_accounts (username, password_hash, role, department_id, is_active)
SELECT 'demo.exams-officer', student.password_hash, 'ExamsOfficer', department.id, TRUE
FROM user_accounts AS student
CROSS JOIN departments AS department
WHERE student.username = 'demo.student'
  AND department.name = 'Computer Engineering'
  AND NOT EXISTS (
    SELECT 1 FROM user_accounts AS existing
    WHERE existing.username = 'demo.exams-officer'
  );
