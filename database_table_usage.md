# 🗄️ MediCureFlow - Database Table Usage

This document explains the purpose and usage of each table in the [db.sqlite3](file:///d:/hospitalmanagment/wellcarepluscure/db.sqlite3) database for the MediCureFlow healthcare platform.

---

## 🔐 Identity & Authentication (Django Core)
These tables manage user accounts, permissions, and security.

| Table Name | Usage |
|:---|:---|
| `auth_user` | Stores core account data (username, password, email) for all users (Admin, Doctor, Patient). |
| `auth_group` | Manages user roles/groups for permission bundling. |
| `auth_permission` | Defines specific actions (add/change/delete) allowed on models. |
| `authtoken_token` | Stores REST API authentication tokens for mobile or decoupled frontend access. |
| `django_session` | Manages active login sessions for the web interface. |

---

## 👤 Patient Management (`users` app)
Contains extended data specifically for patients.

| Table Name | Usage |
|:---|:---|
| `users_userprofile` | **Core Patient Data**: Stores medical history, blood group, allergies, contact info, and profile pictures. Links to `auth_user`. |

---

## 🩺 Clinical Operations (`doctors` app)
The largest module, managing healthcare providers and their services.

| Table Name | Usage |
|:---|:---|
| `doctors_doctor` | **Doctor Profiles**: Specialization, fees, bios, and verification status. |
| `doctors_doctoravailability` | **Schedule**: Stores specific day/time slots when a doctor is available for booking. |
| `doctors_appointment` | **Bookings**: Tracks interactions between patients and doctors (date, time, status, notes). |
| `doctors_doctoreducation` | **Credentials**: Academic degrees and institutions of the doctors. |
| `doctors_doctorspecialization` | **Expertise**: Detailed sub-specialities and years of experience in specific fields. |
| `doctors_review` | **Feedback**: Patient ratings and written testimonials for doctors. |
| `doctors_medication` | **Prescriptions**: (If present) Stores medications recommended during consultations. |

---

## 💳 Financial Services (`payments` app)
Handles all monetization and billing logic.

| Table Name | Usage |
|:---|:---|
| `payments_payment` | **Stripe Records**: Tracks payment intents, status (Succeeded/Failed), and amounts. |
| `payments_invoices` | **Billing**: Generates formal billing documents for appointments. |
| `payments_paymentmethod` | **Wallets**: Stores saved payment methods for repeat users. |
| `payments_transaction` | **Ledger**: Internal logs of all financial movements. |

---

## 🔔 Communications (`notifications` app)
Manages outgoing alerts and system messages.

| Table Name | Usage |
|:---|:---|
| `notifications_notificationqueue` | **Buffer**: Stores messages waiting to be sent via Email or SMS. |
| `notifications_notificationtype` | **Templates**: Defines categories like "Appointment Reminder" or "Payment Success". |
| `system_alerts` | **Global Alerts**: Site-wide messages shown to all users (e.g., "System Maintenance on Sunday"). |

---

## 👑 Administration & Logs
System-wide tracking and configuration.

| Table Name | Usage |
|:---|:---|
| `admin_activities` | **Audit Trail**: Records administrative actions (e.g., verifying a doctor, deleting a user). |
| `admin_configurations` | **Settings**: Dynamic site settings like consultation fees or feature toggles. |
| `django_migrations` | **History**: Tracks database schema versions applied by Django. |
| `sqlite_sequence` | **Auto-increment**: Internal SQLite table to track primary key sequences. |
