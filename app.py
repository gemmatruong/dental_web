# imports
import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, send_from_directory, current_app
from dotenv import load_dotenv
from db import init_db, get_conn
from pathlib import Path
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import time
from pdf_tools import fill_pdf
from datetime import datetime, timedelta
from flask_wtf.csrf import CSRFProtect
import logging



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

# Turn on CSFR globally protection
csrf = CSRFProtect(app)


# ADD THESE:
app.config.update(
    SESSION_COOKIE_SECURE=True,       # Only send over HTTPS
    SESSION_COOKIE_HTTPONLY=True,     # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE='Lax',    # CSRF protection
)

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


SEX_MAP = {"Male": "1", "Female": "2"}
YESNO_MAP = {"Yes": "1", "No": "2"}
MARITAL_MAP = {"Single":"1","Married":"2","Divorced":"3","Separated":"4","Widowed":"5"}
SUB_REL_MAP = {"Self":"1","Spouse":"2","Child":"3","Other":"4"}


@app.get("/new-patients")
def new_patients():
    return render_template("new_patients.html", clinic=CLINIC, success=False)

@app.post("/new-patients")
def new_patients_submit():
    form = request.form
    try:
        # basic required checks
        p_first = form.get("p_first", "").strip()
        p_last = form.get("p_last", "").strip()
        sig_med = form.get("sig_med", "").strip()
        if not p_first or not p_last:
            return render_template("new_patients.html", clinic=CLINIC, success=False,
                                   error="Patient first and last name are required.")
        if not sig_med:
            return render_template("new_patients.html", clinic=CLINIC, success=False,
                                   error="Medical signature is required.")
        if not form.get("agree"):
            return render_template("new_patients.html", clinic=CLINIC, success=False,
                                   error="You must agree to the policy to submit.")

        # build common text fields
        pdf_fields = {
            "pt-firstname": form.get("p_first", "").strip(),
            "pt-lastname": form.get("p_last", "").strip(),
            "pt-midname": form.get("p_mi", "").strip(),
            "pt-address": form.get("p_address", "").strip(),
            "pt-city": form.get("p_city", "").strip(),
            "pt-state": form.get("p_state", "").strip(),
            "pt-zipcode": form.get("p_zip", "").strip(),
            "pt-cellphone": form.get("p_cell_phone", "").strip(),
            "pt-alt-phone": form.get("p_alt_phone", "").strip(),
            "pt-dob": form.get("p_dob", "").strip(),
            "pt-email": form.get("p_email", "").strip(),
            # textareas
            "pt-medications": form.get("m_meds", "").strip(),
            "pt-allergies": form.get("m_allergies", "").strip(),
            # signature text fields (replace keys if your PDF uses different names)
            "pt-med-sig": sig_med,
            "pt-med-date": form.get("sig_med_date", "").strip() or datetime.now().strftime("%m/%d/%y"),
            # Insurance text fields (adjust RHS to exact PDF text field names if they differ)
            "sub-name": form.get("pi_subscriber", "").strip(),
            "sub-ID": form.get("pi_member_id", "").strip(),
            "sub-group": form.get("pi_group", "").strip(),
            "sub-dob": form.get("pi_dob", "").strip(),
            "sub-ins-name": form.get("pi_company", "").strip(),
            "sub-sig-name": form.get("sig_ins_name", "").strip(),
            "sub-signature": form.get("sig_ins", "").strip(),
            "sub-sig-date": form.get("sig_ins_date", "").strip() or datetime.now().strftime("%m/%d/%y"),
        }

        # radios -> numbers
        if form.get("p_sex") in SEX_MAP:
            pdf_fields["sex"] = SEX_MAP[form.get("p_sex")]
        
        if form.get("p_marital") in MARITAL_MAP:
            pdf_fields["marital-status"] = MARITAL_MAP[form.get("p_marital")]
        
        if form.get("pi_rel") in SUB_REL_MAP:
            pdf_fields["sub-relationship"] = SUB_REL_MAP[form.get("pi_rel")]

        if form.get("m_serious") in YESNO_MAP:
            pdf_fields["serious-illness"] = YESNO_MAP[form.get("m_serious")]

        if form.get("m_phenfen") in YESNO_MAP:
            pdf_fields["phen-fen"] = YESNO_MAP[form.get("m_phenfen")]
        
        if form.get("w_pregnant") in YESNO_MAP:
            pdf_fields["pregnant"] = YESNO_MAP[form.get("w_pregnant")]
        
        if form.get("w_ocp") in YESNO_MAP:
            pdf_fields["contraceptives"] = YESNO_MAP[form.get("w_ocp")]

        if form.get("w_nursing") in YESNO_MAP:
            pdf_fields["nursing"] = YESNO_MAP[form.get("w_nursing")]

        # checkboxes -> Yes
        for condition in form.getlist("m_conditions"):
            pdf_fields[condition] = "Yes"

        pdf_fields = {k: v for k,v in pdf_fields.items() if str(v).strip()}

        # File name + output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{form.get('p_last','Patient')}_{form.get('p_first','')}"
        safe_name = secure_filename(safe_name) or "patient"
        output_pdf = FILLED_DIR / f"{safe_name}_{timestamp}.pdf"
        
        # fill PDF
        fill_pdf(PDF_TEMPLATE, output_pdf, pdf_fields)

        # TODO: upload to Drive + send notification email (if you want)


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
    
    # Check session timeout (60 minutes)
    last_activity = session.get("last_activity")
    if last_activity:
        last_time = datetime.fromisoformat(last_activity)
        if datetime.now() - last_time > timedelta(minutes=60):
            session.clear()
            abort(403)
    
    # Update last activity
    session["last_activity"] = datetime.now().isoformat()

# Track failed login attempts (simple in-memory, resets on restart)
failed_attempts = {}

@app.get("/admin")
def admin_login_get():
    return render_template("admin_login.html", clinic=CLINIC)

# Track failed login attempts (simple in-memory, resets on restart)
failed_attempts = {}

@app.post("/admin")
def admin_login_post():
    password = request.form.get("password", "")
    ip = request.remote_addr
    
    # Rate limiting: check failed attempts
    if ip in failed_attempts:
        attempts, last_time = failed_attempts[ip]
        if attempts >= 5 and time.time() - last_time < 300:  # 5 min lockout
            return render_template("admin_login.html", clinic=CLINIC, 
                                   error="Too many failed attempts. Try again in 5 minutes.")
    
    # Get HASHED password from environment
    hashed_pw = os.environ.get("ADMIN_PASSWORD_HASH")
    
    if not hashed_pw:
        app.logger.error("ADMIN_PASSWORD_HASH not set!")
        abort(500)
    
    if password and check_password_hash(hashed_pw, password):
        session["is_admin"] = True
        # Clear failed attempts on success
        failed_attempts.pop(ip, None)
        return redirect(url_for("admin_requests"))
    
    # Track failed attempt
    if ip in failed_attempts:
        failed_attempts[ip] = (failed_attempts[ip][0] + 1, time.time())
    else:
        failed_attempts[ip] = (1, time.time())
    
    return render_template("admin_login.html", clinic=CLINIC, 
                           error="Incorrect password.")

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
        return render_template(
            "admin_reviews.html",
            clinic=CLINIC,
            images=list_review_images(),
            error="No file uploaded."
        )
    
    file = request.files["image"]
    
    if not file or file.filename == "":
        return render_template(
            "admin_reviews.html",
            clinic=CLINIC,
            images=list_review_images(),
            error="No file selected."
        )
    
    if not allowed_file(file.filename):
        return render_template(
            "admin_reviews.html",
            clinic=CLINIC,
            images=list_review_images(),
            error="Only PNG, JPG, JPEG, or WEBP files are allowed."
        )
    
    # Add file size validation
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset
    
    if size > app.config["MAX_CONTENT_LENGTH"]:
        return render_template(
            "admin_reviews.html",
            clinic=CLINIC,
            images=list_review_images(),
            error="File too large. Maximum 8MB."
        )
    
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    safe = secure_filename(file.filename)
    if not safe:
        return render_template(
            "admin_reviews.html",
            clinic=CLINIC,
            images=list_review_images(),
            error="Invalid filename."
        )
    
    # Prevent directory traversal
    dest = (UPLOAD_DIR / safe).resolve()
    if not str(dest).startswith(str(UPLOAD_DIR.resolve())):
        abort(403)
    
    # Handle duplicates
    if dest.exists():
        stem = dest.stem
        ext = dest.suffix
        i = 2
        while (UPLOAD_DIR / f"{stem}-{i}{ext}").exists():
            i += 1
        dest = UPLOAD_DIR / f"{stem}-{i}{ext}"
    
    file.save(dest)
    return redirect(url_for("admin_reviews_get"))


# Configure logging
logging.basicConfig(
    filename='admin_audit.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@app.post("/admin/reviews/delete/<filename>")
def admin_reviews_delete(filename: str):
    require_admin()
    safe = secure_filename(filename)
    target = UPLOAD_DIR / safe

    # Safety check: ensure delete stays inside the upload folder
    if target.exists() and target.is_file():
        target.unlink()
        logging.info(f"Admin deleted review image: {safe} from IP {request.remote_addr}")
    
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