# WarrantyPro - Warranty Management System

An end-to-end digital warranty tracking and claims management platform featuring distinct, purpose-built portals for **Admins**, **Warranty Officers**, **Technicians**, and **Customers**.

---

## 🌟 Overview

**WarrantyPro** streamlines the entire warranty lifecycle from initial product registration to claim resolution:
- **Customer Portal**: Register products, monitor warranty expiration, submit warranty claims with photo attachments, and track repair status in real time.
- **Officer Panel**: Review incoming warranty claims, approve or reject submissions, and dispatch approved repairs directly to qualified service center technicians.
- **Technician Dashboard**: View assigned repair tickets, log diagnostic inspections, submit repair progress updates, and mark jobs as completed.
- **Admin Management Panel**: Real-time KPI metrics, active warranty monitoring, user role management, system audit logs, and status filtering.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Authentication**: Supabase Auth (Email Verification + Direct Google OAuth Login) & Flask-Login Session Management
- **Frontend**: Tailwind CSS & Bootstrap 5, Jinja2 Templates, Bootstrap Icons, Google Fonts

---

## 🚀 Setup & Installation Guide

### 1. Clone the Repository
```bash
git clone https://github.com/razaaliabidi/WarrantyPro.git
cd WarrantyPro
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` template to `.env` and fill in your Supabase project credentials and PostgreSQL database connection string:

```bash
cp .env.example .env
```

Edit `.env`:
```env
SUPABASE_URL=your_supabase_project_url_here
SUPABASE_KEY=your_supabase_anon_key_here
SECRET_KEY=your_flask_secret_key_here
DATABASE_URL=postgresql://username:password@localhost:5432/warranty_db
```

> **Note**: Never commit `.env` containing real keys to Git. It is automatically ignored by `.gitignore`.

### 5. Launch the Application
```bash
python app.py
```
The application will start locally at **http://127.0.0.1:5003**.

---

## 👥 Default Roles & Test Portals

| Role | Access Level | Portal Features |
| :--- | :--- | :--- |
| **Admin** | Full System Control | KPI overview, claims review, product catalog, user management, audit logs |
| **Warranty Officer** | Claims & Operations | Review incoming claims, approve/reject requests, assign to technicians |
| **Technician** | Service & Repair | Task board, inspection details, repair logging, status updates |
| **Customer** | End User | Product registration, warranty cards, claim submissions, notifications |

---

## 🔒 Security Best Practices
- **Password Strength Enforcement**: Multi-step registration requires $\ge 8$ characters, uppercase, lowercase, and special characters.
- **Credential Clearance**: Automatic cache-busting headers and credential purge on logout across all portals.
- **Role Isolation**: Granular route decorators ensuring strict permission separation between user roles.
