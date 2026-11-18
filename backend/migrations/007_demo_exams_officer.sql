-- Remove the legacy identity constraint that excludes ExamsOfficer; the newer
-- user_accounts_identity_check continues to enforce valid role-to-record linkage.
ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_check;

-- The Argon2 hash represents a random password that is intentionally not distributed.
-- Demo access is issued through the server-side quick-login endpoint.
INSERT INTO user_accounts (username, password_hash, role, department_id, is_active)
SELECT 'demo.exams-officer', '$argon2id$v=19$m=65536,t=3,p=2$WcsWYv3JYUVEX9U/iKiyIQ$FRLPd4Y38x18rRqRlM3/OfJp/xcwU85TySxJ/BGe5VM', 'ExamsOfficer', department.id, TRUE
FROM departments AS department
WHERE department.name = 'Computer Engineering'
  AND NOT EXISTS (
    SELECT 1 FROM user_accounts AS existing
    WHERE existing.username = 'demo.exams-officer'
  );
