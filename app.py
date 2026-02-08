"""
Flask Application for Dental Clinic Website
Features: Appointment Request, New patient forms, Admin panel, AI Chatbot
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from groq import Groq

# Import our modules
from db import init_db, get_conn, seed_admin_user, USE_POSTGRES
from auth import (
    require_admin, log_admin_action, check_rate_limit, record_failed_login,
    clear_failed_logins, rate_limit_chat, create_password_reset_token,
    verify_reset_token, mark_token_as_used, cleanup_expired_tokens,
    get_admin_by_email, update_admin_password, verify_admin_password
)
from email_utils import (
    send_password_reset_email, send_password_changed_notification,
    send_appointment_notification
)
from pdf_tools import fill_pdf

# Load environment variables
load_dotenv()

# ============================================================================
# APP CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

# File Upload Configuration
UPLOAD_DIR = Path("static/uploads/reviews")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_MB = 8
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# PDF Form Configuration
PDF_TEMPLATE = Path("static/uploads/forms/NP_form.pdf")
FILLED_DIR = Path("filled_forms")
FILLED_DIR.mkdir(parents=True, exist_ok=True)

# Secure session cookies
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# Initialize extensions
mail = Mail(app)
csrf = CSRFProtect(app)

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

# Load clinic info
with open("clinic_info.json", "r", encoding="utf-8") as f:
    CLINIC = json.load(f)

# Initialize Groq AI
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq AI initialized")
else:
    logger.warning("GROQ_API_KEY not found - chatbot will use FAQ fallback")

# Initialize database
init_db()
seed_admin_user()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def list_review_images():
    """Get list of review images"""
    if not UPLOAD_DIR.exists():
        return []
    files = []
    for p in sorted(UPLOAD_DIR.iterdir()):
        if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_EXTENSIONS:
            files.append(p.name)
    return files


# ============================================================================
# PUBLIC PAGES
# ============================================================================

@app.route("/")
def home():
    """Home page"""
    return render_template("home.html", clinic=CLINIC)


@app.route("/services")
def services():
    """Services page"""
    return render_template("services.html", clinic=CLINIC)


@app.route("/implants")
def implants():
    """Dental implants page"""
    return render_template("implants.html", clinic=CLINIC)


@app.route("/reviews")
def reviews_page():
    """Reviews page"""
    images = list_review_images()
    return render_template("reviews.html", clinic=CLINIC, images=images)


# ============================================================================
# CONTACT & APPOINTMENT REQUESTS
# ============================================================================

@app.route("/contact", methods=["GET"])
def contact_get():
    """Contact page - GET"""
    return render_template("contact.html", clinic=CLINIC, success=False)


@app.route("/contact", methods=["POST"])
def contact_post():
    """Contact page - POST (appointment request)"""
    name = request.form.get("name", "").strip()
    contact = request.form.get("contact", "").strip()
    preferred_times = request.form.get("preferred_times", "").strip()
    service = request.form.get("service", "").strip()
    note = request.form.get("note", "").strip()

    # Validation
    if not name or not contact or not preferred_times or not service:
        return render_template(
            "contact.html",
            clinic=CLINIC,
            success=False,
            error="Please fill all required fields."
        )
    
    # Save to database
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO appointment_requests(name, contact, preferred_times, service, note)
                    VALUES(%s, %s, %s, %s, %s)
                """, (name, contact, preferred_times, service, note))
            else:
                cursor.execute("""
                    INSERT INTO appointment_requests(name, contact, preferred_times, service, note)
                    VALUES(?, ?, ?, ?, ?)
                """, (name, contact, preferred_times, service, note))
            conn.commit()
        
        # Optional: Send notification email to admin
        admin_email = os.environ.get("ADMIN_EMAIL")
        if admin_email:
            appointment_data = {
                'name': name,
                'contact': contact,
                'preferred_times': preferred_times,
                'service': service,
                'note': note
            }
            send_appointment_notification(mail, admin_email, appointment_data, CLINIC)
        
        return render_template("contact.html", clinic=CLINIC, success=True)
    
    except Exception as e:
        logger.error(f"Error saving appointment request: {e}")
        return render_template(
            "contact.html",
            clinic=CLINIC,
            success=False,
            error="An error occurred. Please try again or call us directly."
        )


# ============================================================================
# NEW PATIENT FORM
# ============================================================================

# Mapping dictionaries for PDF form fields
SEX_MAP = {"Male": "1", "Female": "2"}
YESNO_MAP = {"Yes": "1", "No": "2"}
MARITAL_MAP = {"Single":"1","Married":"2","Divorced":"3","Separated":"4","Widowed":"5"}
SUB_REL_MAP = {"Self":"1","Spouse":"2","Child":"3","Other":"4"}


@app.route("/new-patients", methods=["GET"])
def new_patients():
    """New patient form - GET"""
    return render_template("new_patients.html", clinic=CLINIC, success=False)


@app.route("/new-patients", methods=["POST"])
def new_patients_submit():
    """New patient form - POST"""
    form = request.form
    
    try:
        # Validate required fields
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

        # Build PDF fields
        pdf_fields = {
            "pt-firstname": p_first,
            "pt-lastname": p_last,
            "pt-midname": form.get("p_mi", "").strip(),
            "pt-address": form.get("p_address", "").strip(),
            "pt-city": form.get("p_city", "").strip(),
            "pt-state": form.get("p_state", "").strip(),
            "pt-zipcode": form.get("p_zip", "").strip(),
            "pt-cellphone": form.get("p_cell_phone", "").strip(),
            "pt-alt-phone": form.get("p_alt_phone", "").strip(),
            "pt-dob": form.get("p_dob", "").strip(),
            "pt-email": form.get("p_email", "").strip(),
            "pt-medications": form.get("m_meds", "").strip(),
            "pt-allergies": form.get("m_allergies", "").strip(),
            "pt-med-sig": sig_med,
            "pt-med-date": form.get("sig_med_date", "").strip() or datetime.now().strftime("%m/%d/%y"),
            "sub-name": form.get("pi_subscriber", "").strip(),
            "sub-ID": form.get("pi_member_id", "").strip(),
            "sub-group": form.get("pi_group", "").strip(),
            "sub-dob": form.get("pi_dob", "").strip(),
            "sub-ins-name": form.get("pi_company", "").strip(),
            "sub-sig-name": form.get("sig_ins_name", "").strip(),
            "sub-signature": form.get("sig_ins", "").strip(),
            "sub-sig-date": form.get("sig_ins_date", "").strip() or datetime.now().strftime("%m/%d/%y"),
        }

        # Map radio buttons to PDF values
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

        # Map checkboxes
        for condition in form.getlist("m_conditions"):
            pdf_fields[condition] = "Yes"

        # Remove empty fields
        pdf_fields = {k: v for k, v in pdf_fields.items() if str(v).strip()}

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{p_last}_{p_first}"
        safe_name = secure_filename(safe_name) or "patient"
        output_pdf = FILLED_DIR / f"{safe_name}_{timestamp}.pdf"
        
        # Fill PDF
        fill_pdf(PDF_TEMPLATE, output_pdf, pdf_fields)
        logger.info(f"New patient form created: {output_pdf.name}")

        return render_template("new_patients.html", clinic=CLINIC, success=True)

    except Exception as e:
        logger.error(f"Error processing new patient form: {e}")
        return render_template("new_patients.html", clinic=CLINIC, 
                             error="An error occurred processing your form. Please try again.")


# ============================================================================
# ADMIN - LOGIN & AUTHENTICATION
# ============================================================================

@app.route("/admin", methods=["GET"])
def admin_login_get():
    """Admin login page - GET"""
    # Clean up expired tokens on login page load
    cleanup_expired_tokens()
    return render_template("admin_login.html", clinic=CLINIC)


@app.route("/admin", methods=["POST"])
def admin_login_post():
    """Admin login - POST"""
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    ip = request.remote_addr
    
    # Rate limiting check
    is_limited, remaining = check_rate_limit(ip, max_attempts=5, window_minutes=15)
    if is_limited:
        log_admin_action("LOGIN_RATE_LIMITED", f"IP: {ip}")
        return render_template("admin_login.html", clinic=CLINIC,
                             error="Too many failed attempts. Please try again in 15 minutes.")
    
    # Validate credentials
    if verify_admin_password(email, password):
        # Successful login
        session["is_admin"] = True
        session["admin_email"] = email
        session["last_activity"] = datetime.now().isoformat()
        session.permanent = True
        
        clear_failed_logins(ip)
        log_admin_action("LOGIN_SUCCESS", f"Email: {email}, IP: {ip}")
        
        return redirect(url_for("admin_requests"))
    
    # Failed login
    record_failed_login(ip)
    log_admin_action("LOGIN_FAILED", f"Email: {email}, IP: {ip}, Remaining: {remaining-1}")
    
    return render_template("admin_login.html", clinic=CLINIC,
                         error=f"Incorrect email or password. {remaining-1} attempts remaining.")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    """Admin logout"""
    email = session.get("admin_email", "unknown")
    log_admin_action("LOGOUT", f"Email: {email}")
    session.clear()
    return redirect(url_for("admin_login_get"))


# ============================================================================
# ADMIN - FORGOT PASSWORD
# ============================================================================

@app.route("/admin/forgot-password", methods=["GET"])
def admin_forgot_password_get():
    """Forgot password page - GET"""
    return render_template("admin_forgot_password.html", clinic=CLINIC)


@app.route("/admin/forgot-password", methods=["POST"])
def admin_forgot_password_post():
    """Forgot password - POST (send reset email)"""
    email = request.form.get("email", "").strip().lower()
    
    if not email:
        return render_template("admin_forgot_password.html", clinic=CLINIC,
                             error="Please enter your email address.")
    
    # Always show success message (security: don't reveal if email exists)
    # But only send email if email is valid
    token, expires_at = create_password_reset_token(email)
    
    if token:
        # Send reset email
        success = send_password_reset_email(mail, email, token, CLINIC['office_name'])
        if success:
            log_admin_action("PASSWORD_RESET_REQUESTED", f"Email: {email}")
        else:
            logger.error(f"Failed to send reset email to {email}")
    
    # Always show success (security best practice)
    return render_template("admin_forgot_password.html", clinic=CLINIC, success=True,
                         message="If that email exists, we've sent password reset instructions.")


# ============================================================================
# ADMIN - RESET PASSWORD (WITH TOKEN)
# ============================================================================

@app.route("/admin/reset-password/<token>", methods=["GET"])
def admin_reset_password_get(token):
    """Reset password page - GET (with token)"""
    # Verify token is valid
    email = verify_reset_token(token)
    
    if not email:
        return render_template("admin_reset_password.html", clinic=CLINIC,
                             error="Invalid or expired reset link. Please request a new one.",
                             token=None)
    
    return render_template("admin_reset_password.html", clinic=CLINIC, token=token, email=email)


@app.route("/admin/reset-password/<token>", methods=["POST"])
def admin_reset_password_post(token):
    """Reset password - POST (with token)"""
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    
    # Verify token
    email = verify_reset_token(token)
    if not email:
        return render_template("admin_reset_password.html", clinic=CLINIC,
                             error="Invalid or expired reset link.", token=None)
    
    # Validate passwords
    if not new_password or not confirm_password:
        return render_template("admin_reset_password.html", clinic=CLINIC,
                             error="Please fill in all fields.", token=token, email=email)
    
    if new_password != confirm_password:
        return render_template("admin_reset_password.html", clinic=CLINIC,
                             error="Passwords do not match.", token=token, email=email)
    
    if len(new_password) < 8:
        return render_template("admin_reset_password.html", clinic=CLINIC,
                             error="Password must be at least 8 characters.", token=token, email=email)
    
    # Update password
    if update_admin_password(email, new_password):
        # Mark token as used
        mark_token_as_used(token)
        
        # Send confirmation email
        send_password_changed_notification(mail, email, CLINIC['office_name'])
        
        log_admin_action("PASSWORD_RESET_SUCCESS", f"Email: {email}")
        
        return render_template("admin_reset_password.html", clinic=CLINIC,
                             success=True, message="Password changed successfully! You can now log in.")
    
    return render_template("admin_reset_password.html", clinic=CLINIC,
                         error="Failed to update password. Please try again.", token=token, email=email)


# ============================================================================
# ADMIN - CHANGE PASSWORD (WHILE LOGGED IN)
# ============================================================================

@app.route("/admin/change-password", methods=["GET"])
@require_admin
def admin_change_password_get():
    """Change password page - GET (for logged-in admin)"""
    return render_template("admin_change_password.html", clinic=CLINIC)


@app.route("/admin/change-password", methods=["POST"])
@require_admin
def admin_change_password_post():
    """Change password - POST (for logged-in admin)"""
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    
    email = session.get("admin_email")
    
    # Validate current password
    if not verify_admin_password(email, current_password):
        return render_template("admin_change_password.html", clinic=CLINIC,
                             error="Current password is incorrect.")
    
    # Validate new passwords
    if not new_password or not confirm_password:
        return render_template("admin_change_password.html", clinic=CLINIC,
                             error="Please fill in all fields.")
    
    if new_password != confirm_password:
        return render_template("admin_change_password.html", clinic=CLINIC,
                             error="New passwords do not match.")
    
    if len(new_password) < 8:
        return render_template("admin_change_password.html", clinic=CLINIC,
                             error="Password must be at least 8 characters.")
    
    if new_password == current_password:
        return render_template("admin_change_password.html", clinic=CLINIC,
                             error="New password must be different from current password.")
    
    # Update password
    if update_admin_password(email, new_password):
        # Send confirmation email
        send_password_changed_notification(mail, email, CLINIC['office_name'])
        
        log_admin_action("PASSWORD_CHANGED", f"Email: {email}")
        
        return render_template("admin_change_password.html", clinic=CLINIC,
                             success=True, message="Password changed successfully!")
    
    return render_template("admin_change_password.html", clinic=CLINIC,
                         error="Failed to update password. Please try again.")


# ============================================================================
# ADMIN - APPOINTMENT REQUESTS
# ============================================================================

@app.route("/admin/requests")
@require_admin
def admin_requests():
    """View appointment requests"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM appointment_requests 
            ORDER BY created_at DESC LIMIT 50
        """)
        rows = cursor.fetchall()
    
    return render_template("admin_requests.html", clinic=CLINIC, rows=rows)


@app.route("/admin/requests/<int:req_id>/status", methods=["POST"])
@require_admin
def admin_update_status(req_id: int):
    """Update appointment request status"""
    new_status = request.form.get("status", "new")
    if new_status not in ("new", "contacted", "closed"):
        new_status = "new"
    
    with get_conn() as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute(
                "UPDATE appointment_requests SET status=%s WHERE id=%s",
                (new_status, req_id)
            )
        else:
            cursor.execute(
                "UPDATE appointment_requests SET status=? WHERE id=?",
                (new_status, req_id)
            )
        conn.commit()
    
    log_admin_action("STATUS_UPDATE", f"Request #{req_id} -> {new_status}")
    return redirect(url_for("admin_requests"))


@app.route("/admin/requests/<int:req_id>/delete", methods=["POST"])
@require_admin
def admin_delete_request(req_id: int):
    """Delete appointment request"""
    with get_conn() as conn:
        cursor = conn.cursor()
        
        # Get request details before deleting
        if USE_POSTGRES:
            cursor.execute("SELECT * FROM appointment_requests WHERE id=%s", (req_id,))
        else:
            cursor.execute("SELECT * FROM appointment_requests WHERE id=?", (req_id,))
        
        row = cursor.fetchone()
        
        if row:
            # Delete request
            if USE_POSTGRES:
                cursor.execute("DELETE FROM appointment_requests WHERE id=%s", (req_id,))
            else:
                cursor.execute("DELETE FROM appointment_requests WHERE id=?", (req_id,))
            conn.commit()
            
            log_admin_action("REQUEST_DELETED", f"Request #{req_id} - {row['name']}")
    
    return redirect(url_for("admin_requests"))


# ============================================================================
# ADMIN - REVIEWS MANAGEMENT
# ============================================================================

@app.route("/admin/reviews")
@require_admin
def admin_reviews_get():
    """Reviews management page"""
    images = list_review_images()
    return render_template("admin_reviews.html", clinic=CLINIC, images=images)


@app.route("/admin/reviews/upload", methods=["POST"])
@require_admin
def admin_reviews_upload():
    """Upload review image"""
    if "image" not in request.files:
        return render_template("admin_reviews.html", clinic=CLINIC,
                             images=list_review_images(), error="No file uploaded.")
    
    file = request.files["image"]
    
    if not file or file.filename == "":
        return render_template("admin_reviews.html", clinic=CLINIC,
                             images=list_review_images(), error="No file selected.")
    
    if not allowed_file(file.filename):
        return render_template("admin_reviews.html", clinic=CLINIC,
                             images=list_review_images(),
                             error="Only PNG, JPG, JPEG, or WEBP files are allowed.")
    
    # Validate file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > app.config["MAX_CONTENT_LENGTH"]:
        return render_template("admin_reviews.html", clinic=CLINIC,
                             images=list_review_images(),
                             error=f"File too large. Maximum {MAX_UPLOAD_MB}MB.")
    
    # Save file
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(file.filename)
    
    if not safe:
        return render_template("admin_reviews.html", clinic=CLINIC,
                             images=list_review_images(), error="Invalid filename.")
    
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
    log_admin_action("REVIEW_IMAGE_UPLOADED", f"File: {dest.name}")
    
    return redirect(url_for("admin_reviews_get"))


@app.route("/admin/reviews/delete/<filename>", methods=["POST"])
@require_admin
def admin_reviews_delete(filename: str):
    """Delete review image"""
    safe = secure_filename(filename)
    target = UPLOAD_DIR / safe
    
    # Safety check
    if target.exists() and target.is_file():
        target.unlink()
        log_admin_action("REVIEW_IMAGE_DELETED", f"File: {safe}")
    
    return redirect(url_for("admin_reviews_get"))


# ============================================================================
# AI CHATBOT API
# ============================================================================

# Emergency keywords for immediate response
EMERGENCY_KEYWORDS = [
    "uncontrolled bleeding", "bleeding won't stop", "can't stop bleeding",
    "can't breathe", "difficulty breathing", "trouble breathing",
    "trouble swallowing", "difficulty swallowing", "choking",
    "severe pain", "fever", "severe swelling", "facial swelling"
]

# FAQ fallback system
FAQ = [
    {
        "patterns": ["hour", "hours", "open", "opening"],
        "response": lambda: (
            "Our hours are: " +
            ", ".join(f"\n{day}: {hrs}" for day, hrs in CLINIC["hours"].items())
        )
    },
    {
        "patterns": ["email"],
        "response": lambda: f"Our email address is: {CLINIC['email']}"
    },
    {
        "patterns": ["address", "location", "where is", "where's"],
        "response": lambda: f"Our address is {CLINIC['address']}."
    },
    {
        "patterns": ["phone", "call", "number"],
        "response": lambda: f"You can call us at {CLINIC['phone']}."
    },
    {
        "patterns": ["insurance", "coverage"],
        "response": lambda: CLINIC['insurance']
    },
    {
        "patterns": ["appointment", "book", "schedule"],
        "response": lambda: 'To request an appointment, please use our <a href="/contact">Contact</a> page or call us.'
    }
]


def is_emergency(msg: str) -> bool:
    """Check if message contains emergency keywords"""
    m = msg.lower()
    return any(k in m for k in EMERGENCY_KEYWORDS)


def faq_reply(msg: str):
    """Find FAQ response if available"""
    m = msg.lower()
    for intent in FAQ:
        for pattern in intent["patterns"]:
            if pattern in m:
                return intent
    return None


def build_website_context():
    """Build comprehensive context for AI chatbot"""
    services_text = []
    for service in CLINIC.get('services', []):
        if isinstance(service, dict):
            services_text.append(f"• {service.get('name', '')}: {service.get('description', '')}")
        else:
            services_text.append(f"• {service}")
    
    return f"""
=== CLINIC INFORMATION ===
Name: {CLINIC.get('office_name', CLINIC.get('name', ''))}
Address: {CLINIC['address']}
Phone: {CLINIC['phone']}
Email: {CLINIC['email']}

=== OFFICE HOURS ===
{chr(10).join(f'{day}: {hrs}' for day, hrs in CLINIC['hours'].items())}

=== SERVICES ===
{chr(10).join(services_text)}

=== INSURANCE ===
{CLINIC['insurance']}

=== DENTAL IMPLANTS ===
{CLINIC.get('implant', 'Please call for implant information.')}

For appointments, patients can:
1. Use our Contact page: /contact
2. Call: {CLINIC['phone']}

For emergencies, call {CLINIC['phone']} immediately.
"""


@app.route("/api/chat", methods=["POST"])
@rate_limit_chat(max_per_minute=20)
def api_chat():
    """AI-powered chatbot endpoint"""
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()

    if not user_msg:
        return jsonify({"reply": "Please type a question and I'll help you! 😊"})
    
    # Emergency check - immediate response
    if is_emergency(user_msg):
        return jsonify({"reply": 
            f"⚠️ <strong>If this is urgent, please call us immediately at {CLINIC['phone']}.</strong><br><br>"
            "If you have uncontrolled bleeding, trouble breathing/swallowing, or severe pain/swelling, "
            "please go to urgent care or the ER right away!"
        })
    
    # Try AI response
    try:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")
        
        system_message = f"""You are a helpful assistant for {CLINIC.get('office_name', CLINIC.get('name', ''))}.

{build_website_context()}

Keep responses friendly, concise (2-3 sentences), and professional. Never provide medical diagnoses.
For health concerns, recommend calling {CLINIC['phone']} or scheduling an appointment.
Use HTML links when helpful: <a href="/contact">Contact</a>, <a href="/services">Services</a>
"""
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_msg}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=400,
            top_p=0.9
        )
        
        reply = chat_completion.choices[0].message.content
        return jsonify({"reply": reply})
        
    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        
        # Fallback to FAQ
        ans = faq_reply(user_msg)
        if ans:
            return jsonify({"reply": ans['response']()})
        
        # Ultimate fallback
        return jsonify({"reply": 
            f"I'm having trouble right now. Please call us at <strong>{CLINIC['phone']}</strong> for assistance!"
        })


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    # Verify configuration on startup
    logger.info("=" * 60)
    logger.info("Starting Flask Application")
    logger.info("=" * 60)
    logger.info(f"Database: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
    logger.info(f"Groq AI: {'✓ Configured' if GROQ_API_KEY else '✗ Not configured'}")
    logger.info(f"Email: {'✓ Configured' if app.config['MAIL_USERNAME'] else '✗ Not configured'}")
    logger.info(f"Admin Email: {os.environ.get('ADMIN_EMAIL', '✗ Not set')}")
    logger.info("=" * 60)
    
    # Use Railway's PORT or default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
