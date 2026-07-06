from flask import Flask, request, redirect, render_template, jsonify, session, url_for
import sqlite3
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "dev-secret-change-this"

DB_FILE = "links.db"

# ================= DB INIT =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # links table (now tied to user)
    c.execute("""
    CREATE TABLE IF NOT EXISTS links (
        token TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        first_click TEXT,
        clicks INTEGER DEFAULT 0,
        created_at TEXT,
        user_id INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= AUTH HELPERS =================
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, email FROM users WHERE id=?", (uid,))
    user = c.fetchone()
    conn.close()
    return user

# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (email, password) VALUES (?,?)",
                      (email, password))
            conn.commit()
        except:
            return "User exists"

        conn.close()
        return redirect("/login")

    return """
    <form method='POST'>
        <input name='email' placeholder='email'/>
        <input name='password' type='password'/>
        <button>Register</button>
    </form>
    """

# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=? AND password=?",
                  (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect("/")

        return "Invalid login"

    return """
    <form method='POST'>
        <input name='email'/>
        <input name='password' type='password'/>
        <button>Login</button>
    </form>
    """

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= CREATE LINK =================
@app.post("/create")
def create():
    if not current_user():
        return redirect("/login")

    url = request.form.get("url", "").strip()
    if not url:
        return "Missing URL", 400

    token = secrets.token_urlsafe(6)
    now = datetime.utcnow().isoformat()
    uid = current_user()[0]

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO links (token, url, first_click, clicks, created_at, user_id)
        VALUES (?, ?, NULL, 0, ?, ?)
    """, (token, url, now, uid))

    conn.commit()
    conn.close()

    return render_template("result.html", link=request.host_url + token)

# ================= DASHBOARD =================
@app.route("/")
def index():
    user = current_user()
    if not user:
        return redirect("/login")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT token, url, first_click, clicks, created_at
        FROM links
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (user[0],))

    links = c.fetchall()
    conn.close()

    return render_template("index.html", links=links)

# ================= VISIT LINK =================
@app.route("/<token>")
def visit(token):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT url, first_click, clicks FROM links WHERE token=?", (token,))
    row = c.fetchone()

    if not row:
        return "Invalid link", 404

    url, first_click, clicks = row
    clicks = (clicks or 0) + 1

    if first_click is None:
        first_click = datetime.utcnow().isoformat()

    c.execute("""
        UPDATE links
        SET first_click=?, clicks=?
        WHERE token=?
    """, (first_click, clicks, token))

    conn.commit()
    conn.close()

    first_time = datetime.fromisoformat(first_click)

    if datetime.utcnow() > first_time + timedelta(days=14):
        return "<h2>Interview Link Expired</h2>"

    return redirect(url)

# ================= GLOBAL STATS =================
@app.route("/api/stats")
def stats():
    user = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (user[0],))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM links WHERE user_id=? AND first_click IS NOT NULL", (user[0],))
    clicked = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM links WHERE user_id=? AND first_click IS NULL", (user[0],))
    active = c.fetchone()[0]

    c.execute("SELECT SUM(clicks) FROM links WHERE user_id=?", (user[0],))
    clicks = c.fetchone()[0] or 0

    conn.close()

    return jsonify({
        "total_links": total,
        "clicked_links": clicked,
        "active_links": active,
        "total_clicks": clicks
    })

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)