-- CampusBook academic session date ranges and semester calendars.
-- First and second semester are generated from the session dates. Summer remains
-- optional because institutions do not all operate a summer semester.
ALTER TABLE semesters ADD COLUMN IF NOT EXISTS starts_on DATE;
ALTER TABLE semesters ADD COLUMN IF NOT EXISTS ends_on DATE;
ALTER TABLE semesters ADD CONSTRAINT semesters_date_range_check
    CHECK (starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on);
