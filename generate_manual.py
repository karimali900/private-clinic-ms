#!/usr/bin/env python3
"""Generate user manuals (English + Arabic PDF) for Private Clinic OMS."""

from fpdf import FPDF
import os

DROID_KUFI = "/usr/share/fonts/paktype-naskh-basic-fonts/PakTypeNaskhBasic.ttf"
DROID_KUFI_BOLD = "/usr/share/fonts/paktype-naskh-basic-fonts/PakTypeNaskhBasic.ttf"
DROID_SANS = "/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf"
DROID_SANS_BOLD = "/usr/share/fonts/google-droid-sans-fonts/DroidSans-Bold.ttf"

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_pdf")
os.makedirs(OUT_DIR, exist_ok=True)


class EnglishManual(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("DroidSans", "", DROID_SANS)
        self.add_font("DroidSans", "B", DROID_SANS_BOLD)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("DroidSans", "", 7)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "Private Clinic — Obstetrics Management System  |  User Manual", align="C")
            self.ln(4)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("DroidSans", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def chapter_title(self, num, title):
        self.set_font("DroidSans", "B", 16)
        self.set_text_color(25, 60, 120)
        self.cell(0, 12, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(25, 60, 120)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def section_title(self, title):
        self.set_font("DroidSans", "B", 12)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("DroidSans", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def bullet(self, text):
        self.set_font("DroidSans", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, " * " + text, new_x="LMARGIN", new_y="NEXT")

    def step(self, num, text):
        self.set_font("DroidSans", "B", 10)
        self.set_text_color(25, 60, 120)
        self.cell(0, 6, f"Step {num}:", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DroidSans", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def note_box(self, text):
        self.set_fill_color(240, 245, 255)
        self.set_draw_color(25, 60, 120)
        y = self.get_y()
        self.rect(12, y, 186, 16)
        self.set_xy(14, y + 1)
        self.set_font("DroidSans", "B", 9)
        self.set_text_color(25, 60, 120)
        self.cell(0, 6, "NOTE:")
        self.set_xy(14, y + 7)
        self.set_font("DroidSans", "", 9)
        self.set_text_color(50, 50, 50)
        self.multi_cell(182, 5, text)
        self.ln(18)


class ArabicManual(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("DroidKufi", "", DROID_KUFI)
        self.add_font("DroidKufi", "B", DROID_KUFI_BOLD)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("DroidKufi", "", 7)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "العيادة الخاصة — نظام إدارة التوليد  |  دليل المستخدم", align="C")
            self.ln(4)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("DroidKufi", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"الصفحة {self.page_no()}", align="C")

    def chapter_title(self, num, title):
        self.set_font("DroidKufi", "B", 16)
        self.set_text_color(25, 60, 120)
        self.cell(0, 12, f"{title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(25, 60, 120)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def section_title(self, title):
        self.set_font("DroidKufi", "B", 12)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("DroidKufi", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def bullet(self, text):
        self.set_font("DroidKufi", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, "-  " + text, new_x="LMARGIN", new_y="NEXT")

    def step(self, num, text):
        self.set_font("DroidKufi", "B", 10)
        self.set_text_color(25, 60, 120)
        self.cell(0, 7, f"الخطوة {num}:", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DroidKufi", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def note_box(self, text):
        self.set_fill_color(240, 245, 255)
        self.set_draw_color(25, 60, 120)
        y = self.get_y()
        self.rect(12, y, 186, 18)
        self.set_xy(14, y + 1)
        self.set_font("DroidKufi", "B", 9)
        self.set_text_color(25, 60, 120)
        self.cell(0, 6, "ملاحظة:")
        self.set_xy(14, y + 7)
        self.set_font("DroidKufi", "", 9)
        self.set_text_color(50, 50, 50)
        self.multi_cell(182, 6, text)
        self.ln(20)


def build_english():
    pdf = EnglishManual()
    pdf.set_title("Private Clinic OMS — User Manual")
    pdf.set_author("Karim Abdelaziz")

    # ── Cover Page ──
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("DroidSans", "B", 26)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 15, "Private Clinic", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "Obstetrics Management System", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("DroidSans", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "User Manual", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("DroidSans", "", 11)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, "Created by Karim Abdelaziz", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "Support: 00201029927276", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("DroidSans", "", 9)
    pdf.cell(0, 8, "Version 2.0.0", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Table of Contents ──
    pdf.add_page()
    pdf.set_font("DroidSans", "B", 18)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 14, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    toc = [
        ("1", "Introduction"),
        ("2", "Getting Started"),
        ("  2.1", "System Requirements"),
        ("  2.2", "How to Start the Application"),
        ("3", "Login & Language Settings"),
        ("  3.1", "Default Login Credentials"),
        ("  3.2", "Facility Code"),
        ("  3.3", "Switching Between English and Arabic"),
        ("  3.4", "Password Visibility Toggle"),
        ("  3.5", "New User Registration"),
        ("4", "Dashboard Overview"),
        ("5", "Patient Management"),
        ("  5.1", "Adding a New Patient"),
        ("  5.2", "Searching for Patients"),
        ("  5.3", "Patient Profile"),
        ("6", "Antenatal Care"),
        ("  6.1", "Recording a Visit"),
        ("  6.2", "Follow-up Schedule"),
        ("7", "Investigations"),
        ("  7.1", "Adding Lab Results"),
        ("  7.2", "Viewing Investigation History"),
        ("8", "Classification & Risk Assessment"),
        ("9", "Delivery Management"),
        ("10", "Postpartum Care"),
        ("11", "Admin Panel"),
        ("  11.1", "User Management"),
        ("  11.2", "Facility Management & Branding"),
        ("12", "Troubleshooting"),
        ("13", "Support"),
    ]
    for num, title in toc:
        pdf.set_font("DroidSans", "B" if not num.startswith(" ") else "", 10)
        pdf.set_text_color(30, 30, 30)
        indent = 15 if num.startswith(" ") else 0
        pdf.set_x(12 + indent)
        pdf.cell(0, 7, f"{num.strip()}   {title}", new_x="LMARGIN", new_y="NEXT")

    # ── Chapter 1: Introduction ──
    pdf.add_page()
    pdf.chapter_title("1", "Introduction")
    pdf.body_text(
        "Private Clinic — Obstetrics Management System (OMS) is a comprehensive software application "
        "designed for Egyptian maternity hospitals and obstetrics & gynecology clinics. It provides "
        "end-to-end management of patient care, from registration through antenatal visits, "
        "investigations, delivery, and postpartum follow-up."
    )
    pdf.body_text(
        "The system is bilingual (English and Arabic) with full RTL support, works offline using "
        "a local database, and can run from a USB drive with no installation required. It supports "
        "multiple facilities (hospitals or clinics) with isolated patient data and independent "
        "branding (name, logo, support phone)."
    )
    pdf.body_text(
        "Key features include:"
    )
    pdf.bullet("Patient registration and comprehensive profile management")
    pdf.bullet("Antenatal visit tracking with vital signs and clinical notes")
    pdf.bullet("Investigations management (lab results, imaging)")
    pdf.bullet("ML-based risk classification and assessment")
    pdf.bullet("Labor & delivery tracking")
    pdf.bullet("Postpartum care for mother and baby")
    pdf.bullet("Bilingual interface (English / Arabic)")
    pdf.bullet("Multi-facility support with independent branding")
    pdf.bullet("Offline operation — no internet required")
    pdf.bullet("USB portable — runs without installation")

    # ── Chapter 2: Getting Started ──
    pdf.add_page()
    pdf.chapter_title("2", "Getting Started")

    pdf.section_title("2.1  System Requirements")
    pdf.bullet("Operating System: Windows 10/11, Linux, or macOS")
    pdf.bullet("RAM: 4 GB minimum, 8 GB recommended")
    pdf.bullet("Disk Space: 200 MB free")
    pdf.bullet("Screen Resolution: 1280 x 720 or higher")
    pdf.bullet("No internet connection required for daily use")

    pdf.section_title("2.2  How to Start the Application")
    pdf.step(1, "Insert the USB drive into your computer.")
    pdf.step(2, "Open the USB folder and locate the start file:")
    pdf.bullet("Windows: Double-click start.bat")
    pdf.bullet("Linux: Double-click start.sh (or run bash start.sh in terminal)")
    pdf.bullet("macOS: Run bash start.sh in Terminal")
    pdf.step(3, "Wait for the application to load. Your browser will open automatically.")
    pdf.step(4, "The system opens at: http://localhost:5000/dashboard")
    pdf.note_box("If the browser does not open automatically, manually open your browser and navigate to http://localhost:5000/dashboard")

    # ── Chapter 3: Login ──
    pdf.add_page()
    pdf.chapter_title("3", "Login & Language Settings")

    pdf.section_title("3.1  Default Login Credentials")
    pdf.body_text("On first use, log in with the default administrator account:")
    pdf.bullet("Username: admin")
    pdf.bullet("Password: admin123")
    pdf.body_text("It is recommended to change the admin password after first login.")

    pdf.section_title("3.2  Facility Code")
    pdf.body_text(
        "If you are running a single clinic, leave the facility code field empty "
        "(DEFAULT will be used automatically). For multi-facility setups, enter your "
        "assigned facility code. A facility code is a short identifier like 'CLINIC01' "
        "or 'HOSPITAL_A' that links to that facility's data and branding."
    )
    pdf.body_text("You can browse available facilities by clicking the magnifying glass (search) icon next to the facility code field.")

    pdf.section_title("3.3  Switching Between English and Arabic")
    pdf.body_text(
        "On the login page and throughout the application, you will find a language "
        "toggle button. Click it to switch between English and Arabic. The interface "
        "instantly updates all text, labels, and messages to the selected language."
    )

    pdf.section_title("3.4  Password Visibility Toggle")
    pdf.body_text(
        "When typing your password, click the eye icon (show/hide) next to the password "
        "field to reveal or hide the characters. This helps avoid typing errors."
    )

    pdf.section_title("3.5  New User Registration")
    pdf.body_text(
        "New users can register by clicking the 'Register' link on the login page. "
        "Fill in your name, username, password, and select a role. After registration, "
        "an administrator must approve your account before you can log in."
    )

    # ── Chapter 4: Dashboard ──
    pdf.add_page()
    pdf.chapter_title("4", "Dashboard Overview")
    pdf.body_text(
        "After logging in, you will see the main dashboard. This is your central "
        "hub for navigating the system. The dashboard displays:"
    )
    pdf.bullet("Quick statistics: total patients, today's visits, pending investigations")
    pdf.bullet("Search bar to find patients quickly")
    pdf.bullet("Navigation sidebar with links to all sections")
    pdf.bullet("Your facility name and branding at the top")
    pdf.bullet("Language toggle (English / Arabic)")
    pdf.bullet("User profile and logout button")
    pdf.body_text(
        "Use the sidebar menu to navigate between sections: "
        "Patients, Antenatal Care, Investigations, Classification, Delivery, Postpartum, and Admin."
    )

    # ── Chapter 5: Patient Management ──
    pdf.add_page()
    pdf.chapter_title("5", "Patient Management")

    pdf.section_title("5.1  Adding a New Patient")
    pdf.step(1, "From the sidebar, click 'Patients' then 'Add New Patient'.")
    pdf.step(2, "Fill in the patient's information:")
    pdf.bullet("Full name (required)")
    pdf.bullet("Date of birth")
    pdf.bullet("Phone number")
    pdf.bullet("Address")
    pdf.bullet("Medical history notes")
    pdf.step(3, "Click 'Save' to register the patient.")
    pdf.body_text("The patient will appear in the patient list immediately.")

    pdf.section_title("5.2  Searching for Patients")
    pdf.body_text(
        "Use the search bar on the dashboard or the Patients page. You can search by:"
    )
    pdf.bullet("Patient name (partial matches supported)")
    pdf.bullet("Patient ID")
    pdf.bullet("Phone number")
    pdf.body_text("Results update in real-time as you type.")

    pdf.section_title("5.3  Patient Profile")
    pdf.body_text(
        "Click on a patient's name to open their profile. The profile page shows "
        "all information for that patient, including:"
    )
    pdf.bullet("Personal details and contact information")
    pdf.bullet("Medical history")
    pdf.bullet("Antenatal visit history")
    pdf.bullet("Investigation results")
    pdf.bullet("Classification and risk status")
    pdf.bullet("Delivery records")
    pdf.bullet("Postpartum follow-up records")

    # ── Chapter 6: Antenatal Care ──
    pdf.add_page()
    pdf.chapter_title("6", "Antenatal Care")

    pdf.section_title("6.1  Recording a Visit")
    pdf.step(1, "From the sidebar, click 'Antenatal Care'.")
    pdf.step(2, "Select the patient from the list or search for them.")
    pdf.step(3, "Click 'New Visit' to record a check-up.")
    pdf.step(4, "Enter the visit details:")
    pdf.bullet("Date of visit")
    pdf.bullet("Gestational age (weeks)")
    pdf.bullet("Blood pressure, weight, fundal height")
    pdf.bullet("Fetal heart rate")
    pdf.bullet("Clinical notes and observations")
    pdf.step(5, "Click 'Save Visit' to record the data.")

    pdf.section_title("6.2  Follow-up Schedule")
    pdf.body_text(
        "The system helps track follow-up appointments. After each visit, you can "
        "schedule the next visit date. The dashboard shows upcoming follow-ups."
    )

    # ── Chapter 7: Investigations ──
    pdf.add_page()
    pdf.chapter_title("7", "Investigations")

    pdf.section_title("7.1  Adding Lab Results")
    pdf.step(1, "From the sidebar, click 'Investigations'.")
    pdf.step(2, "Select the patient.")
    pdf.step(3, "Click 'Add Investigation'.")
    pdf.step(4, "Select the investigation type (e.g., Complete Blood Count, Blood Glucose, Urinalysis, Ultrasound).")
    pdf.step(5, "Enter the results and any notes.")
    pdf.step(6, "Click 'Save'.")

    pdf.section_title("7.2  Viewing Investigation History")
    pdf.body_text(
        "All investigations for a patient are displayed in chronological order on "
        "their profile. You can view trends over time, compare results, and see "
        "which values are outside the normal range."
    )

    # ── Chapter 8: Classification ──
    pdf.add_page()
    pdf.chapter_title("8", "Classification & Risk Assessment")
    pdf.body_text(
        "The system includes a machine learning-based classification engine that "
        "helps assess patient risk. It analyzes patient data and visit history to "
        "provide risk scores and recommendations."
    )
    pdf.step(1, "From the sidebar, click 'Classification'.")
    pdf.step(2, "Select a patient.")
    pdf.step(3, "Review the automatically calculated risk factors.")
    pdf.step(4, "The system displays risk level (Low, Moderate, High) and recommendations.")
    pdf.body_text(
        "Classification considers: maternal age, BMI, blood pressure, blood glucose "
        "levels, previous pregnancy complications, and other clinical parameters."
    )

    # ── Chapter 9: Delivery ──
    pdf.add_page()
    pdf.chapter_title("9", "Delivery Management")
    pdf.body_text(
        "The delivery module tracks labor and delivery details for each patient."
    )
    pdf.step(1, "From the sidebar, click 'Delivery'.")
    pdf.step(2, "Select the patient.")
    pdf.step(3, "Record delivery details:")
    pdf.bullet("Delivery date and time")
    pdf.bullet("Delivery mode (normal vaginal, C-section, vacuum, forceps)")
    pdf.bullet("Duration of labor")
    pdf.bullet("Complications (if any)")
    pdf.bullet("Baby details: weight, length, head circumference, Apgar scores")
    pdf.step(4, "Click 'Save Delivery Record'.")
    pdf.body_text("Delivery records are stored in the patient's history for future reference.")

    # ── Chapter 10: Postpartum ──
    pdf.add_page()
    pdf.chapter_title("10", "Postpartum Care")
    pdf.body_text(
        "The postpartum module tracks follow-up care for both mother and baby "
        "after delivery."
    )
    pdf.step(1, "From the sidebar, click 'Postpartum'.")
    pdf.step(2, "Select the patient.")
    pdf.step(3, "Record postpartum visit details:")
    pdf.bullet("Date of follow-up")
    pdf.bullet("Mother: blood pressure, temperature, uterine involution, lochia, wound healing")
    pdf.bullet("Baby: feeding status, weight, jaundice check, vaccination status")
    pdf.step(4, "Click 'Save'.")
    pdf.body_text("Regular postpartum follow-up is recommended at 1 week, 2 weeks, and 6 weeks after delivery.")

    # ── Chapter 11: Admin Panel ──
    pdf.add_page()
    pdf.chapter_title("11", "Admin Panel")
    pdf.body_text("The Admin panel is accessible to users with the Admin role.")

    pdf.section_title("11.1  User Management")
    pdf.body_text(
        "Administrators can manage user accounts:"
    )
    pdf.bullet("View all registered users")
    pdf.bullet("Approve or reject new user registrations")
    pdf.bullet("Edit user roles (Admin, Doctor, Nurse, Receptionist)")
    pdf.bullet("Deactivate or delete user accounts")
    pdf.step(1, "From the sidebar, click 'Admin' then 'User Management'.")
    pdf.step(2, "Pending users appear with an 'Approve' button.")
    pdf.step(3, "Click 'Approve' to grant access, or 'Reject' to deny.")

    pdf.section_title("11.2  Facility Management & Branding")
    pdf.body_text(
        "Each facility can customize its branding. This controls what patients see "
        "when they log in:"
    )
    pdf.bullet("Clinic Name: Displayed in the login box, sidebar, and footer")
    pdf.bullet("Support Phone: Displayed in the login box and footer")
    pdf.bullet("Clinic Logo: Upload a custom image (JPG/PNG) displayed on the login page and sidebar")
    pdf.step(1, "Go to Admin -> Facility Management -> Clinic Branding.")
    pdf.step(2, "Enter the clinic name and support phone number.")
    pdf.step(3, "Click 'Choose File' to upload a logo image.")
    pdf.step(4, "Click 'Save Branding' to update.")
    pdf.body_text("Changes take effect immediately. Each facility sees only its own branding.")

    # ── Chapter 12: Troubleshooting ──
    pdf.add_page()
    pdf.chapter_title("12", "Troubleshooting")

    pdf.section_title("Application does not start")
    pdf.bullet("Ensure you have Python 3.8+ installed (if running from source)")
    pdf.bullet("Check that port 5000 is not in use by another application")
    pdf.bullet("On Windows, run start.bat as Administrator")
    pdf.bullet("On Linux/macOS, ensure the start.sh file has execute permissions (chmod +x start.sh)")

    pdf.section_title("Browser does not open automatically")
    pdf.body_text("Manually open your browser and go to http://localhost:5000/dashboard")

    pdf.section_title("Cannot log in")
    pdf.bullet("Check that Caps Lock is off")
    pdf.bullet("Use the default credentials: admin / admin123")
    pdf.bullet("If you registered a new account, ask an administrator to approve it")
    pdf.bullet("Verify the facility code is correct")

    pdf.section_title("Language not switching properly")
    pdf.body_text("Click the language toggle button again. If the issue persists, refresh the page (F5).")

    # ── Chapter 13: Support ──
    pdf.add_page()
    pdf.chapter_title("13", "Support")
    pdf.body_text("For technical support, questions, or feedback:")
    pdf.bullet("Developer: Karim Abdelaziz")
    pdf.bullet("Phone: 00201029927276")
    pdf.body_text("We welcome your feedback to help improve the system.")

    # ── Save ──
    out_path = os.path.join(OUT_DIR, "OMS_User_Manual_EN.pdf")
    pdf.output(out_path)
    return out_path


def build_arabic():
    pdf = ArabicManual()
    pdf.set_title("نظام إدارة التوليد — دليل المستخدم")
    pdf.set_author("كريم عبد العزيز")

    # ── Cover Page ──
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("DroidKufi", "B", 26)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 15, "العيادة الخاصة", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "نظام إدارة التوليد", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("DroidKufi", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "دليل المستخدم", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("DroidKufi", "", 11)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, "إعداد: كريم عبد العزيز", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "الدعم الفني: 00201029927276", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("DroidKufi", "", 9)
    pdf.cell(0, 8, "الإصدار 2.0.0", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── Table of Contents ──
    pdf.add_page()
    pdf.set_font("DroidKufi", "B", 18)
    pdf.set_text_color(25, 60, 120)
    pdf.cell(0, 14, "المحتويات", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    toc = [
        "مقدمة",
        "بدء الاستخدام",
        "تسجيل الدخول وإعدادات اللغة",
        "نظرة عامة على لوحة التحكم",
        "إدارة المرضى",
        "رعاية ما قبل الولادة",
        "التحاليل والفحوصات",
        "التصنيف وتقييم المخاطر",
        "إدارة الولادة",
        "رعاية ما بعد الولادة",
        "لوحة الإدارة",
        "حل المشكلات",
        "الدعم الفني",
    ]
    for i, title in enumerate(toc, 1):
        pdf.set_font("DroidKufi", "", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.set_x(12)
        pdf.cell(0, 7, f"{i}   {title}", new_x="LMARGIN", new_y="NEXT")

    # ── Chapter 1 ──
    pdf.add_page()
    pdf.chapter_title("1", "مقدمة")
    pdf.body_text(
        "نظام إدارة التوليد (OMS) هو تطبيق برمجي شامل مصمم لمستشفيات الولادة المصرية "
        "وعيادات أمراض النساء والتوليد. يوفر إدارة متكاملة لرعاية المريضات بدءًا من "
        "التسجيل مرورًا بزيارات ما قبل الولادة والتحاليل والفحوصات والولادة ومتابعة ما بعد الولادة."
    )
    pdf.body_text(
        "النظام ثنائي اللغة (الإنجليزية والعربية) مع دعم كامل للكتابة من اليمين إلى اليسار، "
        "ويعمل بدون اتصال بالإنترنت باستخدام قاعدة بيانات محلية، ويمكن تشغيله من ذاكرة USB "
        "بدون الحاجة إلى تثبيت. يدعم النظام عدة منشآت (مستشفيات أو عيادات) مع بيانات معزولة "
        "وهوية بصرية مستقلة (الاسم والشعار ورقم الدعم)."
    )
    pdf.body_text("الميزات الرئيسية:")
    pdf.bullet("تسجيل المريضات وإدارة الملفات الشاملة")
    pdf.bullet("متابعة زيارات ما قبل الولادة مع العلامات الحيوية والملاحظات السريرية")
    pdf.bullet("إدارة التحاليل والفحوصات (نتائج المعمل، الأشعة)")
    pdf.bullet("تصنيف المخاطر باستخدام التعلم الآلي")
    pdf.bullet("تتبع الولادة والمخاض")
    pdf.bullet("رعاية ما بعد الولادة للأم والطفل")
    pdf.bullet("واجهة ثنائية اللغة (إنجليزي / عربي)")
    pdf.bullet("دعم عدة منشآت مع هوية بصرية مستقلة")
    pdf.bullet("يعمل بدون إنترنت")
    pdf.bullet("قابل للنقل عبر USB بدون تثبيت")

    # ── Chapter 2 ──
    pdf.add_page()
    pdf.chapter_title("2", "بدء الاستخدام")

    pdf.section_title("المتطلبات")
    pdf.bullet("نظام التشغيل: ويندوز 10/11، لينكس، أو ماك")
    pdf.bullet("الذاكرة: 4 جيجابايت كحد أدنى، 8 جيجابايت موصى به")
    pdf.bullet("مساحة التخزين: 200 ميجابايت")
    pdf.bullet("دقة الشاشة: 1280 × 720 أو أعلى")
    pdf.bullet("لا يحتاج اتصال بالإنترنت للاستخدام اليومي")

    pdf.section_title("كيفية تشغيل التطبيق")
    pdf.step(1, "أدخل ذاكرة USB في جهاز الكمبيوتر.")
    pdf.step(2, "افتح المجلد وابحث عن ملف التشغيل:")
    pdf.bullet("ويندوز: اضغط مرتين على start.bat")
    pdf.bullet("لينكس: اضغط مرتين على start.sh أو شغّل bash start.sh في الطرفية")
    pdf.bullet("ماك: شغّل bash start.sh في الطرفية")
    pdf.step(3, "انتظر حتى يتم تحميل التطبيق. سيفتح المتصفح تلقائيًا.")
    pdf.step(4, "يفتح النظام على الرابط: http://localhost:5000/dashboard")
    pdf.note_box("إذا لم يفتح المتصفح تلقائيًا، افتح المتصفح يدويًا واذهب إلى http://localhost:5000/dashboard")

    # ── Chapter 3 ──
    pdf.add_page()
    pdf.chapter_title("3", "تسجيل الدخول وإعدادات اللغة")

    pdf.section_title("بيانات الدخول الافتراضية")
    pdf.body_text("في أول استخدام، سجل الدخول بحساب المدير الافتراضي:")
    pdf.bullet("اسم المستخدم: admin")
    pdf.bullet("كلمة المرور: admin123")
    pdf.body_text("يوصى بتغيير كلمة مرور المدير بعد أول تسجيل دخول.")

    pdf.section_title("رمز المنشأة")
    pdf.body_text(
        "إذا كنت تدير عيادة واحدة، اترك حقل رمز المنشأة فارغًا (سيتم استخدام "
        "DEFAULT تلقائيًا). في حالة وجود عدة منشآت، أدخل رمز المنشأة الخاص بك. "
        "رمز المنشأة هو معرف قصير مثل 'CLINIC01' أو 'HOSPITAL_A' يربط ببيانات "
        "وهوية تلك المنشأة."
    )
    pdf.body_text("يمكنك تصفح المنشآت المتاحة بالضغط على أيقونة البحث بجانب حقل رمز المنشأة.")

    pdf.section_title("التبديل بين الإنجليزية والعربية")
    pdf.body_text(
        "في صفحة تسجيل الدخول وفي جميع أنحاء التطبيق، ستجد زر تبديل اللغة. "
        "اضغط عليه للتبديل بين الإنجليزية والعربية. يتم تحديث الواجهة فورًا."
    )

    pdf.section_title("إظهار / إخفاء كلمة المرور")
    pdf.body_text(
        "عند كتابة كلمة المرور، اضغط على أيقونة العين بجانب حقل كلمة المرور "
        "لإظهار أو إخفاء الأحرف. هذا يساعد في تجنب أخطاء الكتابة."
    )

    pdf.section_title("تسجيل مستخدم جديد")
    pdf.body_text(
        "يمكن للمستخدمين الجدد التسجيل بالضغط على رابط 'تسجيل' في صفحة الدخول. "
        "املأ الاسم واسم المستخدم وكلمة المرور واختر الدور. بعد التسجيل، يجب "
        "أن يوافق المدير على الحساب قبل أن تتمكن من تسجيل الدخول."
    )

    # ── Chapter 4 ──
    pdf.add_page()
    pdf.chapter_title("4", "نظرة عامة على لوحة التحكم")
    pdf.body_text(
        "بعد تسجيل الدخول، ستظهر لوحة التحكم الرئيسية. هذه هي مركزك الرئيسي "
        "للتنقل في النظام. تعرض لوحة التحكم:"
    )
    pdf.bullet("إحصائيات سريعة: إجمالي المريضات، زيارات اليوم، التحاليل المعلقة")
    pdf.bullet("شريط بحث للعثور على المريضات بسرعة")
    pdf.bullet("قائمة جانبية للتنقل مع روابط لجميع الأقسام")
    pdf.bullet("اسم المنشأة والهوية البصرية في الأعلى")
    pdf.bullet("زر تبديل اللغة (إنجليزي / عربي)")
    pdf.bullet("ملف المستخدم وزر تسجيل الخروج")
    pdf.body_text(
        "استخدم القائمة الجانبية للتنقل بين الأقسام: المريضات، رعاية ما قبل الولادة، "
        "التحاليل، التصنيف، الولادة، ما بعد الولادة، والإدارة."
    )

    # ── Chapter 5 ──
    pdf.add_page()
    pdf.chapter_title("5", "إدارة المريضات")

    pdf.section_title("إضافة مريضة جديدة")
    pdf.step(1, "من القائمة الجانبية، اضغط 'المريضات' ثم 'إضافة مريضة جديدة'.")
    pdf.step(2, "املأ بيانات المريضة:")
    pdf.bullet("الاسم الكامل (مطلوب)")
    pdf.bullet("تاريخ الميلاد")
    pdf.bullet("رقم الهاتف")
    pdf.bullet("العنوان")
    pdf.bullet("ملاحظات التاريخ المرضي")
    pdf.step(3, "اضغط 'حفظ' لتسجيل المريضة.")
    pdf.body_text("ستظهر المريضة في قائمة المريضات فورًا.")

    pdf.section_title("البحث عن مريضة")
    pdf.body_text("استخدم شريط البحث في لوحة التحكم أو صفحة المريضات. يمكنك البحث بـ:")
    pdf.bullet("اسم المريضة (يدعم البحث الجزئي)")
    pdf.bullet("رقم المريضة")
    pdf.bullet("رقم الهاتف")
    pdf.body_text("يتم تحديث النتائج فورًا أثناء الكتابة.")

    pdf.section_title("ملف المريضة")
    pdf.body_text(
        "اضغط على اسم المريضة لفتح ملفها. تظهر صفحة الملف جميع معلومات المريضة:"
    )
    pdf.bullet("البيانات الشخصية ومعلومات الاتصال")
    pdf.bullet("التاريخ المرضي")
    pdf.bullet("تاريخ زيارات ما قبل الولادة")
    pdf.bullet("نتائج التحاليل والفحوصات")
    pdf.bullet("التصنيف وحالة المخاطر")
    pdf.bullet("سجلات الولادة")
    pdf.bullet("سجلات متابعة ما بعد الولادة")

    # ── Chapter 6 ──
    pdf.add_page()
    pdf.chapter_title("6", "رعاية ما قبل الولادة")

    pdf.section_title("تسجيل زيارة")
    pdf.step(1, "من القائمة الجانبية، اضغط 'رعاية ما قبل الولادة'.")
    pdf.step(2, "اختر المريضة من القائمة أو ابحث عنها.")
    pdf.step(3, "اضغط 'زيارة جديدة' لتسجيل كشف.")
    pdf.step(4, "أدخل تفاصيل الزيارة:")
    pdf.bullet("تاريخ الزيارة")
    pdf.bullet("عمر الحمل (بالأسابيع)")
    pdf.bullet("ضغط الدم، الوزن، ارتفاع قاع الرحم")
    pdf.bullet("نبض قلب الجنين")
    pdf.bullet("الملاحظات السريرية")
    pdf.step(5, "اضغط 'حفظ الزيارة' لتسجيل البيانات.")

    pdf.section_title("جدول المتابعة")
    pdf.body_text(
        "يساعد النظام في تتبع مواعيد المتابعة. بعد كل زيارة، يمكنك جدولة موعد "
        "الزيارة التالية. تعرض لوحة التحكم المواعيد القادمة."
    )

    # ── Chapter 7 ──
    pdf.add_page()
    pdf.chapter_title("7", "التحاليل والفحوصات")

    pdf.section_title("إضافة نتائج التحاليل")
    pdf.step(1, "من القائمة الجانبية، اضغط 'التحاليل'.")
    pdf.step(2, "اختر المريضة.")
    pdf.step(3, "اضغط 'إضافة تحليل'.")
    pdf.step(4, "اختر نوع التحليل (مثل صورة دم كاملة، سكر الدم، تحليل بول، أشعة صوتية).")
    pdf.step(5, "أدخل النتائج وأي ملاحظات.")
    pdf.step(6, "اضغط 'حفظ'.")

    pdf.section_title("عرض تاريخ التحاليل")
    pdf.body_text(
        "جميع تحاليل المريضة تظهر بترتيب زمني في ملفها الشخصي. يمكنك عرض "
        "الاتجاهات مع مرور الوقت ومقارنة النتائج."
    )

    # ── Chapter 8 ──
    pdf.add_page()
    pdf.chapter_title("8", "التصنيف وتقييم المخاطر")
    pdf.body_text(
        "يحتوي النظام على محرك تصنيف يعتمد على التعلم الآلي يساعد في تقييم "
        "مخاطر المريضة. يحلل بيانات المريضة وتاريخ الزيارات لتوفير درجات المخاطر "
        "والتوصيات."
    )
    pdf.step(1, "من القائمة الجانبية، اضغط 'التصنيف'.")
    pdf.step(2, "اختر مريضة.")
    pdf.step(3, "راجع عوامل الخطر المحسوبة تلقائيًا.")
    pdf.step(4, "يعرض النظام مستوى المخاطر (منخفض، متوسط، مرتفع) والتوصيات.")
    pdf.body_text(
        "يشمل التصنيف: عمر الأم، مؤشر كتلة الجسم، ضغط الدم، مستوى سكر الدم، "
        "مضاعفات الحمل السابقة، وغيرها من المعايير السريرية."
    )

    # ── Chapter 9 ──
    pdf.add_page()
    pdf.chapter_title("9", "إدارة الولادة")
    pdf.body_text("وحدة الولادة تتبع تفاصيل المخاض والولادة لكل مريضة.")
    pdf.step(1, "من القائمة الجانبية، اضغط 'الولادة'.")
    pdf.step(2, "اختر المريضة.")
    pdf.step(3, "سجل تفاصيل الولادة:")
    pdf.bullet("تاريخ ووقت الولادة")
    pdf.bullet("طريقة الولادة (طبيعية، قيصرية، شفط، ملقط)")
    pdf.bullet("مدة المخاض")
    pdf.bullet("المضاعفات (إن وجدت)")
    pdf.bullet("بيانات المولود: الوزن، الطول، محيط الرأس، درجات أبغار")
    pdf.step(4, "اضغط 'حفظ سجل الولادة'.")
    pdf.body_text("تُحفظ سجلات الولادة في تاريخ المريضة للرجوع إليها مستقبلاً.")

    # ── Chapter 10 ──
    pdf.add_page()
    pdf.chapter_title("10", "رعاية ما بعد الولادة")
    pdf.body_text("وحدة ما بعد الولادة تتابع رعاية الأم والطفل بعد الولادة.")
    pdf.step(1, "من القائمة الجانبية، اضغط 'ما بعد الولادة'.")
    pdf.step(2, "اختر المريضة.")
    pdf.step(3, "سجل تفاصيل زيارة ما بعد الولادة:")
    pdf.bullet("تاريخ المتابعة")
    pdf.bullet("الأم: ضغط الدم، درجة الحرارة، ارتداد الرحم، الإفرازات النفاسية، التئام الجرح")
    pdf.bullet("الطفل: حالة الرضاعة، الوزن، فحص الصفار، حالة التطعيم")
    pdf.step(4, "اضغط 'حفظ'.")
    pdf.body_text("يوصى بمتابعة ما بعد الولادة بعد أسبوع، أسبوعين، وستة أسابيع من الولادة.")

    # ── Chapter 11 ──
    pdf.add_page()
    pdf.chapter_title("11", "لوحة الإدارة")
    pdf.body_text("لوحة الإدارة متاحة للمستخدمين بدور المدير.")

    pdf.section_title("إدارة المستخدمين")
    pdf.body_text("يمكن للمديرين إدارة حسابات المستخدمين:")
    pdf.bullet("عرض جميع المستخدمين المسجلين")
    pdf.bullet("الموافقة على تسجيلات المستخدمين الجدد أو رفضها")
    pdf.bullet("تعديل أدوار المستخدمين (مدير، طبيب، ممرضة، استقبال)")
    pdf.bullet("إلغاء تنشيط أو حذف حسابات المستخدمين")
    pdf.step(1, "من القائمة الجانبية، اضغط 'الإدارة' ثم 'إدارة المستخدمين'.")
    pdf.step(2, "يظهر المستخدمون المعلقون مع زر 'موافقة'.")
    pdf.step(3, "اضغط 'موافقة' لمنح الوصول أو 'رفض' للحرمان.")

    pdf.section_title("إدارة المنشأة والهوية البصرية")
    pdf.body_text("يمكن لكل منشأة تخصيص هويتها البصرية. هذا يتحكم في ما يراه المستخدمون:")
    pdf.bullet("اسم العيادة: يظهر في شاشة الدخول والقائمة الجانبية والتذييل")
    pdf.bullet("رقم الدعم: يظهر في شاشة الدخول والتذييل")
    pdf.bullet("شعار العيادة: يمكن رفع صورة مخصصة (JPG/PNG) تظهر في شاشة الدخول والقائمة الجانبية")
    pdf.step(1, "اذهب إلى الإدارة ← إدارة المنشآت ← الهوية البصرية للعيادة.")
    pdf.step(2, "أدخل اسم العيادة ورقم الدعم.")
    pdf.step(3, "اضغط 'اختيار ملف' لرفع شعار.")
    pdf.step(4, "اضغط 'حفظ' لتحديث الهوية.")
    pdf.body_text("تصبح التغييرات سارية المفعول فورًا. كل منشأة ترى هويتها فقط.")

    # ── Chapter 12 ──
    pdf.add_page()
    pdf.chapter_title("12", "حل المشكلات")

    pdf.section_title("التطبيق لا يعمل")
    pdf.bullet("تأكد من تثبيت بايثون 3.8+ (إذا كان التشغيل من المصدر)")
    pdf.bullet("تأكد أن المنفذ 5000 غير مستخدم من تطبيق آخر")
    pdf.bullet("في ويندوز، شغّل start.bat كمسؤول")
    pdf.bullet("في لينكس/ماك، تأكد من صلاحيات التنفيذ لـ start.sh (chmod +x start.sh)")

    pdf.section_title("المتصفح لا يفتح تلقائيًا")
    pdf.body_text("افتح المتصفح يدويًا واذهب إلى http://localhost:5000/dashboard")

    pdf.section_title("لا يمكن تسجيل الدخول")
    pdf.bullet("تأكد أن Caps Lock غير مفعل")
    pdf.bullet("استخدم بيانات الدخول الافتراضية: admin / admin123")
    pdf.bullet("إذا سجلت حسابًا جديدًا، اطلب من المدير الموافقة عليه")
    pdf.bullet("تأكد من صحة رمز المنشأة")

    pdf.section_title("اللغة لا تعمل بشكل صحيح")
    pdf.body_text("اضغط على زر تبديل اللغة مرة أخرى. إذا استمرت المشكلة، حدّث الصفحة (F5).")

    # ── Chapter 13 ──
    pdf.add_page()
    pdf.chapter_title("13", "الدعم الفني")
    pdf.body_text("للدعم الفني والاستفسارات:")
    pdf.bullet("المطور: كريم عبد العزيز")
    pdf.bullet("الهاتف: 00201029927276")
    pdf.body_text("نرحب بملاحظاتكم للمساعدة في تطوير النظام.")

    out_path = os.path.join(OUT_DIR, "OMS_User_Manual_AR.pdf")
    pdf.output(out_path)
    return out_path


if __name__ == "__main__":
    en_path = build_english()
    ar_path = build_arabic()
    print(f"English: {en_path}")
    print(f"Arabic:  {ar_path}")
