-- Pending admission applications. Applicants do not become student accounts until
-- an administrator verifies admission and assigns an official matriculation number.
CREATE TABLE IF NOT EXISTS admission_applications (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(160) NOT NULL,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    application_reference VARCHAR(80),
    status VARCHAR(20) NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending','Approved','Rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by BIGINT REFERENCES user_accounts(id) ON DELETE SET NULL,
    student_id BIGINT REFERENCES students(id) ON DELETE SET NULL,
    review_note TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_admission_applications_pending_email
    ON admission_applications (LOWER(email)) WHERE status = 'Pending';
CREATE INDEX IF NOT EXISTS idx_admission_applications_status_created
    ON admission_applications (status, created_at DESC);
GRANT SELECT, INSERT, UPDATE, DELETE ON admission_applications TO campusbook_app;
GRANT USAGE, SELECT ON SEQUENCE admission_applications_id_seq TO campusbook_app;
