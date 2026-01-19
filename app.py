# imports
import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, send_from_directory, current_app
from dotenv import load_dotenv
from db import init_db, get_conn
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime
from utils.pdf_gen import generate_np_pdf
from pdf_tools import fill_pdf_form


# read .env file (environment file) and get values from it
load_dotenv()

app = Flask(__name__)

# for later use in image uploads
UPLOAD_DIR = Path("static/uploads/reviews")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_MB = 8

PDF_TEMPLATE = Path("static/uploads/forms/NP_form.pdf")
FILLED_DIR = Path("filled_forms")
FILLED_DIR.mkdir(parents=True, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024  # 8MB limit

# Get value of variable named FLASK_SECRET_KEY from .env file
# otherwise the default string
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

with open("clinic_info.json", "r", encoding="utf-8") as f:
    CLINIC = json.load(f)   # convert json data into a dict in python

# Initialize DB on startup
init_db()

#----------------------------
#-------Reviews uploads------
#----------------------------
# Check if file is an image
def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def list_review_images():
    if not UPLOAD_DIR.exists():
        return []
    files = []
    for p in sorted(UPLOAD_DIR.iterdir()):
        if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_EXTENSIONS:
            files.append(p.name)
    return files

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



CONDITION_MAP = {
    "AIDS/HIV +": "heath_AIDS",
    "Alzheimer's Disease": "heath_Alzheimer",
    "Anemia": "health_Anemia",
    "Arthritis/Gout": "health_Arthritis",
    "Artificial Heart Valve": "health_AHV",
    "Artificial Joint": "health_Artificial-joint",
    "Asthma": "health_Asthma",
    "Blood Disease": "health_Blood-disease",
    "Blood Transfusion": "health_Blood-transfusion",
    "Cancer": "health_Cancer",
    "Chest Pains": "health_Chest-pains",
    "Circulatory Problems": "heath_Circulatory-problem",
    "Cortisone Medicine": "heath_Cortisone",
    "Diabetes": "heath_Diabetes",
    "Epilepsy or Seizures": "heath_Epilepsy",
    "Fainting": "heath_Fainting",
    "Glaucoma": "heath_Glaucoma",
    "Heart Attack/Failure": "heath_Heart-attack",
    "Heart Murmur": "heath_Heart-murmur",
    "Heart Pacemaker": "heath_Heart-pacemaker",
    "Heart Disease": "heath_Heart-disease",
    "Hemophilia": "heath_Hemophilia",
    "Hepatitis": "heath_Hepatitis",
    "High Blood Pressure": "heath_HBP",
    "High Cholesterol": "heath_HC",
    "Hypoglycemia": "heath_Hypoglycemia",
    "Jaw pain / TMJ": "heath_TMJ",
    "Kidney Problems": "heath_Kidney-problems",
    "Leukemia": "heath_Leukemia",
    "Liver Disease": "heath_Liver-disease",
    "Low Blood Pressure": "heath_LBP",
    "Lung Disease": "heath_Lung-disease",
    "Osteoporosis": "heath_Osteoporosis",
    "Radiation Treatments": "heath_Radiation-treatment",
    "Renal Dialysis": "heath_Renal-dialysis",
    "Rheumatic Fever": "heath_Rheumatic-fever",
    "Scarlet Fever": "heath_Scarlet-fever",
    "Sickle Cell Disease": "heath_Sickle-cell",
    "Sinus Trouble": "heath_Sinus-trouble",
    "Stroke": "heath_Stroke",
    "Thyroid Disease": "heath_Thyroid-disease",
    "Tonsillitis": "heath_Tonsillitis",
    "Tuberculosis": "heath_Tuberculosis",
    "Ulcers": "heath_Ulcers",
}

@app.get("/new-patients")
def new_patients():
    return render_template("new_patients.html", clinic=CLINIC, success=False)

@app.post("/new-patients")
def new_patients_submit():
    form = request.form
    try:
        pdf_fields = {
            # Patient info
            "pt-firstname": form.get("p_first", ""),
            "pt-lastname": form.get("p_last", ""),
            "pt-midname": form.get("p_mi", ""),
            "pt-address": form.get("p_address", ""),
            "pt-city": form.get("p_city", ""),
            "pt-state": form.get("p_state", ""),
            "pt-zipcode": form.get("p_zip", ""),
            "pt-cellphone": form.get("p_cell_phone", ""),
            "pt-alt-phone": form.get("p_alt_phone", ""),
            "pt-dob": form.get("p_dob", ""),
            "pt-email": form.get("p_email", ""),

            # Radios
            "sex": form.get("p_sex", ""),
            "marital-status": form.get("p_marital", ""),

            # Medical
            "serious-illness": form.get("m_serious", ""),
            "phen-fen": form.get("m_phenfen", ""),
            "pregnant": form.get("w_pregnant", ""),
            "contraceptives": form.get("w_ocp", ""),
            "nursing": form.get("w_nursing", ""),

            # Textareas
            "pt-medications": form.get("m_meds", ""),
            "pt-allergies": form.get("m_allergies", ""),

            # Signatures
            "pt-med-sig": form.get("sig_med", ""),
            "pt-med-date": form.get("sig_med_date", ""),

            # Insurance
            "sub-name": form.get("pi_subscriber", ""),
            "sub-ID": form.get("pi_member_id", ""),
            "sub-group": form.get("pi_group", ""),
            "sub-dob": form.get("pi_dob", ""),
            "sub-ins-name": form.get("pi_company", ""),
            "sub-sig-name": form.get("sig_ins_name", ""),
            "sub-signature": form.get("sig_ins", ""),
            "sub-sig-rel": form.get("pi_rel", ""),
            "sub-relationship": form.get("pi_rel", ""),
            "sub-sig-date": form.get("sig_ins_date", ""),
        }

        # Handle condition checkboxes
        for condition in form.getlist("m_conditions"):
            pdf_field = CONDITION_MAP.get(condition)
            if pdf_field:
                pdf_fields[pdf_field] = "Yes"  # or "On" if your PDF uses On

        # File name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{form.get('p_last','Patient')}_{form.get('p_first','')}"
        output_pdf = FILLED_DIR / f"{safe_name}_{timestamp}.pdf"

        fill_pdf_form(
            input_pdf=PDF_TEMPLATE,
            output_pdf=output_pdf,
            field_values=pdf_fields
        )

        return render_template("new_patients.html", clinic=CLINIC, success=True)

    except Exception as e:
        return render_template("new_patients.html", clinic=CLINIC, error=str(e))


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

@app.get("/reviews")
def reviews_page():
    images = list_review_images()
    return render_template("reviews.html", clinic=CLINIC, images=images)



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

@app.get("/admin/reviews")
def admin_reviews_get():
    require_admin()
    images = list_review_images()
    return render_template("admin_reviews.html", clinic=CLINIC, images=images)

@app.post("/admin/reviews/uploads")
def admin_reviews_upload():
    require_admin()

    if "image" not in request.files:
        return redirect(url_for("admin_reviews_get"))
    
    file = request.files["images"]
    if not file or file.filename == "":
        return redirect(url_for("admin_reviews_get"))
    
    if not allowed_file(file.filename):
        return render_template(
            "admin_reviews.html",
            clinic=CLINIC,
            images=list_review_images(),
            error="Only PNG, JPG, JPEG, or WEBP files are allowed."
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe = secure_filename(file.filename)   #remove weird characters

    # Avoid overwriting existing files:
    dest = UPLOAD_DIR / safe
    if dest.exists():
        stem = dest.stem
        ext = dest.suffix
        i = 2
        while (UPLOAD_DIR / f"{stem}-{i}{ext}").exists():
            i += 1
            dest = UPLOAD_DIR / f"{stem}-{i}{ext}"
    file.save(dest)
    return redirect(url_for("admin_reviews_get"))

@app.post("/admin/reviews/delete/<filename>")
def admin_reviews_delete(filename: str):
    require_admin()
    safe = secure_filename(filename)
    target = UPLOAD_DIR / safe

    # Safety check: ensure delete stays inside the upload folder
    if target.exists() and target.is_file():
        target.unlink()
    
    return redirect(url_for("admin_reviews_get"))

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
        "patterns": ["hour", "hours", "open", "opening"],
        "response": lambda: (
            "Our hours are: " +
            ", ".join(f"\n{day}: {hrs}" for day, hrs in CLINIC["hours"].items())
        )
    },
        {
        "name": "email",
        "patterns": ["email"],
        "response": lambda: f"Our email address is: {CLINIC['email']}"
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
        "response": lambda: CLINIC['insurance']
    },
    {
        "name": "implants",
        "patterns": ["implant", "implants"],
        "response": lambda: CLINIC["implant"]
    },
    {
        "name": "services",
        "patterns": [
            "service","services", "treatments", "what do you offer",
            "what services", "procedures"
        ],
        "response": lambda: (
            "We offer the following services:\n- " +
            "\n- ".join(CLINIC["services"])
        )
    },
    {
        "name": "appointment",
        "patterns": [
            "appointment", "book", "schedule", "scheduled",
            "visit", "see the dentist", "consult", "consultation"
        ],
        "response": lambda: ('To request an appointment, please use our <a href="/contact" target="_blank">Contact</a> page. '
                             'If your prefer, you can also call the office.')
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
    
    return jsonify({"reply": "Here is what I can help you with: \n- hours\n- location\n- services\n- insurance info\n- appointment requests"})

if __name__ == "__main__":
    app.run(debug=True)