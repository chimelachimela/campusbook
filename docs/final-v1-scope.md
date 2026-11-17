# CampusBook — Final Version 1 Scope

## Product definition

CampusBook is a focused university student records, course registration, and results management system. It supports academic administrators maintaining institutional records, students registering for courses, and lecturers entering results for their assigned course offerings.

This version is an academic client/server project with limited student self-service, not a full university ERP or learning-management system.

## Product roles

### Administrator / Registrar

- Manage faculties and departments.
- Register, edit, search, and deactivate student records.
- Maintain the course catalogue and academic sessions/semesters.
- Create course offerings/sections and assign lecturers.
- Enrol students into course offerings or manage the class roster.
- Create student and lecturer accounts and assign their roles.\n- Configure course registration periods and eligible course offerings.\n- Review registrations and perform administrative overrides when necessary.
- Review submitted course results and approve/finalise them.
- Create and restore application-level backups.
- Review activity logs.

### Lecturer

- Sign in using an account created by an administrator; public self-registration is disabled.
- See only course offerings assigned to that lecturer.
- View the enrolled student roster for each offering.
- Enter or edit draft marks for students in that roster.
- Import a CSV roster of marks using a downloadable template.
- Preview validation errors before saving.
- Submit a completed roster for administrator review.
- Cannot create or delete student records, assign lecturers, manage accounts, or restore backups.

### Student

Student login, self-service transcripts, course registration, fee payments, attendance, and student messaging are not included in Version 1.

## Academic information architecture

Faculty
└── Department
    ├── Students
    └── Course catalogue
        └── Course offering (academic session + semester + section)
            ├── Assigned lecturer
            ├── Enrolled students (class roster)
            └── Student grades

A student belongs to one department. A department belongs to one faculty. A course is defined once in the catalogue; each delivery in a semester is a separate course offering. A lecturer is assigned to an offering, not hard-coded to a course forever. The same course can therefore be offered to multiple sections or cohorts and assigned to the relevant lecturer(s).

## Core workflows

### Student records

1. Administrator selects a faculty.
2. Administrator selects or creates a department within that faculty.
3. Administrator adds a student under that department.
4. Student record captures name, matriculation number, department, level, and status.
5. Email is not collected or displayed for student records in this version.

### Course and result entry

1. Administrator creates or selects an academic session and semester.
2. Administrator creates/selects a course in the course catalogue.
3. Administrator creates a course offering/section and assigns a lecturer.
4. Administrator enrols the relevant students into that offering (or imports a roster).
5. Lecturer opens **My Courses**, selects an assigned offering, and sees the class roster.
6. Lecturer enters marks in a spreadsheet-like grid or imports a CSV using the system's roster template.
7. The system validates student membership, duplicate rows, missing marks, and score bounds, then shows a preview.
8. Lecturer saves a draft and submits the completed roster for review.
9. Administrator reviews and finalises the roster. Finalised grades are locked from lecturer editing; corrections require an administrator-controlled change with an audit entry.

A grade belongs to a student's enrolment in a particular course offering. It is not an independent student-grade row with a free-text course name.

### Backup and recovery

Retain the existing application-level JSONB snapshot workflow and pre-restore safety snapshot. Explain that snapshots stored in the same Neon database are not independent disaster-recovery copies.

## Privacy and security

- Do not collect student email addresses in Version 1.
- Do not return internal email fields or unnecessary personal properties from student API responses.
- Keep student records, grades, and activity logs behind authenticated API routes.
- Use three roles: Administrator, Lecturer, and Student.\n- Student accounts are institution-provisioned; public self-registration is disabled.
- No public sign-up. Administrators create and disable staff accounts.
- Enforce permissions on the server, not only by hiding frontend buttons.
- Students may access only their own records and course registrations.\n- Lecturers may access only their assigned course offerings and rosters.
- Only administrators may manage academic structure, student records, accounts, backups, restores, and final grade approval.
- Use parameterised SQL, request validation, password hashing, secure session/token handling, restricted CORS, and non-sensitive audit messages.
- Do not claim that the system is immune to hacking. Validate the implemented controls with tests.

## Interface requirements

- Keep the current CampusBook visual identity, but make the wordmark and institution identity visible at mobile widths.
- Use readable type sizes, stronger text contrast, clear labels, and scannable table hierarchy.
- Use a mobile navigation pattern that does not permanently hide the product identity or leave users without navigation labels.
- Make all visible controls functional. Remove decorative Settings, Help, notification, or workspace controls if their workflows are not implemented.
- Students page: browse by Faculty → Department, search, filter, and view students in the selected academic context.
- Results page: organise by academic session → semester → course offering → class roster, not a flat list of individual grades.
- Provide clear loading, empty, error, and success states. Never present an API failure as a valid zero count.

## Data migration

- Preserve existing fictional demonstration records.
- Replace any real student contact email with non-routable dummy data, then stop exposing or collecting student email in the application.
- Map existing departments to faculties.
- Map existing sample results to course catalogue entries, offerings, registrations, and grade rows.\n- Provision demo student accounts without using real email addresses.
- Do not invent or alter a student's real matriculation number without confirming the institution's exact format.
- Preserve backup/restore history where migration permits and take a verified backup before schema migration.

## Explicitly out of scope

- Student accounts and student self-service portal.
- Admissions, fees, payments, scholarships, attendance, timetables, hostel management, library, LMS, messaging, and payroll.
- Multi-campus tenancy, complex academic advising, degree audits, and transcript certification.
- Production-grade disaster recovery beyond the existing demonstration backup workflow.
- Public registration or unrestricted API access.

## Definition of done

- Faculty → department → student hierarchy works end-to-end.
- Course catalogue, course offering, lecturer assignment, roster enrolment, and grade relationships are enforced by PostgreSQL constraints.
- Lecturer sees only assigned offerings; administrator has the administrative functions.
- Grades can be entered in a roster and imported from CSV with preview and validation.
- Draft, submitted, and finalised grade states work and are audited.
- No student email is collected or exposed through API responses, browser UI, logs, or backups.
- Matriculation number validation follows the working pattern `DE/YYYY/NNNN` (for example, `DE/2023/0001`: DE prefix, four-digit entry year, four-digit sequence). Exact separators should be checked against the user's physical matriculation card before enforcing the regex.
- Public API requests without a valid session are denied for student/result data and all write/restore actions.
- Mobile navigation and product identity are clear; text contrast and size are improved.
- Every visible control either works or is removed.
- Automated tests cover role permissions, roster isolation, grade validation, privacy response fields, backup/restore, and CRUD.
- Deployment and live API are verified after migration; no switch of hosting provider unless evidence shows a platform limitation that blocks the requirements.
