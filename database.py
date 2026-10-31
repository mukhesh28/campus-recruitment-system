"""Database layer: schema + super admin + sample data (matches the ER / Class diagrams)."""
import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campus.db")

# Modules that the "staff" (System User) role can be given permission for
PERM_MODULES = ["students", "colleges", "companies", "jobs", "vacancies",
                "placements", "qualifications", "applications", "reports"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, description TEXT);
CREATE TABLE IF NOT EXISTS permissions (
    role TEXT NOT NULL, module TEXT NOT NULL, PRIMARY KEY (role, module));
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password TEXT NOT NULL, role TEXT NOT NULL, full_name TEXT, email TEXT,
    mobile TEXT, address TEXT, sec_q TEXT, sec_a TEXT, created_at TEXT, dob TEXT);
CREATE TABLE IF NOT EXISTS password_resets (
    token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT, used INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS login_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, success INTEGER, at TEXT);
CREATE TABLE IF NOT EXISTS colleges (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    description TEXT, address TEXT);
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL, type TEXT, description TEXT, address TEXT);
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    college_id INTEGER REFERENCES colleges(id) ON DELETE SET NULL,
    name TEXT NOT NULL, email TEXT, mobile TEXT, course TEXT, address TEXT, skills TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL, type TEXT, salary TEXT, openings INTEGER DEFAULT 1,
    location TEXT, status TEXT DEFAULT 'Open', description TEXT, skills TEXT);
CREATE TABLE IF NOT EXISTS vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    type TEXT, openings INTEGER, description TEXT);
CREATE TABLE IF NOT EXISTS qualifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    type TEXT, percentage REAL, description TEXT);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'Applied', applied_at TEXT, interview_at TEXT,
    UNIQUE (student_id, job_id));
CREATE TABLE IF NOT EXISTS placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    college_id INTEGER REFERENCES colleges(id) ON DELETE SET NULL,
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    qualification TEXT, type TEXT, description TEXT, placed_on TEXT,
    source TEXT DEFAULT 'manual');
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def add_user(conn, username, password, role, full_name="", email="",
             mobile="", address="", sec_q="", sec_a="", dob=""):
    cur = conn.execute(
        "INSERT INTO users (username,password,role,full_name,email,mobile,address,sec_q,sec_a,created_at,dob)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (username, generate_password_hash(password), role, full_name, email, mobile, address,
         sec_q, generate_password_hash(sec_a.strip().lower()) if sec_a else "", now(), dob))
    return cur.lastrowid


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()


# Set to False if you want a completely empty system (only the super admin account).
LOAD_SAMPLE_DATA = True

SUPER_ADMIN_USERNAME = "mukhesh"
SUPER_ADMIN_PASSWORD = "mukhesh28"


def seed(conn):
    """First run: creates the roles, the super admin account and (optionally) sample records."""
    for name, desc in [("admin", "Super Admin - full control of the system"),
                       ("staff", "System User - works with modules the admin allows"),
                       ("company", "Company - posts jobs and reviews applicants"),
                       ("student", "Student - searches jobs and applies")]:
        conn.execute("INSERT INTO roles (name, description) VALUES (?,?)", (name, desc))
    for m in PERM_MODULES:
        conn.execute("INSERT INTO permissions (role, module) VALUES ('staff', ?)", (m,))
    add_user(conn, SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD, "admin", "Mukhesh")
    if LOAD_SAMPLE_DATA:
        load_sample(conn)


def load_sample(conn):
    """Sample colleges / companies / jobs / students (none of them can log in)."""
    for c in [("ABC Institute of Technology", "Autonomous engineering college", "Guntur, Andhra Pradesh"),
              ("Sunrise College of Engineering", "Engineering and technology", "Vijayawada, Andhra Pradesh"),
              ("National Institute of Management", "MBA and management studies", "Hyderabad, Telangana")]:
        conn.execute("INSERT INTO colleges (name,description,address) VALUES (?,?,?)", c)
    for c in [("TechNova Solutions", "IT Services", "Software products and services", "Hyderabad"),
              ("Infosys", "IT Services", "Global consulting and IT", "Bengaluru"),
              ("Zoho", "Product", "Cloud software products", "Chennai"),
              ("Wipro", "IT Services", "Technology services", "Pune")]:
        conn.execute("INSERT INTO companies (name,type,description,address) VALUES (?,?,?,?)", c)
    for j in [(1, "Software Engineer", "Full Time", "6 LPA", 10, "Hyderabad", "Open", "Build and maintain web applications.", "Python, SQL, Flask"),
              (1, "Data Analyst", "Full Time", "5 LPA", 5, "Hyderabad", "Open", "Analyse data and build dashboards.", "SQL, Excel, Python"),
              (2, "System Engineer", "Full Time", "4.5 LPA", 20, "Bengaluru", "Open", "Work on enterprise systems.", "Java, SQL"),
              (3, "Web Developer Intern", "Internship", "20K / month", 6, "Chennai", "Open", "Learn and build with our product team.", "HTML, CSS, JavaScript"),
              (4, "QA Tester", "Full Time", "4 LPA", 8, "Pune", "Closed", "Test applications and report bugs.", "Testing, SQL")]:
        conn.execute("INSERT INTO jobs (company_id,name,type,salary,openings,location,status,description,skills) VALUES (?,?,?,?,?,?,?,?,?)", j)
    conn.execute("INSERT INTO vacancies (job_id,type,openings,description) VALUES (1,'Fresher',6,'Fresh graduates, 2026 batch')")
    conn.execute("INSERT INTO vacancies (job_id,type,openings,description) VALUES (1,'Experienced',4,'1-2 years experience')")
    for s_ in [(1, "Kiran Teja", "kiran@mail.com", "9876500000", "B.Tech CSE", "Guntur", "Python, Java, SQL"),
               (1, "Ravi Kumar", "ravi@mail.com", "9876500001", "B.Tech CSE", "Guntur", "Python, Flask, SQL"),
               (2, "Anjali Reddy", "anjali@mail.com", "9876500002", "B.Tech IT", "Vijayawada", "Java, HTML, CSS, JavaScript"),
               (2, "Suresh Babu", "suresh@mail.com", "9876500003", "B.Tech ECE", "Vijayawada", "C, Embedded"),
               (3, "Priya Sharma", "priya@mail.com", "9876500004", "MBA", "Hyderabad", "Excel, SQL")]:
        conn.execute("INSERT INTO students (college_id,name,email,mobile,course,address,skills) VALUES (?,?,?,?,?,?,?)", s_)
    for sid, t, p, d in [(1, "12th", 91.5, "Intermediate - MPC"), (1, "B.Tech", 8.4, "CSE - CGPA 8.4"),
                         (1, "Programming Language", None, "Python (intermediate), Java (basic)"),
                         (2, "B.Tech", 7.9, "CSE - CGPA 7.9"), (3, "B.Tech", 8.8, "IT - CGPA 8.8"),
                         (4, "B.Tech", 7.2, "ECE - CGPA 7.2"), (5, "MBA", 8.1, "Finance - CGPA 8.1")]:
        conn.execute("INSERT INTO qualifications (student_id,type,percentage,description) VALUES (?,?,?,?)", (sid, t, p, d))
    d1 = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
    d2 = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 10:30")
    for sid, jid, st, iv in [(2, 1, "Selected", None), (3, 1, "Shortlisted", None), (3, 2, "Applied", None),
                             (4, 3, "Interview Scheduled", d2), (5, 2, "Rejected", None), (1, 4, "Applied", None)]:
        conn.execute("INSERT INTO applications (student_id,job_id,status,applied_at,interview_at) VALUES (?,?,?,?,?)", (sid, jid, st, d1, iv))
    conn.execute("INSERT INTO placements (student_id,college_id,company_id,job_id,qualification,type,description,placed_on,source)"
                 " VALUES (2,1,1,1,'B.Tech','Full Time','Selected for Software Engineer at TechNova Solutions',?, 'auto')",
                 (datetime.now().strftime("%Y-%m-%d"),))
