-- Demo changes are staged in the isolated demo branch and reviewed by institution admins.
CREATE TABLE IF NOT EXISTS demo_change_requests (
 id BIGSERIAL PRIMARY KEY,
 method VARCHAR(10) NOT NULL,
 path TEXT NOT NULL,
 payload JSONB NOT NULL DEFAULT '{}'::jsonb,
 status VARCHAR(20) NOT NULL DEFAULT 'Pending',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 reviewed_at TIMESTAMPTZ,
 reviewed_by BIGINT REFERENCES user_accounts(id) ON DELETE SET NULL,
 review_note TEXT
);
CREATE INDEX IF NOT EXISTS demo_change_requests_status_created_idx ON demo_change_requests(status,created_at DESC);
GRANT SELECT,INSERT,UPDATE ON demo_change_requests TO campusbook_app;
GRANT USAGE,SELECT ON SEQUENCE demo_change_requests_id_seq TO campusbook_app;