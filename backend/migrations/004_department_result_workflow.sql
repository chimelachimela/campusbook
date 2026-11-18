-- Department examination officers and departmental result submission workflow.
ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS department_id BIGINT REFERENCES departments(id) ON DELETE RESTRICT;
ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_role_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_role_check
    CHECK (role IN ('Administrator','Lecturer','Student','ExamsOfficer'));
ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_check;
ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_identity_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_identity_check CHECK (
    (role='Administrator' AND student_id IS NULL AND lecturer_id IS NULL AND department_id IS NULL) OR
    (role='Student' AND student_id IS NOT NULL AND lecturer_id IS NULL AND department_id IS NULL) OR
    (role='Lecturer' AND lecturer_id IS NOT NULL AND student_id IS NULL AND department_id IS NULL) OR
    (role='ExamsOfficer' AND department_id IS NOT NULL AND student_id IS NULL AND lecturer_id IS NULL)
);
CREATE TABLE IF NOT EXISTS department_result_submissions (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    semester_id BIGINT NOT NULL REFERENCES semesters(id) ON DELETE RESTRICT,
    level VARCHAR(10) NOT NULL CHECK (level IN ('100','200','300','400','500','600')),
    status VARCHAR(20) NOT NULL DEFAULT 'Submitted' CHECK (status IN ('Submitted','Approved','Rejected')),
    submitted_by BIGINT NOT NULL REFERENCES user_accounts(id) ON DELETE RESTRICT,
    reviewed_by BIGINT REFERENCES user_accounts(id) ON DELETE SET NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    UNIQUE(department_id,semester_id,level)
);
CREATE TABLE IF NOT EXISTS department_result_submission_grades (
    submission_id BIGINT NOT NULL REFERENCES department_result_submissions(id) ON DELETE CASCADE,
    grade_id BIGINT NOT NULL UNIQUE REFERENCES course_grades(id) ON DELETE RESTRICT,
    PRIMARY KEY(submission_id,grade_id)
);
