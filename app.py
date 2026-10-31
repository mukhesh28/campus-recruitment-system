"""
Campus Recruitment System  -  UML Mini Project (Flask + SQLite)
Roles: Admin (Super Admin) | Staff (System User) | Company | Student
"""
import csv
import io
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

import database as dbm
from database import PERM_MODULES, add_user, get_db

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-real-use"
dbm.init_db()

SEC_QUESTIONS = ["What is your pet's name?", "What is your mother's maiden name?",
                 "What was the name of your first school?", "What is your favourite colour?",
                 "In which city were you born?"]
APP_STATUS = ["Applied", "Shortlisted", "Interview Scheduled", "Selected", "Rejected"]
FULL = {"r", "c", "u", "d"}

# ---------------------------------------------------------------- module config
# Each module = a class from the Class Diagram. fields = (name, label, kind[, options])
MODULES = {
    "students": dict(
        title="Students", icon="🎓", hide=["address"],
        optional=["email", "mobile", "course", "college_id", "skills"],
        fields=[("name", "Full Name", "text"), ("email", "Email", "email"),
                ("mobile", "Mobile", "text"), ("course", "Course / Branch", "text"),
                ("skills", "Skills (comma separated, e.g. Python, Java, SQL)", "text"),
                ("college_id", "College", "select:colleges"), ("address", "Address", "textarea")]),
    "colleges": dict(
        title="Colleges", icon="🏫", hide=[], optional=[],
        fields=[("name", "College Name", "text"), ("description", "Description", "textarea"),
                ("address", "Address", "textarea")]),
    "companies": dict(
        title="Companies", icon="🏢", hide=["description"], optional=["type"],
        fields=[("name", "Company Name", "text"),
                ("type", "Company Type", "choice", ["IT Services", "Product", "Core", "Finance", "Startup", "Other"]),
                ("description", "Description", "textarea"), ("address", "Address", "textarea")]),
    "jobs": dict(
        title="Jobs", icon="💼", hide=["description"], optional=["location", "salary", "skills"],
        fields=[("name", "Job Title", "text"),
                ("type", "Job Type", "choice", ["Full Time", "Internship", "Part Time", "Contract"]),
                ("salary", "Salary / Stipend", "text"), ("openings", "Openings", "number"),
                ("location", "Location", "text"), ("skills", "Required Skills (comma separated)", "text"),
                ("status", "Status", "choice", ["Open", "Closed"]),
                ("company_id", "Company", "select:companies"), ("description", "Description", "textarea")]),
    "vacancies": dict(
        title="Vacancies", icon="📌", hide=[], optional=[],
        fields=[("type", "Vacancy Type", "choice", ["Fresher", "Experienced", "Walk-in"]),
                ("job_id", "Job", "select:jobs"), ("openings", "Openings", "number"),
                ("description", "Description", "textarea")]),
    "placements": dict(
        title="Placements", icon="🏆", hide=["description"],
        optional=["college_id", "job_id", "qualification"],
        defaults=lambda: {"placed_on": datetime.now().strftime("%Y-%m-%d"), "source": "manual"},
        fields=[("student_id", "Student", "select:students"), ("company_id", "Company", "select:companies"),
                ("job_id", "Job", "select:jobs"), ("college_id", "College", "select:colleges"),
                ("qualification", "Qualification", "text"),
                ("type", "Placement Type", "choice", ["Full Time", "Internship", "Part Time", "Contract"]),
                ("description", "Description", "textarea")]),
    "qualifications": dict(
        title="Qualifications", icon="📜", hide=[], optional=["percentage"],
        fields=[("student_id", "Student", "select:students"),
                ("type", "Qualification / Skill (pick or type your own)", "suggest",
                 ["10th", "12th", "Diploma", "B.Tech", "B.Sc", "B.Com", "M.Tech", "MBA", "MCA", "Programming Language",
                  "Python", "Java", "C", "C++", "JavaScript", "SQL", "Certification", "Course", "Internship", "Project", "Other"]),
                ("percentage", "Percentage / CGPA (leave empty for skills)", "number"),
                ("description", "Institute / Branch / Details", "textarea")]),
}
STATIC_ACCESS = {"company": {"jobs": FULL, "students": {"r"}, "placements": {"r"}},
                 "student": {"qualifications": FULL}}


# ---------------------------------------------------------------- request hooks
@app.before_request
def load_user():
    g.user, g.perms = None, set()
    uid = session.get("uid")
    if uid:
        conn = get_db()
        g.user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if g.user and g.user["role"] not in ("admin", "company", "student"):
            g.perms = {r["module"] for r in conn.execute("SELECT module FROM permissions WHERE role=?", (g.user["role"],))}
        conn.close()
        if not g.user:
            session.clear()
    if request.method == "POST":  # CSRF protection
        if not session.get("csrf") or session["csrf"] != request.form.get("csrf"):
            abort(400)


def csrf_field():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return Markup('<input type="hidden" name="csrf" value="%s">' % session["csrf"])


def access(module):
    role = g.user["role"]
    if role == "admin":
        return FULL
    if role in STATIC_ACCESS:
        return STATIC_ACCESS[role].get(module, set())
    return FULL if module in g.perms else set()   # staff-type roles (staff, or roles created by admin)


def need(module, action):
    if action not in access(module):
        abort(403)


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not g.user:
            flash("Please login to continue.", "warning")
            return redirect("/")
        return f(*a, **k)
    return wrapper


def roles_required(*roles):
    def deco(f):
        @wraps(f)
        @login_required
        def wrapper(*a, **k):
            if g.user["role"] not in roles:
                abort(403)
            return f(*a, **k)
        return wrapper
    return deco


def build_nav():
    role, nav = g.user["role"], [("Dashboard", "/dashboard", "🏠")]
    if role == "company":
        nav += [("My Jobs", "/m/jobs", "💼"), ("Applicants", "/applications", "📨"),
                ("Students", "/m/students", "🎓"), ("Placements", "/m/placements", "🏆")]
    elif role == "student":
        nav += [("Browse Jobs", "/jobs", "🔎"), ("My Applications", "/applications", "📨"),
                ("My Qualifications", "/m/qualifications", "📜")]
    else:  # admin and staff-type roles
        for m in ["students", "colleges", "companies", "jobs", "vacancies", "placements", "qualifications"]:
            if access(m):
                nav.append((MODULES[m]["title"], "/m/" + m, MODULES[m]["icon"]))
        if "applications" in g.perms or role == "admin":
            nav.append(("Applications", "/applications", "📨"))
        if "reports" in g.perms or role == "admin":
            nav.append(("Reports", "/reports", "📊"))
        if role == "admin":
            nav += [("Users", "/admin/users", "👥"), ("Roles & Permissions", "/admin/permissions", "🔐")]
    nav += [("My Profile", "/profile", "👤"), ("Change Password", "/password", "🔑"), ("Logout", "/logout", "🚪")]
    return nav


@app.context_processor
def inject():
    return dict(user=g.user, csrf_field=csrf_field, nav=build_nav() if g.user else [])


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def errors(e):
    msg = {400: "Bad request or expired form. Please go back and try again.",
           403: "You do not have permission to open this page.",
           404: "Page not found."}[e.code]
    return render_template("error.html", code=e.code, msg=msg), e.code


# ---------------------------------------------------------------- helpers
def my_id(table):
    conn = get_db()
    r = conn.execute("SELECT id FROM %s WHERE user_id=?" % table, (g.user["id"],)).fetchone()
    conn.close()
    return r["id"] if r else None


def valid_date(v):
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_account(username, password, confirm, email, mobile, name, conn, dob=""):
    """Username and password can be ANYTHING (letters, numbers, spaces, symbols) - only must not be empty."""
    errs = []
    if not name:
        errs.append("Full name is required.")
    if not username:
        errs.append("Username cannot be empty.")
    elif len(username) > 50:
        errs.append("Username can be at most 50 characters.")
    elif conn.execute("SELECT 1 FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone():
        errs.append("That username is already taken. Please choose another one.")
    if not password:
        errs.append("Password cannot be empty.")
    if password != confirm:
        errs.append("Passwords do not match.")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errs.append("Enter a valid email address.")
    if mobile and not re.fullmatch(r"\d{10}", mobile):
        errs.append("Mobile number must be 10 digits.")
    if dob and not valid_date(dob):
        errs.append("Enter a valid date of birth.")
    return errs


def send_mail(to, subject, body):
    """Sends a real email if SMTP_HOST / SMTP_USER / SMTP_PASS are set. Otherwise returns False (the reset link is shown on screen instead)."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    try:
        import smtplib
        from email.message import EmailMessage
        m = EmailMessage()
        m["Subject"], m["To"] = subject, to
        m["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER", "noreply@campus.local")
        m.set_content(body)
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as srv:
            srv.starttls()
            if os.environ.get("SMTP_USER"):
                srv.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
            srv.send_message(m)
        return True
    except Exception:
        return False


def role_names(conn):
    return [r["name"] for r in conn.execute("SELECT name FROM roles ORDER BY id")]


def resolve_college(conn, college_id, other):
    """Student picked a listed college OR typed their own - a new college is created automatically."""
    other = (other or "").strip()
    if college_id == "other" or (not college_id and other):
        if not other:
            return None
        row = conn.execute("SELECT id FROM colleges WHERE name=? COLLATE NOCASE", (other,)).fetchone()
        if row:
            return row["id"]
        return conn.execute("INSERT INTO colleges (name, description, address) VALUES (?,?,?)",
                            (other[:100], "Added by a student", "")).lastrowid
    return int(college_id) if college_id and college_id.isdigit() else None


def skill_list(text):
    return [x.strip().lower() for x in re.split(r"[,;\n]", text or "") if x.strip()]


def student_pool(conn, sid):
    """Everything we know a student can do: skills + qualification types + qualification details."""
    if sid is None:
        return set(), ""
    row = conn.execute("SELECT skills FROM students WHERE id=?", (sid,)).fetchone()
    tokens, text = set(skill_list(row["skills"] if row else "")), []
    for q in conn.execute("SELECT type, description FROM qualifications WHERE student_id=?", (sid,)):
        tokens.add((q["type"] or "").strip().lower())
        text.append((q["description"] or "").lower())
    return tokens, " ".join(text)


def match_info(pool, job_skills):
    """Match score between a student and the skills a job requires."""
    wanted = skill_list(job_skills)
    if not wanted:
        return None
    tokens, text = pool
    ok = [k for k in wanted if k in tokens or re.search(r"(?<![a-z0-9+#])" + re.escape(k) + r"(?![a-z0-9+#])", text)]
    return dict(pct=round(len(ok) * 100 / len(wanted)), matched=ok, missing=[k for k in wanted if k not in ok])


def ensure_profile(conn, uid, role, name, email="", mobile="", address="", college_id=None, course="", ctype="", skills=""):
    if role == "student" and not conn.execute("SELECT 1 FROM students WHERE user_id=?", (uid,)).fetchone():
        conn.execute("INSERT INTO students (user_id,college_id,name,email,mobile,course,address,skills) VALUES (?,?,?,?,?,?,?,?)",
                     (uid, college_id, name, email, mobile, course, address, skills))
    if role == "company" and not conn.execute("SELECT 1 FROM companies WHERE user_id=?", (uid,)).fetchone():
        conn.execute("INSERT INTO companies (user_id,name,type,description,address) VALUES (?,?,?,?,?)",
                     (uid, name, ctype, "", address))


def sync_placement(conn, aid):
    """When an application becomes 'Selected' a placement record is created automatically."""
    a = conn.execute("""SELECT a.student_id, a.job_id, a.status, j.company_id, j.type, j.name jname,
                        co.name cname, s.college_id FROM applications a
                        JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=j.company_id
                        JOIN students s ON s.id=a.student_id WHERE a.id=?""", (aid,)).fetchone()
    if not a:
        return
    conn.execute("DELETE FROM placements WHERE student_id=? AND job_id=? AND source='auto'", (a["student_id"], a["job_id"]))
    if a["status"] == "Selected":
        ql = conn.execute("SELECT type FROM qualifications WHERE student_id=? ORDER BY id DESC LIMIT 1", (a["student_id"],)).fetchone()
        conn.execute("""INSERT INTO placements (student_id,college_id,company_id,job_id,qualification,type,description,placed_on,source)
                        VALUES (?,?,?,?,?,?,?,?, 'auto')""",
                     (a["student_id"], a["college_id"], a["company_id"], a["job_id"], ql["type"] if ql else "",
                      a["type"], "Selected for %s at %s" % (a["jname"], a["cname"]), datetime.now().strftime("%Y-%m-%d")))


# ---------------------------------------------------------------- authentication
@app.route("/", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect("/dashboard")
    if request.method == "POST":
        ident, pw = request.form.get("username", "").strip(), request.form.get("password", "")
        conn = get_db()
        cands = conn.execute("""SELECT * FROM users WHERE username=? COLLATE NOCASE
                                OR (email<>'' AND email=? COLLATE NOCASE)""", (ident, ident)).fetchall()
        user = next((u for u in cands if check_password_hash(u["password"], pw)), None)
        conn.execute("INSERT INTO login_log (username, success, at) VALUES (?,?,?)", (ident[:50], 1 if user else 0, dbm.now()))
        conn.commit()
        conn.close()
        if user:
            session.clear()
            session["uid"] = user["id"]
            flash("Welcome back, %s!" % (user["full_name"] or user["username"]), "success")
            return redirect("/dashboard")
        flash("Invalid Login/Password", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    conn = get_db()
    colleges = conn.execute("SELECT id, name FROM colleges ORDER BY name").fetchall()
    if request.method == "POST":
        f = request.form
        role = f.get("role")
        username = f.get("username", "").strip()
        errs = validate_account(username, f.get("password"), f.get("confirm"), f.get("email", "").strip(),
                                f.get("mobile", "").strip(), f.get("full_name", "").strip(), conn, f.get("dob", "").strip())
        if role not in ("student", "company"):
            errs.append("Choose Student or Company.")
        if f.get("sec_q") not in SEC_QUESTIONS or not f.get("sec_a", "").strip():
            errs.append("Choose a security question and give an answer.")
        if not errs:
            uid = add_user(conn, username, f["password"], role, f["full_name"].strip(), f.get("email", "").strip(),
                           f.get("mobile", "").strip(), f.get("address", "").strip(), f["sec_q"], f["sec_a"], f.get("dob", "").strip())
            cid = resolve_college(conn, f.get("college_id"), f.get("college_other")) if role == "student" else None
            ensure_profile(conn, uid, role, f["full_name"].strip(), f.get("email", "").strip(), f.get("mobile", "").strip(),
                           f.get("address", "").strip(), cid, f.get("course", "").strip(), f.get("ctype", ""),
                           f.get("skills", "").strip())
            conn.commit()
            conn.close()
            flash("Account created! You can now login with your username and password.", "success")
            return redirect("/")
        for e in errs:
            flash(e, "danger")
    conn.close()
    return render_template("register.html", colleges=colleges, questions=SEC_QUESTIONS, data=request.form,
                           ctypes=MODULES["companies"]["fields"][1][3])


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        conn = get_db()
        ident = request.form.get("username", "").strip()
        u = conn.execute("SELECT id FROM users WHERE username=? COLLATE NOCASE OR (email<>'' AND email=? COLLATE NOCASE)", (ident, ident)).fetchone()
        conn.close()
        if u:
            session["reset_uid"] = u["id"]
            session.pop("demo_mail", None)
            return redirect("/forgot/verify")
        flash("No account found with that username or email.", "danger")
    return render_template("forgot.html")


@app.route("/forgot/verify", methods=["GET", "POST"])
def forgot_verify():
    uid = session.get("reset_uid")
    if not uid:
        return redirect("/forgot")
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if request.method == "POST":
        ans, new, conf = request.form.get("answer", "").strip().lower(), request.form.get("password", ""), request.form.get("confirm", "")
        if not u["sec_a"] or not check_password_hash(u["sec_a"], ans):
            flash("Security answer is incorrect.", "danger")
        elif not new or new != conf:
            flash("Password cannot be empty and both fields must match.", "danger")
        else:
            conn.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new), uid))
            conn.commit()
            session.pop("reset_uid", None)
            conn.close()
            flash("Password reset successful. Please login.", "success")
            return redirect("/")
    conn.close()
    return render_template("verify.html", question=u["sec_q"], username=u["username"], has_email=bool(u["email"]),
                           email=u["email"], demo=session.get("demo_mail"))


@app.route("/forgot/email", methods=["POST"])
def forgot_email():
    """Sequence diagram: 'Send email to user to reset password'."""
    uid = session.get("reset_uid")
    if not uid:
        return redirect("/forgot")
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u["email"]:
        conn.close()
        flash("This account has no email address. Use the security question instead.", "warning")
        return redirect("/forgot/verify")
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO password_resets (token, user_id, expires_at) VALUES (?,?,?)",
                 (token, uid, (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    link = request.host_url + "reset/" + token
    sent = send_mail(u["email"], "Reset your CampusHire password",
                     "Hello %s,\n\nOpen this link within 30 minutes to reset your password:\n%s\n" % (u["full_name"] or u["username"], link))
    if sent:
        session.pop("demo_mail", None)
        flash("A reset link has been emailed to %s." % u["email"], "success")
    else:
        session["demo_mail"] = {"to": u["email"], "link": link}
        flash("Email server is not configured, so the reset link is shown below instead of being emailed.", "info")
    return redirect("/forgot/verify")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    conn = get_db()
    r = conn.execute("SELECT * FROM password_resets WHERE token=? AND used=0", (token,)).fetchone()
    if not r or r["expires_at"] < datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
        conn.close()
        flash("This reset link is invalid or has expired.", "danger")
        return redirect("/forgot")
    if request.method == "POST":
        new, conf = request.form.get("password", ""), request.form.get("confirm", "")
        if not new or new != conf:
            flash("Password cannot be empty and both fields must match.", "danger")
        else:
            conn.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new), r["user_id"]))
            conn.execute("UPDATE password_resets SET used=1 WHERE token=?", (token,))
            conn.commit()
            conn.close()
            session.pop("demo_mail", None)
            session.pop("reset_uid", None)
            flash("Password reset successful. Please login.", "success")
            return redirect("/")
    conn.close()
    return render_template("reset.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db()
    role, uid = g.user["role"], g.user["id"]
    extra = conn.execute("SELECT * FROM %s WHERE user_id=?" % ("students" if role == "student" else "companies"), (uid,)).fetchone() \
        if role in ("student", "company") else None
    colleges = conn.execute("SELECT id, name FROM colleges ORDER BY name").fetchall()
    if request.method == "POST":
        f = request.form
        name, email, mobile, addr, dob = (f.get(k, "").strip() for k in ("full_name", "email", "mobile", "address", "dob"))
        errs = []
        if not name:
            errs.append("Full name is required.")
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errs.append("Enter a valid email address.")
        if mobile and not re.fullmatch(r"\d{10}", mobile):
            errs.append("Mobile number must be 10 digits.")
        if dob and not valid_date(dob):
            errs.append("Enter a valid date of birth.")
        if not errs:
            conn.execute("UPDATE users SET full_name=?, email=?, mobile=?, address=?, dob=? WHERE id=?", (name, email, mobile, addr, dob, uid))
            if f.get("sec_a", "").strip() and f.get("sec_q") in SEC_QUESTIONS:
                conn.execute("UPDATE users SET sec_q=?, sec_a=? WHERE id=?",
                             (f["sec_q"], generate_password_hash(f["sec_a"].strip().lower()), uid))
            if role == "student":
                cid = resolve_college(conn, f.get("college_id"), f.get("college_other"))
                conn.execute("UPDATE students SET name=?, email=?, mobile=?, address=?, course=?, college_id=?, skills=? WHERE user_id=?",
                             (name, email, mobile, addr, f.get("course", "").strip(), cid, f.get("skills", "").strip(), uid))
            elif role == "company":
                conn.execute("UPDATE companies SET name=?, address=?, type=?, description=? WHERE user_id=?",
                             (name, addr, f.get("ctype", ""), f.get("description", "").strip(), uid))
            conn.commit()
            conn.close()
            flash("Profile updated successfully.", "success")
            return redirect("/profile")
        for e in errs:
            flash(e, "danger")
    conn.close()
    return render_template("profile.html", extra=extra, colleges=colleges, ctypes=MODULES["companies"]["fields"][1][3],
                           questions=SEC_QUESTIONS)


@app.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        cur, new, conf = (request.form.get(k, "") for k in ("current", "password", "confirm"))
        if not check_password_hash(g.user["password"], cur):
            flash("Current password is wrong.", "danger")
        elif not new or new != conf:
            flash("New password cannot be empty and both fields must match.", "danger")
        else:
            conn = get_db()
            conn.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new), g.user["id"]))
            conn.commit()
            conn.close()
            flash("Password changed successfully.", "success")
            return redirect("/dashboard")
    return render_template("password.html")


# ---------------------------------------------------------------- dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    conn, role, d = get_db(), g.user["role"], {}

    def q(sql, p=()):
        return conn.execute(sql, p).fetchone()[0]

    if role not in ("company", "student"):
        stats = []
        for m in ["students", "colleges", "companies", "jobs", "placements"]:
            if access(m):
                stats.append((MODULES[m]["title"], q("SELECT COUNT(*) FROM " + m), MODULES[m]["icon"], "/m/" + m))
        stats.append(("Applications", q("SELECT COUNT(*) FROM applications"), "📨", "/applications"))
        total, placed = q("SELECT COUNT(*) FROM students"), q("SELECT COUNT(DISTINCT student_id) FROM placements")
        d.update(stats=stats, rate=round(placed * 100 / total) if total else 0, placed=placed, total=total,
                 status_counts=[(s, q("SELECT COUNT(*) FROM applications WHERE status=?", (s,))) for s in APP_STATUS],
                 top=conn.execute("""SELECT co.name, COUNT(a.id) c FROM companies co LEFT JOIN jobs j ON j.company_id=co.id
                        LEFT JOIN applications a ON a.job_id=j.id GROUP BY co.id ORDER BY c DESC, co.name LIMIT 5""").fetchall(),
                 recent=conn.execute("""SELECT s.name student, j.name job, a.status, a.applied_at FROM applications a
                        JOIN students s ON s.id=a.student_id JOIN jobs j ON j.id=a.job_id ORDER BY a.id DESC LIMIT 6""").fetchall())
    elif role == "company":
        cid = my_id("companies")
        d.update(stats=[("My Jobs", q("SELECT COUNT(*) FROM jobs WHERE company_id=?", (cid,)), "💼", "/m/jobs"),
                        ("Applicants", q("SELECT COUNT(*) FROM applications a JOIN jobs j ON j.id=a.job_id WHERE j.company_id=?", (cid,)), "📨", "/applications"),
                        ("Selected", q("SELECT COUNT(*) FROM applications a JOIN jobs j ON j.id=a.job_id WHERE j.company_id=? AND a.status='Selected'", (cid,)), "🏆", "/applications?status=Selected"),
                        ("Students", q("SELECT COUNT(*) FROM students"), "🎓", "/m/students")],
                 recent=conn.execute("""SELECT s.name student, j.name job, a.status, a.applied_at FROM applications a
                        JOIN students s ON s.id=a.student_id JOIN jobs j ON j.id=a.job_id WHERE j.company_id=?
                        ORDER BY a.id DESC LIMIT 6""", (cid,)).fetchall())
    else:
        sid = my_id("students")
        d.update(stats=[("Open Jobs", q("SELECT COUNT(*) FROM jobs WHERE status='Open'"), "🔎", "/jobs")] +
                 [(lbl, q("SELECT COUNT(*) FROM applications WHERE student_id=? AND status IN (%s)" % ",".join("?" * len(sts)), (sid, *sts)), ic, "/applications")
                  for lbl, sts, ic in [("Applied", ["Applied"], "📨"), ("In Progress", ["Shortlisted", "Interview Scheduled"], "⏳"), ("Selected", ["Selected"], "🏆")]],
                 recent=conn.execute("""SELECT j.name job, co.name company, a.status, a.applied_at FROM applications a
                        JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=j.company_id WHERE a.student_id=?
                        ORDER BY a.id DESC LIMIT 6""", (sid,)).fetchall(),
                 latest=conn.execute("""SELECT j.id, j.name, j.salary, j.type, j.skills, co.name company FROM jobs j
                        LEFT JOIN companies co ON co.id=j.company_id WHERE j.status='Open' ORDER BY j.id DESC LIMIT 4""").fetchall(),
                 quals=q("SELECT COUNT(*) FROM qualifications WHERE student_id=?", (sid,)))
        pool = student_pool(conn, sid)
        d["latest"] = [dict(r, match=match_info(pool, r["skills"])) for r in d["latest"]]
    conn.close()
    return render_template("dashboard.html", **d)


# ---------------------------------------------------------------- generic CRUD
def get_cfg(module):
    if module not in MODULES:
        abort(404)
    return MODULES[module]


def scope(module):
    """Row-level restriction: companies see their own jobs, students their own qualifications."""
    role = g.user["role"]
    if role == "company" and module in ("jobs", "placements"):
        cid = my_id("companies")
        if cid is None:
            abort(403)
        return "company_id=?", [cid], ({"company_id": cid} if module == "jobs" else {})
    if role == "student" and module == "qualifications":
        sid = my_id("students")
        if sid is None:
            abort(403)
        return "student_id=?", [sid], {"student_id": sid}
    return "1=1", [], {}


def load_lookups(conn, cfg):
    out = {}
    for f in cfg["fields"]:
        if f[2].startswith("select:"):
            table = f[2].split(":")[1]
            out[f[0]] = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM %s ORDER BY name" % table)}
    return out


def form_values(cfg, forced):
    vals, errs = {}, []
    for f in cfg["fields"]:
        name, label, kind = f[0], f[1], f[2]
        if name in forced:
            continue
        v = request.form.get(name, "").strip()
        if not v:
            if kind != "textarea" and name not in cfg["optional"]:
                errs.append("%s is required." % label)
            vals[name] = None
            continue
        if kind == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            errs.append("Enter a valid email address.")
        if name == "mobile" and not re.fullmatch(r"\d{10}", v):
            errs.append("Mobile number must be 10 digits.")
        if kind == "number":
            try:
                v = float(v)
                if v < 0 or (name == "percentage" and v > 100):
                    raise ValueError
                v = int(v) if v == int(v) else v
            except ValueError:
                errs.append("%s must be a valid number." % label)
        if kind.startswith("select:"):
            if v.isdigit():
                v = int(v)
            else:
                errs.append("Choose a valid %s." % label.lower())
        if isinstance(v, str) and len(v) > 300:
            errs.append("%s is too long." % label)
        if kind == "choice" and v not in f[3]:
            errs.append("Choose a valid %s." % label.lower())
        vals[name] = v
    return vals, errs


@app.route("/m/<module>")
@login_required
def mod_list(module):
    cfg = get_cfg(module)
    need(module, "r")
    where, params, _ = scope(module)
    conn = get_db()
    rows = conn.execute("SELECT * FROM %s WHERE %s ORDER BY id DESC" % (module, where), params).fetchall()
    lookups = load_lookups(conn, cfg)
    conn.close()
    cols = [f for f in cfg["fields"] if f[0] not in cfg["hide"]]
    q = request.args.get("q", "").strip().lower()
    out = []
    for r in rows:
        cells = []
        for f in cols:
            v = r[f[0]]
            if f[2].startswith("select:"):
                v = lookups[f[0]].get(v, "—")
            v = "—" if v in (None, "") else str(v)
            cells.append((f[0], v if len(v) < 46 else v[:43] + "..."))
        if not q or q in " ".join(c[1] for c in cells).lower():
            out.append(dict(id=r["id"], cells=cells))
    return render_template("crud_list.html", cfg=cfg, module=module, headers=[f[1] for f in cols],
                           rows=out, actions=access(module), q=request.args.get("q", ""))


@app.route("/m/<module>/<int:rid>")
@login_required
def mod_detail(module, rid):
    cfg = get_cfg(module)
    need(module, "r")
    where, params, _ = scope(module)
    conn = get_db()
    row = conn.execute("SELECT * FROM %s WHERE id=? AND %s" % (module, where), [rid] + params).fetchone()
    if not row:
        conn.close()
        abort(404)
    lookups = load_lookups(conn, cfg)
    items = []
    for f in cfg["fields"]:
        v = row[f[0]]
        if f[2].startswith("select:"):
            v = lookups[f[0]].get(v)
        items.append((f[1], v if v not in (None, "") else "—"))
    related = []
    if module == "colleges":
        related.append(("Students of this college", ["Name", "Course", "Email"],
                        [list(r) for r in conn.execute("SELECT name, course, email FROM students WHERE college_id=?", (rid,))]))
    elif module == "companies":
        related.append(("Jobs posted by this company", ["Job", "Type", "Salary", "Status"],
                        [list(r) for r in conn.execute("SELECT name, type, salary, status FROM jobs WHERE company_id=?", (rid,))]))
    elif module == "jobs":
        related.append(("Applicants", ["Student", "Status"],
                        [list(r) for r in conn.execute("SELECT s.name, a.status FROM applications a JOIN students s ON s.id=a.student_id WHERE a.job_id=?", (rid,))]))
        related.append(("Vacancies", ["Type", "Openings", "Description"],
                        [list(r) for r in conn.execute("SELECT type, openings, description FROM vacancies WHERE job_id=?", (rid,))]))
    conn.close()
    return render_template("detail.html", cfg=cfg, module=module, row=row, items=items, related=related, actions=access(module))


def save_form(module, rid=None):
    cfg = get_cfg(module)
    need(module, "u" if rid else "c")
    where, params, forced = scope(module)
    conn = get_db()
    row = None
    if rid:
        row = conn.execute("SELECT * FROM %s WHERE id=? AND %s" % (module, where), [rid] + params).fetchone()
        if not row:
            conn.close()
            abort(404)
    data = dict(row) if row else {}
    if request.method == "POST":
        vals, errs = form_values(cfg, forced)
        if not errs:
            try:
                if rid:
                    conn.execute("UPDATE %s SET %s WHERE id=?" % (module, ",".join(k + "=?" for k in vals)), list(vals.values()) + [rid])
                else:
                    vals.update(forced)
                    if "defaults" in cfg:
                        vals.update(cfg["defaults"]())
                    conn.execute("INSERT INTO %s (%s) VALUES (%s)" % (module, ",".join(vals), ",".join("?" * len(vals))), list(vals.values()))
                conn.commit()
                conn.close()
                flash("Record %s successfully." % ("updated" if rid else "added"), "success")
                return redirect("/m/" + module)
            except sqlite3.IntegrityError:
                errs.append("Could not save. Please check the selected values.")
        for e in errs:
            flash(e, "danger")
        data = request.form
    lookups = load_lookups(conn, cfg)
    conn.close()
    return render_template("crud_form.html", cfg=cfg, module=module, data=data, forced=forced, lookups=lookups, editing=bool(rid))


@app.route("/m/<module>/add", methods=["GET", "POST"])
@login_required
def mod_add(module):
    return save_form(module)


@app.route("/m/<module>/<int:rid>/edit", methods=["GET", "POST"])
@login_required
def mod_edit(module, rid):
    return save_form(module, rid)


@app.route("/m/<module>/<int:rid>/delete", methods=["POST"])
@login_required
def mod_delete(module, rid):
    get_cfg(module)
    need(module, "d")
    where, params, _ = scope(module)
    conn = get_db()
    row = conn.execute("SELECT * FROM %s WHERE id=? AND %s" % (module, where), [rid] + params).fetchone()
    if not row:
        conn.close()
        abort(404)
    if module in ("students", "companies") and row["user_id"]:
        conn.execute("DELETE FROM users WHERE id=?", (row["user_id"],))  # cascades to the profile row
    conn.execute("DELETE FROM %s WHERE id=?" % module, (rid,))
    conn.commit()
    conn.close()
    flash("Record deleted.", "info")
    return redirect("/m/" + module)


@app.route("/students/<int:sid>")
@login_required
def student_detail(sid):
    need("students", "r")
    conn = get_db()
    s = conn.execute("SELECT s.*, c.name college FROM students s LEFT JOIN colleges c ON c.id=s.college_id WHERE s.id=?", (sid,)).fetchone()
    if not s:
        conn.close()
        abort(404)
    quals = conn.execute("SELECT * FROM qualifications WHERE student_id=? ORDER BY id", (sid,)).fetchall()
    apps = conn.execute("""SELECT j.name job, co.name company, a.status, a.applied_at FROM applications a
                           JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=j.company_id
                           WHERE a.student_id=? ORDER BY a.id DESC""", (sid,)).fetchall()
    conn.close()
    return render_template("student_detail.html", s=s, quals=quals, apps=apps)


# ---------------------------------------------------------------- jobs & applications
@app.route("/jobs")
@login_required
def browse_jobs():
    conn = get_db()
    sid = my_id("students") if g.user["role"] == "student" else None
    rows = conn.execute("""SELECT j.*, co.name company,
                (SELECT status FROM applications a WHERE a.job_id=j.id AND a.student_id=?) my_status
                FROM jobs j LEFT JOIN companies co ON co.id=j.company_id ORDER BY j.status='Open' DESC, j.id DESC""", (sid,)).fetchall()
    pool = student_pool(conn, sid)
    conn.close()
    q, t = request.args.get("q", "").strip().lower(), request.args.get("type", "")
    rows = [dict(r, match=match_info(pool, r["skills"]) if sid else None) for r in rows if (not t or r["type"] == t) and
            (not q or q in " ".join(str(r[k] or "") for k in ("name", "company", "location", "description", "type", "skills")).lower())]
    return render_template("jobs.html", jobs=rows, q=request.args.get("q", ""), t=t, types=MODULES["jobs"]["fields"][1][3])


@app.route("/jobs/<int:jid>")
@login_required
def job_detail(jid):
    conn = get_db()
    j = conn.execute("SELECT j.*, co.name company, co.type ctype FROM jobs j LEFT JOIN companies co ON co.id=j.company_id WHERE j.id=?", (jid,)).fetchone()
    if not j:
        conn.close()
        abort(404)
    vac = conn.execute("SELECT * FROM vacancies WHERE job_id=?", (jid,)).fetchall()
    my, match = None, None
    if g.user["role"] == "student":
        sid = my_id("students")
        my = conn.execute("SELECT status, interview_at FROM applications WHERE job_id=? AND student_id=?", (jid, sid)).fetchone()
        match = match_info(student_pool(conn, sid), j["skills"])
    conn.close()
    return render_template("job_detail.html", j=j, vac=vac, my=my, match=match, skills=skill_list(j["skills"]))


@app.route("/jobs/<int:jid>/apply", methods=["POST"])
@roles_required("student")
def apply_job(jid):
    sid = my_id("students")
    conn = get_db()
    j = conn.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
    if not j or sid is None:
        conn.close()
        abort(404)
    if j["status"] != "Open":
        flash("This job is closed for applications.", "warning")
    else:
        try:
            conn.execute("INSERT INTO applications (student_id,job_id,status,applied_at) VALUES (?,?, 'Applied', ?)", (sid, jid, dbm.now()))
            conn.commit()
            flash("Application submitted! Track it in My Applications.", "success")
        except sqlite3.IntegrityError:
            flash("You have already applied for this job.", "info")
    conn.close()
    return redirect("/jobs/%d" % jid)


@app.route("/applications")
@login_required
def applications():
    role = g.user["role"]
    where, params = "1=1", []
    if role == "student":
        where, params = "a.student_id=?", [my_id("students")]
    elif role == "company":
        where, params = "j.company_id=?", [my_id("companies")]
    else:
        need("applications", "r")
    job, status = request.args.get("job", ""), request.args.get("status", "")
    if job.isdigit():
        where += " AND a.job_id=?"
        params.append(int(job))
    if status in APP_STATUS:
        where += " AND a.status=?"
        params.append(status)
    conn = get_db()
    rows = conn.execute("""SELECT a.id, a.status, a.applied_at, a.interview_at, j.skills jskills, s.id sid, s.name student, s.course, c.name college,
                j.id jid, j.name job, co.name company FROM applications a
                JOIN students s ON s.id=a.student_id LEFT JOIN colleges c ON c.id=s.college_id
                JOIN jobs j ON j.id=a.job_id LEFT JOIN companies co ON co.id=j.company_id
                WHERE %s ORDER BY a.id DESC""" % where, params).fetchall()
    pools = {}
    if role != "student":
        for r in rows:
            if r["sid"] not in pools:
                pools[r["sid"]] = student_pool(conn, r["sid"])
    rows = [dict(r, match=match_info(pools[r["sid"]], r["jskills"]) if role != "student" else None) for r in rows]
    conn.close()
    return render_template("applications.html", rows=rows, statuses=APP_STATUS, status=status, job=job,
                           can_update=role in ("admin", "staff", "company"))


@app.route("/applications/<int:aid>/status", methods=["POST"])
@login_required
def app_status(aid):
    status = request.form.get("status")
    if status not in APP_STATUS:
        abort(400)
    conn = get_db()
    a = conn.execute("SELECT a.id, j.company_id FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?", (aid,)).fetchone()
    if not a:
        conn.close()
        abort(404)
    role = g.user["role"]
    if role == "student" or (role == "company" and a["company_id"] != my_id("companies")):
        conn.close()
        abort(403)
    if role != "company":
        need("applications", "u")
    iv = request.form.get("interview_at", "").strip()
    if status != "Interview Scheduled":
        conn.execute("UPDATE applications SET status=?, interview_at=NULL WHERE id=?", (status, aid))
    elif iv:
        try:
            datetime.strptime(iv, "%Y-%m-%dT%H:%M")
        except ValueError:
            conn.close()
            abort(400)
        conn.execute("UPDATE applications SET status=?, interview_at=? WHERE id=?", (status, iv.replace("T", " "), aid))
    else:
        conn.execute("UPDATE applications SET status=? WHERE id=?", (status, aid))
    sync_placement(conn, aid)
    conn.commit()
    conn.close()
    flash("Application status updated to '%s'." % status, "success")
    return redirect("/applications")


@app.route("/applications/<int:aid>/withdraw", methods=["POST"])
@roles_required("student")
def withdraw(aid):
    conn = get_db()
    conn.execute("DELETE FROM applications WHERE id=? AND student_id=? AND status='Applied'", (aid, my_id("students")))
    conn.commit()
    conn.close()
    flash("Application withdrawn.", "info")
    return redirect("/applications")


# ---------------------------------------------------------------- reports (DFD level 1)
REPORTS = {
    "students": ("Student Report", """SELECT s.id ID, s.name Name, s.email Email, s.mobile Mobile, s.course Course, s.skills Skills, c.name College,
        (SELECT COUNT(*) FROM applications a WHERE a.student_id=s.id) Applications,
        CASE WHEN EXISTS (SELECT 1 FROM placements p WHERE p.student_id=s.id) THEN 'Placed' ELSE 'Not placed' END Status
        FROM students s LEFT JOIN colleges c ON c.id=s.college_id ORDER BY s.id"""),
    "colleges": ("College Report", """SELECT c.id ID, c.name College, c.address Address,
        (SELECT COUNT(*) FROM students s WHERE s.college_id=c.id) Students,
        (SELECT COUNT(DISTINCT p.student_id) FROM placements p WHERE p.college_id=c.id) Placed
        FROM colleges c ORDER BY c.id"""),
    "companies": ("Company Report", """SELECT co.id ID, co.name Company, co.type Type, co.address Address,
        (SELECT COUNT(*) FROM jobs j WHERE j.company_id=co.id) Jobs,
        (SELECT COUNT(*) FROM applications a JOIN jobs j ON j.id=a.job_id WHERE j.company_id=co.id) Applications,
        (SELECT COUNT(*) FROM placements p WHERE p.company_id=co.id) Placements FROM companies co ORDER BY co.id"""),
    "jobs": ("Job Report", """SELECT j.id ID, j.name Job, co.name Company, j.type Type, j.salary Salary, j.skills Skills, j.openings Openings,
        j.status Status, (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.id) Applicants
        FROM jobs j LEFT JOIN companies co ON co.id=j.company_id ORDER BY j.id"""),
    "placements": ("Placement Report", """SELECT p.id ID, s.name Student, co.name Company, j.name Job, c.name College,
        p.qualification Qualification, p.type Type, p.placed_on Date FROM placements p
        LEFT JOIN students s ON s.id=p.student_id LEFT JOIN companies co ON co.id=p.company_id
        LEFT JOIN jobs j ON j.id=p.job_id LEFT JOIN colleges c ON c.id=p.college_id ORDER BY p.id"""),
    "vacancies": ("Vacancy Report", """SELECT v.id ID, j.name Job, co.name Company, v.type Type, v.openings Openings,
        v.description Description FROM vacancies v LEFT JOIN jobs j ON j.id=v.job_id
        LEFT JOIN companies co ON co.id=j.company_id ORDER BY v.id"""),
    "qualifications": ("Qualification Report", """SELECT q.id ID, s.name Student, q.type Qualification, q.percentage Percentage,
        q.description Details FROM qualifications q LEFT JOIN students s ON s.id=q.student_id ORDER BY q.id"""),
    "logins": ("Login Activity Report (Check User Login Details)", """SELECT id ID, username Username,
        CASE success WHEN 1 THEN 'Success' ELSE 'Failed' END Result, at Time FROM login_log ORDER BY id DESC LIMIT 300"""),
    "users": ("System User Report", """SELECT id ID, username Username, role Role, full_name Name, email Email,
        mobile Mobile, created_at Created FROM users ORDER BY id"""),
}


def check_report(name):
    if name not in REPORTS:
        abort(404)
    if name in ("users", "logins"):
        if g.user["role"] != "admin":
            abort(403)
    else:
        need("reports", "r")


@app.route("/reports")
@login_required
def reports():
    if g.user["role"] in ("company", "student") or ("reports" not in g.perms and g.user["role"] != "admin"):
        abort(403)
    return render_template("reports.html", items=[(k, v[0]) for k, v in REPORTS.items() if k not in ("users", "logins") or g.user["role"] == "admin"])


@app.route("/reports/<name>")
@login_required
def report(name):
    check_report(name)
    conn = get_db()
    cur = conn.execute(REPORTS[name][1])
    headers = [d[0] for d in cur.description]
    rows = [list(r) for r in cur.fetchall()]
    conn.close()
    q = request.args.get("q", "").strip().lower()
    if q:
        rows = [r for r in rows if q in " ".join(str(c) for c in r).lower()]
    if request.args.get("format") == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        w.writerows(rows)
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=%s_report.csv" % name})
    return render_template("report.html", name=name, title=REPORTS[name][0], headers=headers, rows=rows,
                           q=request.args.get("q", ""), generated=dbm.now())


# ---------------------------------------------------------------- admin: users, roles, permissions
@app.route("/admin/users")
@roles_required("admin")
def admin_users():
    conn = get_db()
    q = request.args.get("q", "").strip().lower()
    users = [u for u in conn.execute("SELECT * FROM users ORDER BY id")
             if not q or q in " ".join(str(u[k] or "") for k in ("username", "full_name", "email", "role")).lower()]
    roles = role_names(conn)
    conn.close()
    return render_template("users.html", users=users, roles=roles, q=request.args.get("q", ""))


@app.route("/admin/users/add", methods=["GET", "POST"])
@roles_required("admin")
def admin_user_add():
    conn = get_db()
    roles = role_names(conn)
    if request.method == "POST":
        f = request.form
        username = f.get("username", "").strip()
        errs = validate_account(username, f.get("password"), f.get("password"), f.get("email", "").strip(),
                                f.get("mobile", "").strip(), f.get("full_name", "").strip(), conn, f.get("dob", "").strip())
        if f.get("role") not in roles:
            errs.append("Choose a valid role.")
        if not errs:
            uid = add_user(conn, username, f["password"], f["role"], f["full_name"].strip(),
                           f.get("email", "").strip(), f.get("mobile", "").strip(), dob=f.get("dob", "").strip())
            ensure_profile(conn, uid, f["role"], f["full_name"].strip(), f.get("email", "").strip(), f.get("mobile", "").strip())
            conn.commit()
            conn.close()
            flash("User created.", "success")
            return redirect("/admin/users")
        for e in errs:
            flash(e, "danger")
    conn.close()
    return render_template("user_add.html", roles=roles, data=request.form)


@app.route("/admin/users/<int:uid>/role", methods=["POST"])
@roles_required("admin")
def admin_user_role(uid):
    role = request.form.get("role")
    conn = get_db()
    if role not in role_names(conn):
        conn.close()
        abort(400)
    if uid == g.user["id"]:
        conn.close()
        flash("You cannot change your own role.", "warning")
        return redirect("/admin/users")
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        conn.close()
        abort(404)
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    ensure_profile(conn, uid, role, u["full_name"] or u["username"], u["email"] or "", u["mobile"] or "", u["address"] or "")
    conn.commit()
    conn.close()
    flash("Role assigned: %s is now '%s'." % (u["username"], role), "success")
    return redirect("/admin/users")


@app.route("/admin/users/<int:uid>/delete", methods=["POST"])
@roles_required("admin")
def admin_user_delete(uid):
    if uid == g.user["id"]:
        flash("You cannot delete your own account.", "warning")
    else:
        conn = get_db()
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        conn.close()
        flash("User deleted.", "info")
    return redirect("/admin/users")


PROTECTED_ROLES = ("admin", "staff", "company", "student")


@app.route("/admin/permissions")
@roles_required("admin")
def admin_permissions():
    conn = get_db()
    q = request.args.get("q", "").strip().lower()
    roles = [r for r in conn.execute("SELECT r.*, (SELECT COUNT(*) FROM users u WHERE u.role=r.name) users FROM roles r ORDER BY r.id")
             if not q or q in (r["name"] + " " + (r["description"] or "")).lower()]
    staff_roles = [r["name"] for r in conn.execute("SELECT name FROM roles ORDER BY id") if r["name"] not in ("admin", "company", "student")]
    allowed = {(r["role"], r["module"]) for r in conn.execute("SELECT role, module FROM permissions")}
    conn.close()
    return render_template("permissions.html", roles=roles, staff_roles=staff_roles, modules=PERM_MODULES, allowed=allowed,
                           protected=PROTECTED_ROLES, q=request.args.get("q", ""))


@app.route("/admin/permissions", methods=["POST"])
@roles_required("admin")
def admin_permissions_save():
    conn = get_db()
    for r in conn.execute("SELECT name FROM roles").fetchall():
        name = r["name"]
        if name in ("admin", "company", "student"):
            continue
        conn.execute("DELETE FROM permissions WHERE role=?", (name,))
        for m in request.form.getlist("perm_" + name):
            if m in PERM_MODULES:
                conn.execute("INSERT INTO permissions (role, module) VALUES (?,?)", (name, m))
    conn.commit()
    conn.close()
    flash("Permissions saved.", "success")
    return redirect("/admin/permissions")


@app.route("/admin/roles/add", methods=["POST"])
@roles_required("admin")
def admin_role_add():
    name, desc = request.form.get("name", "").strip().lower(), request.form.get("description", "").strip()
    conn = get_db()
    if not re.fullmatch(r"[a-z0-9_]{2,20}", name):
        flash("Role name must be 2-20 characters: small letters, numbers or underscore.", "danger")
    elif conn.execute("SELECT 1 FROM roles WHERE name=?", (name,)).fetchone():
        flash("That role already exists.", "danger")
    else:
        conn.execute("INSERT INTO roles (name, description) VALUES (?,?)", (name, desc))
        conn.commit()
        flash("Role '%s' added. Now tick its permissions below." % name, "success")
    conn.close()
    return redirect("/admin/permissions")


@app.route("/admin/roles/<int:rid>/edit", methods=["POST"])
@roles_required("admin")
def admin_role_edit(rid):
    conn = get_db()
    conn.execute("UPDATE roles SET description=? WHERE id=?", (request.form.get("description", "").strip(), rid))
    conn.commit()
    conn.close()
    flash("Role description updated.", "success")
    return redirect("/admin/permissions")


@app.route("/admin/roles/<int:rid>/delete", methods=["POST"])
@roles_required("admin")
def admin_role_delete(rid):
    conn = get_db()
    r = conn.execute("SELECT * FROM roles WHERE id=?", (rid,)).fetchone()
    if not r:
        conn.close()
        abort(404)
    if r["name"] in PROTECTED_ROLES:
        flash("The built-in roles cannot be deleted.", "warning")
    elif conn.execute("SELECT 1 FROM users WHERE role=?", (r["name"],)).fetchone():
        flash("This role is assigned to users. Change their role first.", "warning")
    else:
        conn.execute("DELETE FROM permissions WHERE role=?", (r["name"],))
        conn.execute("DELETE FROM roles WHERE id=?", (rid,))
        conn.commit()
        flash("Role deleted.", "info")
    conn.close()
    return redirect("/admin/permissions")


if __name__ == "__main__":
    app.run(debug=True)
