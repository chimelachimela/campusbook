# CampusBook — Final Version 1 Scope

## Product definition

CampusBook is a focused university student records, course registration and results management system. It supports three user groups: administrators, lecturers and students.

This is an academic client/server project, not a complete university ERP or learning-management system.

## User roles

### Administrator / Registrar
- Manage student records and departments within the configured faculty directory.
- Create academic sessions and semesters, including course registration windows.
- Maintain the course catalogue and open course offerings/sections.
- Create lecturer records and provision lecturer/student accounts.
- Assign lecturers to course offerings.
- Review student registrations and submitted grade rosters.
- Approve/publish results.
- Create/restore application snapshots and inspect the activity log.

### Lecturer
- Sign in using an account provisioned by an administrator. Public sign-up is disabled.
- See only course offerings assigned to that lecturer.
- Open the enrolled class roster.
- Enter marks in a spreadsheet-style grid or import a CSV file.
- Review imported values, save draft marks and submit a completed roster.
- Cannot manage students, accounts, course offerings or backups.

### Student
- Sign in using an institution-provisioned account.
- View only their own academic records.
- Browse course offerings available for their department and level.
- Register for and drop courses while the registration window is open.
- Review their registered courses and published results.
- Cannot see another student's private records or enter grades.

## Academic information architecture

```text
University
└── Faculty
    └── Department
        ├── Students
        └── Course catalogue
            └── Course offering (academic session + semester + section)
                ├── Assigned lecturer
                ├── Student registrations / class roster
                └── Student grades
```

A student belongs to one department; a department belongs to one faculty. A course is defined once in the catalogue. Each time it is taught in a particular session, semester and section, it becomes a course offering. Lecturers are assigned to offerings, not permanently to courses.

A grade belongs to a student's registration in a specific offering. It is not an unrelated student-name/grade row.

## Core workflows

### Student records
1. Administrator selects a faculty and department.
2. Administrator creates a student record under that department.
3. The record stores name, matriculation number, department, level and status.
4. Student email is not collected or displayed.
5. New matriculation numbers follow `DE/YYYY/NNNN`, for example `DE/2023/0001`.

### Student course registration
1. Administrator creates an academic session and semester and sets the registration window.
2. Administrator creates course offerings and assigns lecturers.
3. Student signs in and sees offerings matching their department and level.
4. Student registers or drops courses during the configured window.
5. The system rejects duplicate, closed, full or ineligible registrations.

V1 eligibility checks department and level. Prerequisites, maximum credit-unit rules and programme-specific elective groups are outside scope.

### Lecturer grade entry and approval
1. Lecturer selects an assigned course offering.
2. CampusBook loads the enrolled class roster.
3. Lecturer enters marks in the grid or imports a CSV with `matric_number,score` columns.
4. The lecturer reviews the roster, saves drafts and submits the completed set.
5. The API validates that every registered student has one score from 0 to 100.
6. Administrator reviews and publishes the submitted grades.
7. Published grades are read-only through the lecturer workflow.

V1 stores total scores from 0 to 100. It does not invent CA/exam weighting or an institutional letter-grade scale.

### Backup and recovery
- Keep the application-level JSONB snapshot and pre-restore safety snapshot.
- V2 snapshots include the academic data and account records needed to restore V1.
- Revoke active sessions during recovery.
- State clearly that snapshots stored in the same Neon database are not independent disaster-recovery copies.

## Security and privacy
- Three roles: Administrator, Lecturer and Student.
- No public sign-up; administrators provision accounts.
- Passwords are hashed using Argon2id.
- Sessions expire after 12 hours and are checked server-side.
- Every protected API operation enforces its role on the server.
- Students can access only their own records and registrations.
- Lecturers can access only their assigned offerings and rosters.
- Only administrators can manage academic structure, student records, accounts, backups, restores and grade approval.
- Student email is not collected; the legacy database column contains non-routable dummy values and is not returned by student APIs.
- Use parameterised SQL, request validation, restricted CORS and non-sensitive audit messages.
- Do not claim that any website is immune to hacking. Verify controls with tests.

## Interface requirements
- Keep CampusBook's identity visible on desktop and mobile.
- Use readable type, stronger contrast, clear labels and scannable tables.
- Students are browsed by Faculty → Department.
- Results are organised by Session → Semester → Course offering → Class roster.
- Provide loading, empty, error and success states. An API failure must never appear as a valid zero count.
- Every visible button must perform an action; remove decorative controls without a working workflow.

## Data migration
- Preserve the original student record and all fictional demonstration records.
- Replace the real student contact email with non-routable dummy data and stop collecting/returning email.
- Map existing departments to faculties.
- Map existing sample results to courses, offerings, registrations and grade rows.
- Migrate synthetic matric numbers to the DE/year/four-digit pattern without silently changing the original student's number.
- Take a verified snapshot before applying the production schema migration.

## Explicitly out of scope
- Public account creation and student self-service account registration.
- Admissions, fees, payments, scholarships, attendance, timetables, hostel management, library, LMS, messaging and payroll.
- Multi-campus tenancy, complex academic advising, degree audits and transcript certification.
- Prerequisite engines, programme-specific elective rules and credit-unit limits.
- Independent off-site disaster recovery beyond the demonstrated database snapshot flow.

## Definition of done
- Faculty → department → student hierarchy works end-to-end.
- Administrator, Lecturer and Student sign-in and server-enforced permissions work.
- Students can register/drop eligible offerings and see only their own published results.
- Lecturers see only assigned offerings and can submit validated class rosters.
- Administrators can provision accounts, configure academic offerings and approve results.
- Matriculation format and email privacy are enforced.
- Backup/restore includes V1 academic records and invalidates prior sessions.
- Mobile navigation, identity, contrast and typography are clear.
- CI covers CRUD, role boundaries, course registration, grade entry/approval and backup/restore.
- The public deployment is switched only after authentication and API tests pass.
