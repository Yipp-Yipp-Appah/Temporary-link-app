from flask import Flask, request, redirect, render_template, jsonify, session
import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "temporary-development-key")

DB_FILE = "links.db"


# ---------------- DATABASE ----------------

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'recruiter'
    )
    """)

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


def create_initial_admin():
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")

    if not email or not password:
        return

    conn = db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]

    if count == 0:
    print("Creating initial admin:", email)

    c.execute(
        """
        INSERT INTO users
        (email, password, role)
        VALUES (?, ?, ?)
        """,
            (
                email,
                generate_password_hash(password),
                "superadmin"
            )
        )

        conn.commit()

    conn.close()


init_db()
create_initial_admin()


# ---------------- AUTH ----------------

def current_user():
    uid = session.get("user_id")

    if not uid:
        return None

    conn = db()
    c = conn.cursor()

    c.execute(
        "SELECT id,email,role FROM users WHERE id=?",
        (uid,)
    )

    user = c.fetchone()

    conn.close()

    return user


@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        c.execute(
            "SELECT id,password FROM users WHERE email=?",
            (email,)
        )

        user = c.fetchone()

        conn.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            return redirect("/")

        return "Invalid login"

    return """
    <h2>Login</h2>
    <form method="post">
        Email:<br>
        <input name="email"><br><br>

        Password:<br>
        <input name="password" type="password"><br><br>

        <button>Login</button>
    </form>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



# ---------------- DASHBOARD ----------------

@app.route("/")
def home():

    if not current_user():
        return redirect("/login")

    return render_template(
        "index.html",
        user=current_user()
    )



# ---------------- CREATE LINK ----------------

@app.post("/create")
def create():

    user = current_user()

    if not user:
        return redirect("/login")


    url = request.form.get("url","").strip()

    if not url:
        return "Missing URL",400


    token = secrets.token_urlsafe(6)


    conn = db()
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO links
        (
        token,
        url,
        first_click,
        clicks,
        created_at,
        user_id
        )
        VALUES (?,?,?,?,?,?)
        """,
        (
            token,
            url,
            None,
            0,
            datetime.utcnow().isoformat(),
            user[0]
        )
    )

    conn.commit()
    conn.close()


    full_link = request.host_url + token

    return render_template(
        "result.html",
        link=full_link
    )



# ---------------- VISIT LINK ----------------

@app.route("/<token>")
def visit(token):

    conn = db()
    c = conn.cursor()


    c.execute(
        """
        SELECT url,first_click,clicks
        FROM links
        WHERE token=?
        """,
        (token,)
    )


    row = c.fetchone()


    if not row:
        conn.close()
        return "Invalid link",404


    url,first_click,clicks=row


    if first_click is None:

        first_click=datetime.utcnow().isoformat()


    clicks += 1


    c.execute(
        """
        UPDATE links
        SET first_click=?, clicks=?
        WHERE token=?
        """,
        (
            first_click,
            clicks,
            token
        )
    )


    conn.commit()
    conn.close()


    first=datetime.fromisoformat(first_click)


    if datetime.utcnow() > first + timedelta(days=14):
        return "<h2>Interview Link Expired</h2>"


    return redirect(url)



# ---------------- ANALYTICS ----------------

@app.get("/api/stats")
def stats():

    user=current_user()

    if not user:
        return jsonify({"error":"not logged in"}),401


    conn=db()
    c=conn.cursor()


    c.execute(
        """
        SELECT COUNT(*)
        FROM links
        WHERE user_id=?
        """,
        (user[0],)
    )

    total=c.fetchone()[0]


    c.execute(
        """
        SELECT SUM(clicks)
        FROM links
        WHERE user_id=?
        """,
        (user[0],)
    )

    clicks=c.fetchone()[0] or 0


    conn.close()


    return jsonify({
        "links":total,
        "clicks":clicks
    })



if __name__=="__main__":

    port=int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )