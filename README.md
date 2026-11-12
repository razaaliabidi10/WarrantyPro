

https://github.com/user-attachments/assets/6a81bb03-a008-4918-b656-60ce316c5939



https://github.com/user-attachments/assets/56feade8-8424-4688-ac2a-5406099b744e



https://github.com/user-attachments/assets/f4a17113-f15b-4950-8c3b-13646fd31f1f

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
