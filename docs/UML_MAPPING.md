# How the UML diagrams map to this project

## Use Case Diagram
| Actor | Use case | Where |
|---|---|---|
| Super Admin | Manage Users and Full Application | `/admin/users`, `/admin/permissions` |
| Super Admin / System User | Manage Students / College / Company / Placement / Qualification | `/m/students`, `/m/colleges`, `/m/companies`, `/m/placements`, `/m/qualifications` |
| Company | Post Jobs, View Applications, View Students | `/m/jobs`, `/applications`, `/m/students` |
| Student | Search Jobs, Apply for Jobs, View Job Status | `/jobs`, `/jobs/<id>/apply`, `/applications` |
| All | Login and Logout, Update My Profile, Change Account Password | `/`, `/logout`, `/profile`, `/password` |

## Class Diagram
| Class | Table | Methods → where |
|---|---|---|
| Role | `roles` | addRole, editRole, deleteRole, searchRole → Roles & Permissions page; assignRole → Users page |
| Permission | `permissions` | add/edit/delete/search permission → permission matrix |
| User | `users` (incl. date of birth) | add/edit/delete/search → Users page, Register, Profile |
| Student, College, Company, Job, Vacancy, Placement, Qualification | same names | add / edit / delete / search / view → `/m/<module>` |

## Activity Diagram
- Login: Login ID & Password → Check → *Invalid Login/Password → retry* → Login successful → Set user level & permissions → Access functions by permission → Logout (`login()`, `access()`, `need()`).
- Admin can search, view description, add, update and delete College; edit/add/update Job; search and generate report of Vacancy, Student, Company → generic CRUD + detail view + `/reports`.
- "All objects (College, Job, Company) are interlinked" → foreign keys + detail pages showing related records.

## Sequence Diagram
Login Page → Forgot Password → Verification (security question & answer) → **Send email to user to reset password** → Database → Authenticate Page → session created → Logout destroys the session.
Implemented in `/forgot`, `/forgot/verify`, `/forgot/email`, `/reset/<token>`, `login()`, `logout()`.
The second sequence diagram (Add/Edit, Save/Update, List/Delete for Student, College, Company, Job, Placement) = the CRUD pages.

## Data Flow Diagrams
- Level 0: Student, College, Company, Job, Placement, System User, Login management.
- Level 1: Generate Student / Company / Job / College / System User reports and **Check User Login Details** → `/reports/*` including *Login Activity Report*.
- Level 2: Admin → Login → Check credentials → Check roles of access → Manage Modules (Student, College, Qualification, Company, Job, Placement, Report) + Manage System Admins, Roles of User, User Permission, Forgot Password / Send Email to User.

## ER Diagram
Login / User, Roles, Permission, Student, College, Company, Job with the relationships *Has* and *Manage* → `database.py` (`SCHEMA`) with primary and foreign keys.

## Component Diagram
Student, College, Company, Job, Placement components (Data Access) + Security (Encryption = password hashing, Access Control = roles & permissions) + Persistence + Database connector → modules in `app.py`, `generate_password_hash`, `access()`, SQLite in `database.py`.

## Extra features beyond the diagrams
- Students can add their own college; free-text skills and qualification types
- Skill-match score between a student and a job's required skills
- Interview date and time on an application

## Coverage checklist
- [x] All 4 actors (Super Admin, System User, Company, Student)
- [x] All 10 classes with their methods (add / edit / delete / search / save / assign)
- [x] Login activity incl. invalid login and permission check
- [x] Forgot password, security question, email reset
- [x] Reports for Student, College, Company, Job, Vacancy, Qualification, Placement, System User, Login details
- [x] Roles, permissions, manage system admins
- [x] Update profile, change password, logout / destroy session
