-- CampusBook academic session date ranges and semester calendars.
-- First and second semester are generated from session dates. Summer remains
-- optional because institutions do not all operate a summer semester.
ALTER TABLE semesters ADD COLUMN IF NOT EXISTS starts_on DATE;
ALTER TABLE semesters ADD COLUMN IF NOT EXISTS ends_on DATE;
