from flask import Flask, request, redirect, render_template
import json, os, secrets
from datetime import datetime, timedelta

app = Flask(__name__)
DB = "links.json"

def load():
    if not os.path.exists(DB):
        return {}
    return json.load(open(DB))

def save(data):
    json.dump(data, open(DB, "w"), indent=2)

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/create")
def create():
    data = load()

    url = request.form.get("url", "").strip()
    if not url:
        return "Missing URL", 400

    token = secrets.token_urlsafe(5)

    data[token] = {
        "url": url,
        "first": None
    }

    save(data)

    full_link = request.host_url + token

    return render_template("result.html", link=full_link)

@app.route("/<token>")
def visit(token):
    data = load()

    if token not in data:
        return "Invalid link", 404

    entry = data[token]

    if entry["first"] is None:
        entry["first"] = datetime.utcnow().isoformat()
        save(data)

    first = datetime.fromisoformat(entry["first"])

    if datetime.utcnow() > first + timedelta(days=14):
        return "<h2>Interview Link Expired</h2>"

    return redirect(entry["url"])

if __name__ == "__main__":
    app.run(debug=True)