-- CampusBook V1 academic structure, self-service registration, and role accounts.
-- Apply on an isolated Neon branch first. Production rollout requires tested API changes.
-- This migration is additive; legacy student/result tables remain available during transition.

CREATE TABLE IF NOT EXISTS faculties (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    code VARCHAR(16) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE departments
    ADD COLUMN IF NOT EXISTS faculty_id BIGINT REFERENCES faculties(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_departments_faculty_id ON departments(faculty_id);

CREATE TABLE IF NOT EXISTS lecturers (
    id BIGSERIAL PRIMARY KEY,
    staff_number VARCHAR(40) NOT NULL UNIQUE,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS academic_sessions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE,
    starts_on DATE,
    ends_on DATE,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_academic_sessions_one_current
    ON academic_sessions(is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS semesters (
    id BIGSERIAL PRIMARY KEY,
    academic_session_id BIGINT NOT NULL REFERENCES academic_sessions(id) ON DELETE RESTRICT,
    name VARCHAR(30) NOT NULL CHECK (name IN ('First Semester','Second Semester','Summer')),
    registration_opens_at TIMESTAMPTZ,
    registration_closes_at TIMESTAMPTZ,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (academic_session_id, name),
    CHECK (registration_opens_at IS NULL OR registration_closes_at IS NULL
        OR registration_opens_at <= registration_closes_at)
);

CREATE TABLE IF NOT EXISTS courses (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    course_code VARCHAR(20) NOT NULL,
    title VARCHAR(160) NOT NULL,
    credit_units SMALLINT NOT NULL DEFAULT 3 CHECK (credit_units BETWEEN 1 AND 10),
    level VARCHAR(10) NOT NULL CHECK (level IN ('100','200','300','400','500','600')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (department_id, course_code)
);

CREATE TABLE IF NOT EXISTS course_offerings (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    semester_id BIGINT NOT NULL REFERENCES semesters(id) ON DELETE RESTRICT,
    section VARCHAR(20) NOT NULL DEFAULT 'A',
    lecturer_id BIGINT REFERENCES lecturers(id) ON DELETE RESTRICT,
    capacity INTEGER CHECK (capacity IS NULL OR capacity > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Draft','Open','Closed','Completed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (course_id, semester_id, section)
);

CREATE INDEX IF NOT EXISTS idx_course_offerings_semester ON course_offerings(semester_id);
CREATE INDEX IF NOT EXISTS idx_course_offerings_lecturer ON course_offerings(lecturer_id);

CREATE TABLE IF NOT EXISTS course_registrations (
    id BIGSERIAL PRIMARY KEY,
    course_offering_id BIGINT NOT NULL REFERENCES course_offerings(id) ON DELETE RESTRICT,
    student_id BIGINT NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'Registered'
        CHECK (status IN ('Registered','Dropped','Cancelled')),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dropped_at TIMESTAMPTZ,
    UNIQUE (course_offering_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_course_registrations_student ON course_registrations(student_id);
CREATE INDEX IF NOT EXISTS idx_course_registrations_offering ON course_registrations(course_offering_id);

CREATE TABLE IF NOT EXISTS user_accounts (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('Administrator','Lecturer','Student')),
    student_id BIGINT UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    lecturer_id BIGINT UNIQUE REFERENCES lecturers(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (role = 'Student' AND student_id IS NOT NULL AND lecturer_id IS NULL) OR
        (role = 'Lecturer' AND lecturer_id IS NOT NULL AND student_id IS NULL) OR
        (role = 'Administrator' AND student_id IS NULL AND lecturer_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS course_grades (
    id BIGSERIAL PRIMARY KEY,
    registration_id BIGINT NOT NULL UNIQUE
        REFERENCES course_registrations(id) ON DELETE RESTRICT,
    score NUMERIC(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    letter_grade VARCHAR(2) CHECK (letter_grade IS NULL OR letter_grade IN ('A','B','C','D','E','F')),
    status VARCHAR(20) NOT NULL DEFAULT 'Draft'
        CHECK (status IN ('Draft','Submitted','Approved','Published')),
    entered_by BIGINT REFERENCES user_accounts(id) ON DELETE SET NULL,
    submitted_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_expiry ON user_sessions(user_id, expires_at);

-- Keep the application role least-privileged: no schema ownership or DDL.
GRANT SELECT, INSERT, UPDATE, DELETE ON
    faculties, departments, lecturers, academic_sessions, semesters, courses,
    course_offerings, course_registrations, course_grades, user_accounts, user_sessions
TO campusbook_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO campusbook_app;
