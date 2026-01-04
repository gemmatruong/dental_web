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

@app.get("/admin/requests")
def admin_requests():
    require_admin()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM appointment_requests ORDER BY created_at DESC LIMIT 50
        """).fetchall()
    return render_template("admin_requests.html", clinic=CLINIC, rows=rows)

@app.post("/admin/requests/<int:req_id>/status")
def admin_update_status(req_id: int):
    require_admin()
    new_status = request.form.get("status", "new")
    if new_status not in ("new", "contacted", "closed"):
        new_status = "new"
    
    with get_conn() as conn:
        conn.execute("UPDATE appointment_requests SET status=? WHERE id=?", (new_status, req_id))
        conn.commit()
    
    return redirect(url_for("admin_requests"))

@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login_get"))

#------------------------------
# CHATBOT safety + FAQ fallback
#------------------------------
EMERGENCY_KEYWORDS = [
    "uncontrolled bleeding", "bleeding won't stop", "can't stop bleeding", "bleeding a lot",
    "can't breathe", "difficulty breathing", "trouble breathing", "hard to breathe",
    "trouble swallowing", "difficulty swallowing", "choking",
    "severe pain", "fever", "severe swelling", "facial swelling", "constant pain", "dying"
]

def is_emergency(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in EMERGENCY_KEYWORDS)

FAQ = [
    {
        "name": "hours",
        "patterns": ["hour", "hours", "schedule", "open", "opening"],
        "response": lambda: (
            "Our hours are: " +
            ", ".join(f"{day}: {hrs}" for day, hrs in CLINIC["hours"].items())
        )
    },
    {
        "name": "location",
        "patterns": [
            "address", "location",
            "where is the office", "where's the office",
            "where is your office", "where's your office"
        ],
        "response": lambda: f"Our address is {CLINIC['address']}."
    },
    {
        "name": "phone",
        "patterns": ["phone", "call", "number", "contact"],
        "response": lambda: f"You can call us at {CLINIC['phone']}."
    },
    {
        "name": "insurance",
        "patterns": ["insurance", "coverage", "accept insurance"],
        "response": lambda: CLINIC["insurance"]
    },
    {
        "name": "implants",
        "patterns": ["implant", "implants"],
        "response": lambda: CLINIC["implant_note"]
    },
    {
        "name": "services",
        "patterns": [
            "services", "treatments", "what do you offer",
            "what services", "procedures"
        ],
        "response": lambda: (
            "We offer the following services:\n- " +
            "\n- ".join(CLINIC["services"])
        )
    }
]

def faq_reply(msg: str):
    m = msg.lower()
    for intent in FAQ:
        for pattern in intent["patterns"]:
            if pattern in m:
                return intent
    return None

@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type the question and I'll help."})
    
    # Emergency
    if is_emergency(user_msg):
        return jsonify({"reply": 
            f"If this is urgent, please call us immediately at {CLINIC['phone']}. "
            "If you have uncontrolled bleeding, trouble breathing/swallowing or severe pain and swelling, please go to urgent care!"
        })
    
    # Medical advice guardrail
    diagnosis = any(w in user_msg.lower() for w in [
        "do i have", "should i", "is this", "am i", "infected", "infection", "swollen", "pus"
    ])

    if diagnosis:
        return jsonify({"reply": 
            "I can't provide medical advice or diagnosis. "
            f"If you're concerned, please call us at {CLINIC['phone']} to make appointment for an exam."
            "I can also help submit an appointment request from the Contact page."
        })
    
    # FAQ fallback
    ans = faq_reply(user_msg)
    if ans:
        return jsonify({"reply": ans['response']()})
    
    return jsonify({"reply": "Here is what I can help you with: "
        "\n- hours"
        "\n- location"
        "\n- services"
        "\n- insurance info"
        "\n- appointment requests"
        "\nHow can I help you?"
    })

if __name__ == "__main__":
    app.run(debug=True)