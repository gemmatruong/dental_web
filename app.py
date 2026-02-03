# imports
import os
import json
import time
import logging
from groq import Groq
from pathlib import Path
from functools import wraps
from pdf_tools import fill_pdf
from dotenv import load_dotenv
from db import init_db, get_conn
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, send_from_directory, current_app


# read .env file (environment file) and get values from it
load_dotenv()

app = Flask(__name__)

# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('admin_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Helper Functions for Email and Security
def send_password_reset_email(email, token):
    """Send password reset email"""
    try:
        reset_url = url_for('admin_reset_password_get', token=token, _external=True)
        
        msg = Message(
            subject=f"{CLINIC['office_name']} - Password Reset Request",
            recipients=[email],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #4682B4, #83c9f4); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="color: white; margin: 0;">Password Reset Request</h1>
                        </div>
                        
                        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                            <p>Hello,</p>
                            
                            <p>We received a request to reset your admin password for <strong>{CLINIC['office_name']}</strong>.</p>
                            
                            <p>Click the button below to reset your password:</p>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_url}" 
                                   style="background: linear-gradient(135deg, #4682B4, #83c9f4); 
                                          color: white; 
                                          padding: 15px 40px; 
                                          text-decoration: none; 
                                          border-radius: 50px; 
                                          display: inline-block;
                                          font-weight: bold;">
                                    Reset Password
                                </a>
                            </div>
                            
                            <p>Or copy and paste this link into your browser:</p>
                            <p style="word-break: break-all; background: white; padding: 10px; border-radius: 5px; font-size: 12px;">
                                {reset_url}
                            </p>
                            
                            <p style="color: #dc3545; font-weight: bold;">This link will expire in 1 hour.</p>
                            
                            <p>If you didn't request this password reset, please ignore this email or contact your system administrator.</p>
                            
                            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                            
                            <p style="font-size: 12px; color: #666;">
                                This is an automated message from {CLINIC['office_name']}.<br>
                                Please do not reply to this email.
                            </p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        
        mail.send(msg)
        logger.info(f"Password reset email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        return False

def log_admin_action(action, details=""):
    """Enhanced logging with user agent"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO admin_audit_log (action, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?)
            """, (action, details, request.remote_addr, request.headers.get('User-Agent', 'Unknown')))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log admin action: {str(e)}")

def cleanup_expired_tokens():
    """Remove expired password reset tokens"""
    try:
        with get_conn() as conn:
            result = conn.execute("""
                DELETE FROM password_reset_tokens 
                WHERE expires_at < CURRENT_TIMESTAMP OR used = 1
            """)
            conn.commit()
            if result.rowcount > 0:
                logger.info(f"Cleaned up {result.rowcount} expired/used tokens")
    except Exception as e:
        logger.error(f"Failed to cleanup tokens: {str(e)}")

def get_admin_password_hash():
    """Get admin password hash from database or environment"""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT password_hash FROM admin_credentials WHERE id=1"
            ).fetchone()
            
            if row:
                return row['password_hash']
    except Exception as e:
        logger.error(f"Database error getting password hash: {str(e)}")
    
    # Fallback to environment variable
    return os.environ.get("ADMIN_PASSWORD_HASH")

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Configure Groq
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

# Turn on CSFR globally protection
csrf = CSRFProtect(app)

# Secure session cookies
app.config.update(
    SESSION_COOKIE_SECURE=True,       # Only send over HTTPS
    SESSION_COOKIE_HTTPONLY=True,     # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE='Lax',    # CSRF protection
)

# Load clinic info from JSON
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
        if attempts >= 5 and time.time() - last_time < 900:  # 15 min lockout
            return render_template("admin_login.html", clinic=CLINIC, 
                                   error="Too many failed attempts. Try again in 5 minutes.")
    
    # Get HASHED password from environment
    stored_hash = get_admin_password_hash()
    
    if not stored_hash:
        app.logger.error("ADMIN_PASSWORD_HASH not set!")
        abort(500)
    
    if password and check_password_hash(stored_hash, password):
        session["is_admin"] = True
        session["last_activity"] = datetime.now().isoformat()
        session.permanent = True

        # Clear failed attempts on success
        failed_attempts.pop(ip, None)

        log_admin_action("LOGIN_SUCCESS", f"Successful login from {ip}")
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

@app.post("/admin/requests/<int:req_id>/delete")
def admin_delete_request(req_id: int):
    require_admin()
    
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM appointment_requests WHERE id=?", (req_id,)).fetchone()

        if row:
            conn.execute("DELETE FROM appointment_requests WHERE id=?", (req_id, ))
            conn.commit()
            logging.info(f"Admin deleted appointment request #{req_id} - {row['name']} from IP {request.remote_addr}")
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

# Helper to build context for AI chatbot
def build_website_context():
    """Build comprehensive website context for AI"""
    return f"""
=== CLINIC INFORMATION ===
Name: {CLINIC['name']}
Address: {CLINIC['address']}
Phone: {CLINIC['phone']}
Email: {CLINIC['email']}

=== OFFICE HOURS ===
{chr(10).join(f'{day}: {hrs}' for day, hrs in CLINIC['hours'].items())}

=== SERVICES ===
{chr(10).join(f'• {service}' for service in CLINIC['services'])}

=== INSURANCE ===
{CLINIC['insurance']}

=== DENTAL IMPLANTS ===
{CLINIC['implant']}

=== NEW PATIENT INFO ===
We welcome new patients! Our new patient form can be filled out online at /new-patients
Please bring:
- Valid ID
- Insurance card (if applicable)  
- List of current medications
- Medical history information

=== APPOINTMENT REQUESTS ===
Patients can request appointments:
1. Online through our Contact page: /contact
2. By phone: {CLINIC['phone']}

We typically respond to online requests within 24 hours.

=== REVIEWS ===
See what our patients are saying on our Reviews page: /reviews

=== EMERGENCY PROTOCOL ===
For dental emergencies including:
- Uncontrolled bleeding
- Difficulty breathing or swallowing
- Severe pain or swelling
- Facial trauma
Please call {CLINIC['phone']} immediately or go to the nearest urgent care/ER.
"""

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
                             'If you prefer, you can also call the office.')
    }
]

def faq_reply(msg: str):
    """Fallback FAQ system if AI fails"""
    m = msg.lower()
    for intent in FAQ:
        for pattern in intent["patterns"]:
            if pattern in m:
                return intent
    return None

def build_website_context():
    """Build comprehensive website context for AI"""
    
    # Extract services list with descriptions
    services_text = []
    for service in CLINIC['services']:
        services_text.append(f"• {service['name']}: {service['description']}")
    
    # Extract dentist information
    dentists_text = []
    for dentist in CLINIC.get('dentists', []):
        specialties = ", ".join(dentist.get('specialties', []))
        dentists_text.append(
            f"- {dentist['name']}, {dentist.get('title', 'DDS')}\n"
            f"  Specialties: {specialties}\n"
            f"  {dentist.get('bio', '')}"
        )
    
    return f"""
=== CLINIC INFORMATION ===
Name: {CLINIC['office_name']}
Address: {CLINIC['address']}
Phone: {CLINIC['phone']}
Email: {CLINIC['email']}
Fax: {CLINIC.get('fax', '')}

=== OFFICE HOURS ===
{chr(10).join(f'{day}: {hrs}' for day, hrs in CLINIC['hours'].items())}

=== OUR DENTISTS ===
{chr(10).join(dentists_text)}

=== SERVICES WE OFFER ===
{chr(10).join(services_text)}

=== INSURANCE INFORMATION ===
{CLINIC['insurance']}

=== DENTAL IMPLANTS ===
{CLINIC['implant']}

=== NEW PATIENT INFORMATION ===
We welcome new patients! Our new patient form can be filled out online at /new-patients
Please bring:
- Valid ID
- Insurance card (if applicable)  
- List of current medications
- Medical history information

=== APPOINTMENT REQUESTS ===
Patients can request appointments:
1. Online through our Contact page: /contact
2. By phone: {CLINIC['phone']}

We typically respond to online requests within 24 hours.

=== REVIEWS ===
See what our patients are saying on our Reviews page: /reviews

=== EMERGENCY PROTOCOL ===
For dental emergencies including:
- Uncontrolled bleeding
- Difficulty breathing or swallowing
- Severe pain or swelling
- Facial trauma
Please call {CLINIC['phone']} immediately or go to the nearest urgent care/ER.
"""

# Rate limiting for chatbot
chat_rate_limits = {}

def rate_limit_chat(max_per_minute=20):
    """Rate limit chatbot requests to prevent abuse"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            # Clean old entries (older than 60 seconds)
            chat_rate_limits[ip] = [t for t in chat_rate_limits.get(ip, []) if now - t < 60]
            
            # Check limit
            if len(chat_rate_limits.get(ip, [])) >= max_per_minute:
                return jsonify({
                    "reply": "Please wait a moment before sending another message. 😊"
                }), 429
            
            # Record this request
            chat_rate_limits.setdefault(ip, []).append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.post("/api/chat")
@rate_limit_chat(max_per_minute=20)
def api_chat():
    """AI-powered chatbot endpoint using Groq AI"""
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type a question and I'll help you! 😊"})
    
    # Emergency check - immediate response (bypasses AI)
    if is_emergency(user_msg):
        return jsonify({"reply": 
            f"⚠️ <strong>If this is urgent, please call us immediately at {CLINIC['phone']}.</strong><br><br>"
            "If you have uncontrolled bleeding, trouble breathing/swallowing, or severe pain and swelling, "
            "please go to urgent care or the ER right away!"
        })
    
    # Try AI response with Groq
    try:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured - falling back to FAQ")
        
        # Build system message with all context
        system_message = f"""You are a helpful, friendly assistant for {CLINIC['office_name']}, a dental office in Anaheim, California.

{build_website_context()}

RESPONSE GUIDELINES:
1. Be warm, friendly, and professional - talk like a helpful receptionist
2. Keep responses concise (2-3 sentences unless more detail is specifically requested)
3. NEVER provide medical diagnoses or treatment recommendations - you're not a dentist
4. For any health/medical concerns or symptoms, recommend calling the office at {CLINIC['phone']} to speak with a dentist or scheduling an appointment
5. For emergency symptoms (severe pain, uncontrolled bleeding, facial swelling, breathing/swallowing difficulty), immediately tell them to call {CLINIC['phone']} or go to urgent care/ER
6. Use HTML links when helpful:
   - <a href="/contact">Contact page</a> for appointment requests
   - <a href="/new-patients">New Patient form</a> for new patients
   - <a href="/services">Services page</a> for service details
   - <a href="/reviews">Reviews page</a> to see testimonials
   - <a href="/implants">Implants page</a> for implant information
7. Only answer questions about Union Dental Group, our services, policies, and general dental care information
8. If asked about something not in your knowledge base, politely say you don't have that specific information and suggest calling the office at {CLINIC['phone']}
9. Stay in character as a helpful dental office assistant - be conversational and personable
10. Don't use emojis excessively - one or two per response is enough
11. When discussing our dentists, mention their specialties: Dr. Kim specializes in implant surgery, dentures, and braces; Dr. Do is known for gentle dentistry and excellent root canal treatment
12. We accept most PPO insurance and Denti-Cal (Medi-Cal) - always suggest patients call to verify their specific coverage

Remember: Answer based ONLY on the information provided above. Be helpful, accurate, and always prioritize patient safety.
"""
        
        # Generate response using Groq
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_msg
                }
            ],
            model="llama-3.3-70b-versatile",  # Fast, accurate, and FREE!
            temperature=0.7,
            max_tokens=400,
            top_p=0.9,
            stream=False
        )
        
        # Get the AI response
        reply = chat_completion.choices[0].message.content
        
        # Log successful AI response (optional)
        app.logger.info(f"AI chat - User: {user_msg[:50]}... | Response: {reply[:50]}...")
        
        return jsonify({"reply": reply})
        
    except Exception as e:
        # Log the error
        app.logger.error(f"Groq AI chat error: {str(e)}")
        
        # Fallback to FAQ system if AI fails
        ans = faq_reply(user_msg)
        if ans:
            app.logger.info(f"Falling back to FAQ for: {user_msg[:50]}...")
            return jsonify({"reply": ans['response']()})
        
        # Ultimate fallback - generic helpful message
        return jsonify({"reply": 
            "I'm having trouble connecting to my knowledge base right now. 😅<br><br>"
            "I can help with: hours, location, services, insurance info, and appointment requests.<br><br>"
            f"Or you can call us directly at <strong>{CLINIC['phone']}</strong> and we'll be happy to help!"
        })


if __name__ == "__main__":
    # Verify Groq AI configuration on startup
    if GROQ_API_KEY:
        print("✓ Groq API Key configured")
        try:
            groq_client = Groq(api_key=GROQ_API_KEY)
            print("✓ Groq AI initialized successfully")
        except Exception as e:
            print(f"✗ Groq AI initialization error: {e}")
    else:
        print("⚠ GROQ_API_KEY not found - chatbot will use FAQ fallback only")
    
    app.run(debug=True)