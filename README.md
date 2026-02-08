# 🦷 Dental Clinic Website (Flask + AI Chatbot)

**A full-stack web application for a dental clinic featuring appointment booking, patient intake forms, an admin dashboard, security best practices, and an AI-powered chatbot.**

---

## 🚀 Project Overview

This project is a **full-stack healthcare web application** built with **Python (Flask)**, JavaScript, HTML, and CSS. It simulates a real-world dental clinic platform that allows patients to:

- 📅 Request an appointment  
- 📄 Submit new patient intake forms with PDF generation  
- 🤖 Ask questions via an AI-powered chatbot  
- 🔐 Allow administrators to manage appointments and reviews


The project demonstrates **end-to-end web development skills**, including backend APIs, database design, frontend UI/UX, security considerations, and deployment workflows.

---

## 🔍 Why This Project Matters

This project highlights:

- ✅ Real-world full-stack engineering (frontend, backend, database, deployment)  
- ✅ Secure web application practices (CSRF protection, password hashing, rate limiting)  
- ✅ Practical AI integration to improve user experience  
- ✅ Workflow automation (PDF generation, email notifications)
- ✅ Production-ready deployment using industry-standard tools  
- ✅ Clean code organization and maintainability

It was designed to mirror the requirements of modern service-based platforms in healthcare while emphasizing scalability, maintainability, and clean architecture.

---

## 💡 Features

### 🧑‍💻 Patient-Facing

- Responsive landing pages (Home, Services, Implants, Reviews)  
- Appointment request form  
- New patient intake form with automated PDF generation  
- AI chatbot for clinic FAQs, services, and hours  

### 🛠 Admin Panel

- Secure admin authentication with rate limiting  
- Appointment request management  
- Review and image moderation  
- Password reset and account management  
- Audit-style logging for administrative actions  

### 🔐 Security

- CSRF protection on all forms  
- Protected admin-only routes  
- Password hashing using industry-standard libraries  
- Safe database interactions to mitigate SQL injection risks  

---

## 📁 Project Structure

```text
.
├── app.py                     # Main Flask application
├── auth.py                    # Authentication utilities
├── db.py                      # Database setup and logic
├── pdf_tools.py               # PDF generation utilities
├── email_utils.py             # Email sending utilities
├── clinic_info.json           # Clinic configuration data
├── requirements.txt           # Python dependencies
├── Procfile                   # Deployment configuration
├── .env.example               # Environment variable template
├── templates/                 # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── services.html
│   ├── implants.html
│   ├── reviews.html
│   ├── contact.html
│   ├── new_patient.html
│   ├── admin_login.html
│   ├── admin_requests.html
│   ├── admin_reviews.html
│   ├── admin_password_reset.html
│   ├── admin_forgot_password.html
│   └── admin_change_password.html
├── static/                    # Static assets
│   ├── uploads/
│   │   ├── dentists/
│   │   ├── forms/
│   │   ├── images/
│   │   └── reviews/
│   ├── chat.js
│   ├── delete_requests.js
│   ├── image_slider.js
│   ├── new_patient.js
│   └── styles.css
├── filled_forms/              # Generated patient PDF forms
└── README.md


## 📌 Tech Stack

| Layer      | Technologies                                  |
| ---------- | --------------------------------------------- |
| Backend    | Python, Flask                                 |
| Frontend   | HTML, CSS, JavaScript                         |
| Database   | SQLite (local), PostgreSQL (production-ready) |
| AI         | Groq API                                      |
| Deployment | Railway, Gunicorn                             |
| Security   | Werkzeug, CSRF protection                     |


## 🛠 Setup & Installation

1. Clone the Repository

```bash
git clone https://github.com/gemmatruong/dental_web.git
cd dental_web
```

2. Create and Activate a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

3. Install Dependencies

```bash
pip install -r requirements.txt
```

4. Environment Variables
- Copy .env.example to .env
- Add required credentials

```bash
FLASK_SECRET_KEY=your_secret_key
GROQ_API_KEY=gsk_...
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_email_password
```

## 🛢 Initialize the Database
```bash
python db.py
```

## 🏃 Run the Application Locally
```bash
flask run
```

---

## 🚀 Deployment (Railway)

This application is **production-ready** and deployable on **Railway**.

### Deployment Steps

1. Create a new Railway project  
2. Connect the GitHub repository  
3. Configure required environment variables  
4. Railway automatically builds and deploys the app on each push to `main`

---

## 📈 Future Enhancements

- Unit and integration testing  
- Role-based user authentication  
- Improved AI chatbot context and conversational memory  
- Docker containerization  
- CI/CD pipeline integration  

---

## 🤝 Contributions

Contributions are welcome and appreciated.

To contribute:

1. Fork the repository  
2. Create a new feature branch  
3. Submit a pull request with a clear description of changes  

---

## 📫 Contact

**Developer:** Gemma Truong  
**GitHub:** https://github.com/gemmatruong  

**LinkedIn:** *(https://www.linkedin.com/in/gemmatruong/)*  
**Email:** *gemmatruong99@gmail.com*  

---

## 📄 License

This project is proprietary (all rights reserved).  
Please contact the author for permission regarding usage or distribution.
