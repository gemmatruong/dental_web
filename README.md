# Dental Clinic Website - Flask Application

A complete dental clinic website with appointment booking, new patient forms, admin panel, and AI-powered chatbot.

## Features

✅ **Public Pages**
- Home, Services, Implants, Reviews pages
- Contact form with appointment requests
- New patient registration form with PDF generation
- AI-powered chatbot for instant answers

✅ **Admin Panel**
- Secure login with rate limiting
- Appointment request management
- Review image uploads/management
- Password reset via email
- Change password (while logged in)
- Audit logging

✅ **Security**
- CSRF protection
- Secure session cookies
- Rate limiting on login and chatbot
- Password hashing with Werkzeug
- SQL injection protection

## Project Structure

```
.
├── app.py                          # Main Flask application
├── db.py                           # Database handler (PostgreSQL/SQLite)
├── auth.py                         # Authentication utilities
├── email_utils.py                  # Email sending functions
├── pdf_tools.py                    # PDF form filling utilities
├── clinic_info.json                # Clinic information config
├── requirements.txt                # Python dependencies
├── Procfile                        # Railway deployment config
├── .env.example                    # Environment variables template
├── templates/                      # HTML templates
│   ├── admin_login.html
│   ├── admin_forgot_password.html
│   ├── admin_reset_password.html
│   ├── admin_change_password.html
│   ├── admin_requests.html
│   ├── admin_reviews.html
│   ├── home.html
│   ├── services.html
│   ├── implants.html
│   ├── reviews.html
│   ├── contact.html
│   └── new_patients.html
└── static/                         # Static files (CSS, images, uploads)
```

## Setup Instructions

### 1. Clone and Install

```bash
# Clone the repository
git clone <your-repo-url>
cd dental-clinic

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Required Configuration:**

1. **Generate Password Hash:**
```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YourPasswordHere'))"
```

2. **Get Groq API Key:**
   - Visit: https://console.groq.com/keys
   - Create free account
   - Generate API key

3. **Gmail App Password** (for email):
   - Go to Google Account → Security → 2-Step Verification
   - Generate App Password
   - Use this in MAIL_PASSWORD

### 3. Initialize Database

```bash
# Run database initialization
python db.py
```

This creates all required tables and seeds the admin user.

### 4. Run Locally

```bash
# Development mode
python app.py

# Or with gunicorn (production-like)
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

Visit: http://localhost:5000

## Railway Deployment

### Prerequisites
- Railway account (https://railway.app)
- GitHub repository with your code

### Deployment Steps

1. **Create New Project in Railway**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

2. **Add PostgreSQL Database**
   - In your project, click "New"
   - Select "Database" → "PostgreSQL"
   - Railway automatically sets DATABASE_URL

3. **Configure Environment Variables**
   
   In Railway project settings → Variables, add:

   ```
   FLASK_SECRET_KEY=<generate-random-string>
   FLASK_ENV=production
   ADMIN_EMAIL=admin@yourdomain.com
   ADMIN_PASSWORD_HASH=<your-hashed-password>
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=your-email@gmail.com
   GROQ_API_KEY=<your-groq-api-key>
   ```

4. **Deploy**
   - Railway automatically deploys on push to main branch
   - Or click "Deploy" in Railway dashboard

5. **Initialize Database**
   
   After first deployment, you may need to manually run:
   ```bash
   # In Railway's deployment shell:
   python db.py
   ```

### Custom Domain (Optional)

1. In Railway project → Settings → Domains
2. Add your custom domain
3. Update DNS records as shown

## Admin Access

### First Time Login

1. Go to: `https://your-domain.com/admin`
2. Login with:
   - Email: (ADMIN_EMAIL from .env)
   - Password: (the password you hashed)

### Forgot Password

1. Click "Forgot your password?" on login page
2. Enter your admin email
3. Check email for reset link
4. Link expires in 1 hour

### Change Password (While Logged In)

1. Login to admin panel
2. Click "🔐 Change Password" in navbar
3. Enter current password and new password

## Email Configuration

### Gmail Setup

1. **Enable 2-Step Verification**
   - Google Account → Security → 2-Step Verification

2. **Generate App Password**
   - Google Account → Security → App Passwords
   - Select "Mail" and your device
   - Copy the 16-character password

3. **Update .env**
   ```
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=<16-char-app-password>
   ```

### Other Email Providers

**Outlook/Office365:**
```
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=True
```

**SendGrid:**
```
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=<your-sendgrid-api-key>
```

## Chatbot Configuration

The AI chatbot uses Groq (free tier available):

1. Get API key: https://console.groq.com/keys
2. Add to .env: `GROQ_API_KEY=gsk_...`
3. Restart application

**Features:**
- Answers clinic questions (hours, location, services)
- Emergency detection and immediate response
- Rate limiting (20 requests/minute per IP)
- Fallback to FAQ system if API fails

## Security Best Practices

### Production Deployment

1. **Use Strong Secret Key:**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Use Strong Admin Password:**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, symbols

3. **Enable HTTPS:**
   - Railway provides automatic SSL
   - For custom domains, configure SSL certificate

4. **Regular Updates:**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

5. **Monitor Logs:**
   - Check `admin_audit.log` regularly
   - Review failed login attempts

### Environment Variables Security

- Never commit `.env` file to Git
- Use Railway's environment variables
- Rotate passwords regularly
- Use app-specific passwords for email

## Database Schema

### Tables

**appointment_requests**
- id, name, contact, preferred_times, service, note, status, created_at

**admin_credentials**
- id, email, password_hash, created_at, updated_at

**password_reset_tokens**
- id, email, token, expires_at, used, created_at

**admin_audit_log**
- id, action, details, ip_address, user_agent, created_at

## Troubleshooting

### Database Connection Issues

**Local (SQLite):**
- Check if `clinic.db` exists
- Run `python db.py` to recreate

**Railway (PostgreSQL):**
- Verify DATABASE_URL is set
- Check PostgreSQL service is running
- Check logs for connection errors

### Email Not Sending

1. **Check Credentials:**
   - Verify MAIL_USERNAME and MAIL_PASSWORD
   - Ensure App Password is correct (not account password)

2. **Check Firewall:**
   - Port 587 must be open
   - Some ISPs block SMTP

3. **Check Logs:**
   - Look for email errors in console/logs
   - Enable debug logging if needed

### Password Reset Not Working

1. **Check Email Configuration:**
   - Verify emails are being sent
   - Check spam folder

2. **Check Token Expiration:**
   - Tokens expire in 1 hour
   - Request new reset link if expired

3. **Check Database:**
   - Verify password_reset_tokens table exists
   - Check token hasn't been used

### Chatbot Issues

1. **Check API Key:**
   - Verify GROQ_API_KEY is set correctly
   - Test API key at https://console.groq.com

2. **Rate Limiting:**
   - Wait 1 minute if rate limited
   - Adjust limit in auth.py if needed

3. **Fallback to FAQ:**
   - Chatbot uses FAQ if API fails
   - Check FAQ list in app.py

## Maintenance

### Regular Tasks

**Weekly:**
- Review appointment requests
- Check audit logs
- Update review images

**Monthly:**
- Review admin access logs
- Clean up old password reset tokens
- Update dependencies if needed

**Quarterly:**
- Change admin passwords
- Review and update clinic information
- Test all forms and features

### Backup

**Local Development:**
```bash
# Backup SQLite database
cp clinic.db clinic.db.backup
```

**Railway (PostgreSQL):**
- Use Railway's backup feature
- Or use pg_dump via Railway CLI

## Support

For issues or questions:
1. Check this README
2. Review logs (`admin_audit.log`)
3. Check Railway deployment logs
4. Review Flask documentation

## License

This project is proprietary. All rights reserved.

---

**Version:** 2.0  
**Last Updated:** February 2026  
**Python:** 3.8+  
**Flask:** 3.0+