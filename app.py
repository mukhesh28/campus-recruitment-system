from flask import Flask, render_template, request, redirect, session, abort
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "campus-secret-key"

# Each module = table name and its columns
MODULES = {
    "students":   ["name", "email", "mobile", "address"],
    "colleges":   ["name", "description", "address"],
    "companies":  ["name", "type", "description", "address"],
    "jobs":       ["name", "type", "salary", "description"],
    "placements": ["student_name", "company_name", "job_name", "status"],
}

def get_db():
    conn = sqlite3.connect("campus.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    for table, fields in MODULES.items():
        cols = ", ".join(f + " TEXT" for f in fields)
        conn.execute("CREATE TABLE IF NOT EXISTS " + table +
                     " (id INTEGER PRIMARY KEY AUTOINCREMENT, " + cols + ")")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)")
    # default account so admin / admin123 still works
    if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                     ("admin", generate_password_hash("admin123")))
    conn.commit()
    conn.close()

def login_required():
    return "admin" in session

@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?",
                            (request.form["username"].strip(),)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], request.form["password"]):
            session["admin"] = True
            session["username"] = user["username"]
            return redirect("/dashboard")
        error = "Invalid Login/Password"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                         (username, generate_password_hash(password)))
            conn.commit()
            conn.close()
            return redirect("/")
        except sqlite3.IntegrityError:
            conn.close()
            error = "Username already exists. Try another."
    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/")
    conn = get_db()
    counts = {m: conn.execute("SELECT COUNT(*) FROM " + m).fetchone()[0] for m in MODULES}
    conn.close()
    return render_template("dashboard.html", counts=counts)

@app.route("/<module>")
def list_records(module):
    if not login_required():
        return redirect("/")
    if module not in MODULES:
        abort(404)
    search = request.args.get("search", "")
    conn = get_db()
    first = MODULES[module][0]
    rows = conn.execute("SELECT * FROM " + module + " WHERE " + first + " LIKE ?",
                        ("%" + search + "%",)).fetchall()
    conn.close()
    return render_template("list.html", module=module, fields=MODULES[module], rows=rows, search=search)

@app.route("/<module>/add", methods=["GET", "POST"])
def add_record(module):
    if not login_required():
        return redirect("/")
    if module not in MODULES:
        abort(404)
    fields = MODULES[module]
    if request.method == "POST":
        values = [request.form[f] for f in fields]
        conn = get_db()
        conn.execute("INSERT INTO " + module + " (" + ",".join(fields) + ") VALUES (" +
                     ",".join("?" * len(fields)) + ")", values)
        conn.commit()
        conn.close()
        return redirect("/" + module)
    return render_template("form.html", module=module, fields=fields, row=None)

@app.route("/<module>/edit/<int:rid>", methods=["GET", "POST"])
def edit_record(module, rid):
    if not login_required():
        return redirect("/")
    if module not in MODULES:
        abort(404)
    fields = MODULES[module]
    conn = get_db()
    if request.method == "POST":
        values = [request.form[f] for f in fields] + [rid]
        conn.execute("UPDATE " + module + " SET " + ",".join(f + "=?" for f in fields) +
                     " WHERE id=?", values)
        conn.commit()
        conn.close()
        return redirect("/" + module)
    row = conn.execute("SELECT * FROM " + module + " WHERE id=?", (rid,)).fetchone()
    conn.close()
    return render_template("form.html", module=module, fields=fields, row=row)

@app.route("/<module>/delete/<int:rid>")
def delete_record(module, rid):
    if not login_required():
        return redirect("/")
    if module not in MODULES:
        abort(404)
    conn = get_db()
    conn.execute("DELETE FROM " + module + " WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return redirect("/" + module)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
