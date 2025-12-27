# imports
import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from dotenv import load_dotenv
from db import init_db, get_conn

# read .env file (environment file) and get values from it
load_dotenv()

app = Flask(__name__)

# Get value of variable named FLASK_SECRET_KEY from .env file
# otherwise the default string
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

with open("clinic_info.json", "r", encoding="utf-8") as f:
    CLINIC = json.load(f)   # convert json data into a dict in python

# Initialize DB on startup
init_db()

#----------------------------
#-------WEBSITE PAGES--------
#----------------------------
@app.get("/")
def home():
    return render_template("home.html", clinic=CLINIC)

@app.get("/services")
def services():
    return render_template("services.html", clinic=CLINIC)

@app.get("/implants")
def implants():
    return render_template("implants.html", clinic=CLINIC)

@app.get("/new-patients")
def new_patients():
    return render_template("new_patients.html", clinic=CLINIC)

@app.get("/contact")
def contact_get():
    return render_template("contact.html", clinic=CLINIC, success=False)

@app.post("/contact")
def contact_post():
    name = request.form.get("name", "").strip()
    contact = request.form.get("contact", "").strip()
    preferred_times = request.form.get("preferred_times", "").strip()
    service = request.form.get("service", "").strip()
    note = request.form.get("note", "").strip()

    if not name or not contact or not preferred_times or not service:
        return render_template(
            "contact.html",
            clinic=CLINIC,
            success=False,
            error="Please fill all required fields."
        )
    conn = get_conn()
    conn.execute("""
        INSERT INTO appointment_requests(name, contact, preferred_times, service, note)
        VALUES(?, ?, ?, ?, ?)
    """, (name, contact, preferred_times, service, note))
    conn.commit()
    conn.close()
    return render_template("contact.html", clinic=CLINIC, success=True)

#----------------------------
#-------ADMIN AUTH-----------
#----------------------------

def require_admin():
    if not session.get("is_admin"):
        abort(403)

@app.get("/admin")
def admin_login_get():
    return render_template("admin_login.html", clinic=CLINIC)

@app.post("/admin")
def admin_login_post():
    password = request.form.get("password", "")
    if password and password == os.environ.get("ADMIN_PASSWORD", "changeme"):
        session["is_admin"] = True
        return redirect(url_for("admin_requests"))
    return render_template("admin_login.html", clinic=CLINIC, error="Incorrect password.")


if __name__ in "__main__":
    app.run(debug=True)