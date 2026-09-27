# WarrantyPro — Project Status & Handover Guide

> **Last Updated:** September 24, 2026  
> **Server URL:** `http://127.0.0.1:5003`

---

## 1. Authentication System Architecture

The project now features a unified authentication bridge:
1. **Frontend**: Modern Tailwind CSS login interface at `/login` with tabs for **Sign In** and **Create Account**, CSRF protection, and a **Continue with Google** OAuth button.
2. **Supabase Auth Integration**:
   - Direct Email & Password authentication with email verification notices.
   - Google OAuth 2.0 PKCE / Hash fragment callback handler at `/auth/callback` and `/api/set-session`.
3. **Local Database & Role Bridge**:
   - Upon successful Supabase login or Google OAuth callback, the user's email is retrieved.
   - **Case A (Existing local user)**: Retrieves existing user, activates session, and logs in via Flask-Login.
   - **Case B (New user / Google OAuth)**: Auto-creates a local `User` record with role `customer` and linked `Customer` profile.
4. **Legacy Test Accounts Fallback**:
   - Accounts already present in the local database (e.g. `razaali7@gmail.com`, `officer@test.com`, `tech@test.com`, `customer@test.com`) authenticate seamlessly via their local credentials (`raza@8521`) and are auto-synced to Supabase in the background.
5. **Dynamic Role Redirection**:
   - Generic placeholder dashboard has been completely bypassed.
   - Every login immediately redirects to the user's specific WarrantyPro panel:
     - **Admin** (`razaali7@gmail.com`): `/admin/dashboard`
     - **Warranty Officer** (`officer@test.com`): `/officer/dashboard`
     - **Technician** (`tech@test.com`): `/admin/technician-dashboard`
     - **Customer** (`customer@test.com` or new OAuth users): `/warranty/dashboard`
6. **Populated Session Variables**:
   - `session['user_id']`: Local database user ID (integer)
   - `session['email']`: User email
   - `session['role']`: Role name string (`'admin'`, `'warranty_officer'`, `'technician'`, `'customer'`)
   - `session['user']`: User data dictionary `{ 'id', 'email', 'role', 'access_token' }`
   - `flask_login.current_user`: Full ORM User instance with role helper methods (`is_admin()`, `is_warranty_officer()`, etc.)

---

## 2. Test Accounts & Credentials

| Role | Email | Password | Landing Panel |
| :--- | :--- | :--- | :--- |
| **Admin** | `razaali7@gmail.com` | `raza@8521` | `http://127.0.0.1:5003/admin/dashboard` |
| **Officer** | `officer@test.com` | `raza@8521` | `http://127.0.0.1:5003/officer/dashboard` |
| **Technician** | `tech@test.com` | `raza@8521` | `http://127.0.0.1:5003/admin/technician-dashboard` |
| **Customer** | `customer@test.com` | `raza@8521` | `http://127.0.0.1:5003/warranty/dashboard` |
| **Google Sign-In** | Any Google Account | Google Auth | Auto-created as Customer &rarr; `/warranty/dashboard` |

---

## 3. How to Run the Project

```powershell
cd "c:\Users\User\OneDrive - Dawood University of Engineering Technology\Desktop\warranty pro"
python app.py
```
App runs at: **`http://127.0.0.1:5003`**
