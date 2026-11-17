-- CampusBook PostgreSQL schema for Neon.
-- Apply this file while connected as campusbook_owner, never as campusbook_app.

CREATE TABLE IF NOT EXISTS departments (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS students (
    id BIGSERIAL PRIMARY KEY,
    matric_number VARCHAR(40) NOT NULL UNIQUE,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    email VARCHAR(160) NOT NULL,
    department VARCHAR(100) NOT NULL,
    level VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
    id BIGSERIAL PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_code VARCHAR(20) NOT NULL,
    course_title VARCHAR(120) NOT NULL,
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 100),
    semester VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id BIGSERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- Logical snapshots keep the existing in-app backup/restore workflow available.
-- They are in the same database, not independent disaster-recovery copies.
CREATE TABLE IF NOT EXISTS backup_snapshots (
    id BIGSERIAL PRIMARY KEY,
    filename VARCHAR(80) NOT NULL UNIQUE,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

GRANT USAGE ON SCHEMA public TO campusbook_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE departments, students, results, activity_logs, backup_snapshots TO campusbook_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO campusbook_app;
ALTER DEFAULT PRIVILEGES FOR ROLE campusbook_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO campusbook_app;
ALTER DEFAULT PRIVILEGES FOR ROLE campusbook_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO campusbook_app;

INSERT INTO departments (name, code) VALUES
    ('Computer Engineering', 'CPE'),
    ('Computer Science', 'CSC'),
    ('Electrical Engineering', 'EEE'),
    ('Accountancy', 'ACC')
ON CONFLICT DO NOTHING;
