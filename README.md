# 🎓 Campus Recruitment System (CampusHire)

A complete web application for managing campus placements, built as a **UML Mini Project**.
It implements the design in the project's UML diagrams: Use Case, Class, Activity, Sequence,
Component, ER and Data Flow diagrams.

**Technologies:** Python 3 · Flask · SQLite · HTML · CSS (nothing else to download)

## 🔑 Super Admin login
| Username | Password |
|---|---|
| `mukhesh` | `mukhesh28` |

This is the only account that exists on first run. Everyone else **registers themselves**
(Student / Company) or is created by the admin under **Users → + Add User** (Staff or any custom role).

## ✨ Features

| Role | What they can do |
|---|---|
| **Super Admin** | Full control: all modules, applications, reports, users, roles and permissions |
| **Staff / custom roles (System User)** | Only the modules the admin allows. Admin can create new roles (e.g. *hod*) and tick their permissions |
| **Company** | Register, post / edit / delete own jobs with required skills, view students, review applicants (with skill-match %), shortlist, schedule interviews, select / reject |
| **Student** | Register, add skills and qualifications, search & filter jobs, see skill-match %, apply, track status and interview date, withdraw |
| **Everyone** | Login / Logout, Register, Forgot password, Update profile, Change password |

### New in this version
- **Own college:** if a student's college is not listed, they type it and it is added automatically
- **Skills & programming languages:** students list any skills; qualifications accept **any** type typed freely (Python, Rust, Docker, certifications...)
- **Skill-match score:** every job shows how well a student's skills match the job's required skills
- **Interview date & time:** set by the company/admin, visible to the student

### Also included
- **Any username and any password** (only empty values rejected); usernames are case-insensitive; login with email also works
- Role-based access control with an editable permission matrix; add / edit / delete / search / assign roles
- Forgot password: security question **or** email reset link
- Automatic **placement record** when an application is marked *Selected*
- Detail view for every record (a college with its students, a company with its jobs, ...)
- **Reports**: Student, College, Company, Job, Vacancy, Qualification, Placement, System User, Login Activity — search, **CSV**, **print**
- Dashboard with placement rate and charts (pure CSS, works offline)
- Passwords hashed, CSRF protection, parameterised SQL, escaped output

## 🚀 How to run (VS Code)
1. Install Python from python.org (tick **Add Python to PATH**)
2. Open this folder in VS Code → **Terminal → New Terminal**
3. `pip install flask`
4. `python app.py`
5. Open **http://127.0.0.1:5000** and login with the super admin above

To reset everything: stop the app, **delete `campus.db`**, run again.

### Sample data
On first run some sample colleges, companies, jobs and students are added so the pages are not empty
(none of them can log in). For a completely empty system set `LOAD_SAMPLE_DATA = False` in `database.py`
**before** the first run (delete `campus.db` first if it already exists).

## 📧 Email password reset (optional)
Without settings, the reset link is shown on the page instead of being emailed. To send real emails set
`SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` before running.

## 📁 Project structure
```
campus-recruitment-system/
├── app.py              # routes, access control, business logic
├── database.py         # tables (ER / Class diagram), super admin, sample data
├── requirements.txt
├── static/style.css
├── templates/          # all HTML pages
└── docs/
    ├── UML_MAPPING.md  # every UML diagram -> code, with coverage checklist
    └── uml-diagrams/   # reference diagram screenshots
```

> Reference UML diagrams in `docs/uml-diagrams/` come from freeprojectz.com (Campus Recruitment System UML) and were used as the design reference.
