import os
import json
import sqlite3
import time
from datetime import datetime
from typing import Optional

DB_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = "postgresql" in DB_URL

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        USE_POSTGRES = False


class DBConnection:
    def __init__(self):
        if USE_POSTGRES:
            for attempt in range(30):
                try:
                    self._pg = psycopg2.connect(DB_URL, connect_timeout=2)
                    self._pg.autocommit = True
                    self._sqlite = None
                    return
                except Exception:
                    if attempt == 29:
                        raise
                    time.sleep(1)
        else:
            _db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
            os.makedirs(_db_dir, exist_ok=True)
            self._sqlite = sqlite3.connect(os.path.join(_db_dir, "maternal_health.db"))
            self._sqlite.row_factory = sqlite3.Row
            self._sqlite.isolation_level = None
            self._sqlite.execute("PRAGMA journal_mode=WAL")
            self._sqlite.execute("PRAGMA foreign_keys = ON")
            self._pg = None

    def execute(self, sql, params=None):
        if self._pg:
            cur = self._pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params or ())
            return cur
        return self._sqlite.execute(sql, params or ())

    def close(self):
        if self._pg:
            self._pg.close()
        elif self._sqlite:
            self._sqlite.close()


def get_conn():
    return DBConnection()


def _val(cur):
    row = cur.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        vals = list(row.values())
        return vals[0] if vals else None
    return row[0]


def _migrate_sqlite(conn):
    """Add new columns to existing tables for SQLite."""
    migrations = [
        ("patients", [
            ("phone", "TEXT"),
            ("email", "TEXT"),
            ("date_of_birth", "TEXT"),
            ("address", "TEXT"),
            ("emergency_contact_name", "TEXT"),
            ("emergency_contact_phone", "TEXT"),
            ("blood_type", "TEXT"),
            ("photo_path", "TEXT"),
            ("case_type", "TEXT DEFAULT 'follow-up'"),
            ("facility_code", "TEXT DEFAULT 'DEFAULT'"),
        ]),
        ("users", [
            ("approved", "INT DEFAULT 0"),
            ("facility_code", "TEXT DEFAULT 'DEFAULT'"),
        ]),
        ("investigations", [
            ("file_path", "TEXT"),
        ]),
    ]
    for table, columns in migrations:
        for col_name, col_type in columns:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass


def init_db():
    conn = get_conn()
    if USE_POSTGRES:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(200),
                age INT,
                date_of_birth VARCHAR(20),
                bmi_pre_pregnancy DECIMAL(5,2),
                expected_due_date VARCHAR(20),
                phone VARCHAR(20),
                email VARCHAR(200),
                address TEXT,
                emergency_contact_name VARCHAR(200),
                emergency_contact_phone VARCHAR(20),
                blood_type VARCHAR(5),
                photo_path TEXT,
                case_type VARCHAR(20) DEFAULT 'follow-up',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                gestational_age INT,
                blood_pressure_sys INT,
                blood_pressure_dia INT,
                glucose_level DECIMAL(6,2),
                heart_rate INT,
                fetal_heart_rate INT,
                fetal_movement_count INT,
                temperature DECIMAL(4,1),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_assessments (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                assessment_type VARCHAR(50),
                risk_level VARCHAR(20),
                risk_score DECIMAL(5,4),
                details JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                hashed_password VARCHAR(200) NOT NULL,
                role VARCHAR(20) DEFAULT 'clinician',
                approved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ultrasound_exams (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                exam_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gestational_age INT,
                biparietal_diameter DECIMAL(6,2),
                femur_length DECIMAL(6,2),
                abdominal_circumference DECIMAL(6,2),
                head_circumference DECIMAL(6,2),
                estimated_weight DECIMAL(7,2),
                amniotic_fluid_index DECIMAL(6,2),
                placenta_position VARCHAR(50),
                presentation VARCHAR(50),
                heart_rate INT,
                crl DECIMAL(6,2),
                findings JSONB,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maternal_history (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id) UNIQUE,
                gravida INT DEFAULT 0,
                para INT DEFAULT 0,
                previous_cesarean BOOLEAN DEFAULT FALSE,
                previous_miscarriages INT DEFAULT 0,
                chronic_conditions TEXT,
                allergies TEXT,
                medications TEXT,
                family_history TEXT,
                blood_type VARCHAR(5),
                rh_factor VARCHAR(5),
                smoking BOOLEAN DEFAULT FALSE,
                alcohol BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paternal_history (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id) UNIQUE,
                age INT,
                blood_type VARCHAR(5),
                rh_factor VARCHAR(5),
                genetic_disorders TEXT,
                chronic_conditions TEXT,
                medications TEXT,
                smoking BOOLEAN DEFAULT FALSE,
                alcohol BOOLEAN DEFAULT FALSE,
                family_history TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admissions (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                ward_type VARCHAR(30),
                bed_number VARCHAR(20),
                admission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admission_reason TEXT,
                admitted_by VARCHAR(100),
                status VARCHAR(20) DEFAULT 'active',
                discharge_date TIMESTAMP,
                discharge_summary TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                admission_id INT REFERENCES admissions(id),
                delivery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gestational_age INT,
                mode_of_delivery VARCHAR(50),
                presentation VARCHAR(50),
                labor_duration_minutes INT,
                complications TEXT,
                blood_loss_ml INT,
                perineal_status VARCHAR(50),
                episiotomy BOOLEAN DEFAULT FALSE,
                placenta_delivery VARCHAR(50),
                attended_by VARCHAR(100),
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS newborns (
                id SERIAL PRIMARY KEY,
                delivery_id INT REFERENCES deliveries(id),
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                name VARCHAR(200),
                gender VARCHAR(10),
                birth_weight DECIMAL(5,2),
                birth_length DECIMAL(5,2),
                head_circumference DECIMAL(5,2),
                apgar_1min INT,
                apgar_5min INT,
                apgar_10min INT,
                feeding_method VARCHAR(50),
                immunizations TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS antenatal_visits (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                visit_number INT,
                visit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gestational_age INT,
                blood_pressure_sys INT,
                blood_pressure_dia INT,
                weight DECIMAL(5,1),
                fundal_height DECIMAL(5,1),
                fetal_presentation VARCHAR(30),
                fetal_heart_rate INT,
                urine_protein VARCHAR(20),
                urine_glucose VARCHAR(20),
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                test_type VARCHAR(100),
                result TEXT,
                normal_range VARCHAR(100),
                notes TEXT,
                file_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                code VARCHAR(50) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                type VARCHAR(20) DEFAULT 'clinic',
                address TEXT,
                phone VARCHAR(20),
                governorate VARCHAR(100),
                is_active INT DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add branding columns to facilities
        for col in ['branding_name', 'support_phone', 'branding_logo_path']:
            try:
                conn.execute(f"ALTER TABLE facilities ADD COLUMN {col} TEXT")
            except Exception:
                pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS medical_images (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                image_type VARCHAR(50),
                file_path TEXT,
                description TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS follow_ups (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                follow_up_date DATE NOT NULL,
                type VARCHAR(50) DEFAULT 'routine',
                status VARCHAR(20) DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                name TEXT,
                age INT,
                date_of_birth TEXT,
                bmi_pre_pregnancy REAL,
                expected_due_date TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                blood_type TEXT,
                photo_path TEXT,
                case_type TEXT DEFAULT 'follow-up',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                gestational_age INT,
                blood_pressure_sys INT,
                blood_pressure_dia INT,
                glucose_level REAL,
                heart_rate INT,
                fetal_heart_rate INT,
                fetal_movement_count INT,
                temperature REAL,
                recorded_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                assessment_type TEXT,
                risk_level TEXT,
                risk_score REAL,
                details TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'clinician',
                approved INT DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ultrasound_exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                exam_date TEXT DEFAULT (datetime('now')),
                gestational_age INT,
                biparietal_diameter REAL,
                femur_length REAL,
                abdominal_circumference REAL,
                head_circumference REAL,
                estimated_weight REAL,
                amniotic_fluid_index REAL,
                placenta_position TEXT,
                presentation TEXT,
                heart_rate INT,
                crl REAL,
                findings TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maternal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id) UNIQUE,
                gravida INT DEFAULT 0,
                para INT DEFAULT 0,
                previous_cesarean INT DEFAULT 0,
                previous_miscarriages INT DEFAULT 0,
                chronic_conditions TEXT,
                allergies TEXT,
                medications TEXT,
                family_history TEXT,
                blood_type TEXT,
                rh_factor TEXT,
                smoking INT DEFAULT 0,
                alcohol INT DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paternal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id) UNIQUE,
                age INT,
                blood_type TEXT,
                rh_factor TEXT,
                genetic_disorders TEXT,
                chronic_conditions TEXT,
                medications TEXT,
                smoking INT DEFAULT 0,
                alcohol INT DEFAULT 0,
                family_history TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                ward_type TEXT,
                bed_number TEXT,
                admission_date TEXT DEFAULT (datetime('now')),
                admission_reason TEXT,
                admitted_by TEXT,
                status TEXT DEFAULT 'active',
                discharge_date TEXT,
                discharge_summary TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                admission_id INT,
                delivery_date TEXT DEFAULT (datetime('now')),
                gestational_age INT,
                mode_of_delivery TEXT,
                presentation TEXT,
                labor_duration_minutes INT,
                complications TEXT,
                blood_loss_ml INT,
                perineal_status TEXT,
                episiotomy INT DEFAULT 0,
                placenta_delivery TEXT,
                attended_by TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS newborns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delivery_id INT,
                patient_id TEXT REFERENCES patients(patient_id),
                name TEXT,
                gender TEXT,
                birth_weight REAL,
                birth_length REAL,
                head_circumference REAL,
                apgar_1min INT,
                apgar_5min INT,
                apgar_10min INT,
                feeding_method TEXT,
                immunizations TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS antenatal_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                visit_number INT,
                visit_date TEXT DEFAULT (datetime('now')),
                gestational_age INT,
                blood_pressure_sys INT,
                blood_pressure_dia INT,
                weight REAL,
                fundal_height REAL,
                fetal_presentation TEXT,
                fetal_heart_rate INT,
                urine_protein TEXT,
                urine_glucose TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                test_date TEXT DEFAULT (datetime('now')),
                test_type TEXT,
                result TEXT,
                normal_range TEXT,
                notes TEXT,
                file_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'clinic',
                address TEXT,
                phone TEXT,
                governorate TEXT,
                is_active INT DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                from_facility TEXT NOT NULL,
                to_facility TEXT NOT NULL,
                referral_reason TEXT,
                referral_notes TEXT,
                urgency TEXT DEFAULT 'routine',
                status TEXT DEFAULT 'pending',
                accepted_by TEXT,
                outcome TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS icd10_codes (
                code TEXT PRIMARY KEY,
                title_ar TEXT,
                title_en TEXT,
                category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shift_handovers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_code TEXT REFERENCES facilities(code),
                shift_date TEXT NOT NULL,
                shift_type TEXT NOT NULL,
                handed_over_by TEXT NOT NULL,
                received_by TEXT,
                active_patients INT DEFAULT 0,
                high_risk_patients INT DEFAULT 0,
                deliveries_count INT DEFAULT 0,
                notes TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS medical_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                image_type TEXT,
                file_path TEXT,
                description TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS follow_ups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT REFERENCES patients(patient_id),
                follow_up_date TEXT NOT NULL,
                type TEXT DEFAULT 'routine',
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        _migrate_sqlite(conn)
    conn.close()


def add_patient(patient_id, name, age, bmi, due_date,
                phone=None, email=None, date_of_birth=None, address=None,
                emergency_contact_name=None, emergency_contact_phone=None,
                blood_type=None, photo_path=None, case_type='follow-up', facility_code='DEFAULT'):
    conn = get_conn()
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO patients (patient_id, name, age, bmi_pre_pregnancy, expected_due_date, phone, email, date_of_birth, address, emergency_contact_name, emergency_contact_phone, blood_type, photo_path, case_type, facility_code) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (patient_id) DO NOTHING",
            (patient_id, name, age, bmi, due_date, phone, email, date_of_birth, address,
             emergency_contact_name, emergency_contact_phone, blood_type, photo_path, case_type, facility_code)
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                patient_id VARCHAR(50) REFERENCES patients(patient_id),
                from_facility VARCHAR(50) NOT NULL,
                to_facility VARCHAR(50) NOT NULL,
                referral_reason TEXT,
                referral_notes TEXT,
                urgency VARCHAR(20) DEFAULT 'routine',
                status VARCHAR(20) DEFAULT 'pending',
                accepted_by VARCHAR(100),
                outcome TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS icd10_codes (
                code VARCHAR(20) PRIMARY KEY,
                title_ar TEXT,
                title_en TEXT,
                category VARCHAR(50)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shift_handovers (
                id SERIAL PRIMARY KEY,
                facility_code VARCHAR(50) REFERENCES facilities(code),
                shift_date DATE NOT NULL,
                shift_type VARCHAR(20) NOT NULL,
                handed_over_by VARCHAR(100) NOT NULL,
                received_by VARCHAR(100),
                active_patients INT DEFAULT 0,
                high_risk_patients INT DEFAULT 0,
                deliveries_count INT DEFAULT 0,
                notes TEXT,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.execute(
            "INSERT OR IGNORE INTO patients (patient_id, name, age, bmi_pre_pregnancy, expected_due_date, phone, email, date_of_birth, address, emergency_contact_name, emergency_contact_phone, blood_type, photo_path, case_type, facility_code) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (patient_id, name, age, bmi, due_date, phone, email, date_of_birth, address,
             emergency_contact_name, emergency_contact_phone, blood_type, photo_path, case_type, facility_code)
        )
    conn.close()


def update_patient(patient_id, **kwargs):
    conn = get_conn()
    allowed = {"name", "age", "bmi", "due_date", "expected_due_date",
               "phone", "email", "date_of_birth", "address",
               "emergency_contact_name", "emergency_contact_phone",
               "blood_type", "bmi_pre_pregnancy", "photo_path", "case_type"}
    col_map = {"bmi": "bmi_pre_pregnancy", "due_date": "expected_due_date"}
    updates = []
    params = []
    for k, v in kwargs.items():
        col = col_map.get(k, k)
        if col not in allowed or v is None:
            continue
        updates.append(f"{col} = {'%s' if USE_POSTGRES else '?'}")
        params.append(v)
    if not updates:
        conn.close()
        return False
    params.append(patient_id)
    sql = f"UPDATE patients SET {', '.join(updates)} WHERE patient_id = {'%s' if USE_POSTGRES else '?'}"
    conn.execute(sql, params)
    conn.close()
    return True


def delete_patient(patient_id, facility_code=None):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    tables = ["referrals", "follow_ups", "medical_images", "newborns", "deliveries",
              "admissions", "measurements", "risk_assessments", "ultrasound_exams",
              "maternal_history", "paternal_history", "antenatal_visits",
              "investigations", "patients"]
    for table in tables:
        where = f"patient_id = {ph}"
        args = [patient_id]
        if facility_code:
            if table in ("admissions", "deliveries", "newborns", "measurements", "risk_assessments",
                         "ultrasound_exams", "maternal_history", "paternal_history", "antenatal_visits",
                         "investigations"):
                # These tables don't have facility_code, just use patient_id
                pass
        conn.execute(f"DELETE FROM {table} WHERE {where}", args)
    conn.close()


def get_patient(patient_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM patients WHERE patient_id = ?" if not USE_POSTGRES else
                       "SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_all_patients(page=1, per_page=20, facility_code=None):
    conn = get_conn()
    offset = (page - 1) * per_page
    if facility_code:
        ph = "?" if not USE_POSTGRES else "%s"
        if USE_POSTGRES:
            cur = conn.execute(f"SELECT * FROM patients WHERE facility_code = {ph} ORDER BY created_at DESC LIMIT %s OFFSET %s", (facility_code, per_page, offset))
            total = _val(conn.execute(f"SELECT COUNT(*) FROM patients WHERE facility_code = {ph}", (facility_code,)))
        else:
            cur = conn.execute(f"SELECT * FROM patients WHERE facility_code = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (facility_code, per_page, offset))
            total = _val(conn.execute(f"SELECT COUNT(*) FROM patients WHERE facility_code = ?", (facility_code,)))
    else:
        if USE_POSTGRES:
            cur = conn.execute("SELECT * FROM patients ORDER BY created_at DESC LIMIT %s OFFSET %s", (per_page, offset))
            total = _val(conn.execute("SELECT COUNT(*) FROM patients"))
        else:
            cur = conn.execute("SELECT * FROM patients ORDER BY created_at DESC LIMIT ? OFFSET ?", (per_page, offset))
            total = _val(conn.execute("SELECT COUNT(*) FROM patients"))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def add_measurement(patient_id, data):
    conn = get_conn()
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO measurements (patient_id, gestational_age, blood_pressure_sys, blood_pressure_dia, glucose_level, heart_rate, fetal_heart_rate, fetal_movement_count, temperature) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (patient_id, data.get('gestational_age'), data.get('blood_pressure_sys'),
             data.get('blood_pressure_dia'), data.get('glucose_level'), data.get('heart_rate'),
             data.get('fetal_heart_rate'), data.get('fetal_movement_count'), data.get('temperature'))
        )
    else:
        conn.execute(
            "INSERT INTO measurements (patient_id, gestational_age, blood_pressure_sys, blood_pressure_dia, glucose_level, heart_rate, fetal_heart_rate, fetal_movement_count, temperature) VALUES (?,?,?,?,?,?,?,?,?)",
            (patient_id, data.get('gestational_age'), data.get('blood_pressure_sys'),
             data.get('blood_pressure_dia'), data.get('glucose_level'), data.get('heart_rate'),
             data.get('fetal_heart_rate'), data.get('fetal_movement_count'), data.get('temperature'))
        )
    conn.close()


def update_measurement(measurement_id, data):
    conn = get_conn()
    allowed_fields = {"gestational_age", "blood_pressure_sys", "blood_pressure_dia", "glucose_level",
                      "heart_rate", "fetal_heart_rate", "fetal_movement_count", "temperature"}
    updates = []
    params = []
    for k, v in data.items():
        if k in allowed_fields and v is not None:
            updates.append(f"{k} = {'%s' if USE_POSTGRES else '?'}")
            params.append(v)
    if not updates:
        conn.close()
        return False
    params.append(measurement_id)
    sql = f"UPDATE measurements SET {', '.join(updates)} WHERE id = {'%s' if USE_POSTGRES else '?'}"
    conn.execute(sql, params)
    conn.close()
    return True


def delete_measurement(measurement_id):
    conn = get_conn()
    conn.execute("DELETE FROM measurements WHERE id = ?" if not USE_POSTGRES else
                 "DELETE FROM measurements WHERE id = %s", (measurement_id,))
    conn.close()


def get_measurements(patient_id, page=1, per_page=20):
    conn = get_conn()
    offset = (page - 1) * per_page
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM measurements WHERE patient_id = %s ORDER BY recorded_at DESC LIMIT %s OFFSET %s",
                           (patient_id, per_page, offset))
        total = _val(conn.execute("SELECT COUNT(*) FROM measurements WHERE patient_id = %s", (patient_id,)))
    else:
        cur = conn.execute("SELECT * FROM measurements WHERE patient_id = ? ORDER BY recorded_at DESC LIMIT ? OFFSET ?",
                           (patient_id, per_page, offset))
        total = _val(conn.execute("SELECT COUNT(*) FROM measurements WHERE patient_id = ?", (patient_id,)))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_assessments(patient_id, page=1, per_page=20):
    conn = get_conn()
    offset = (page - 1) * per_page
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM risk_assessments WHERE patient_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                           (patient_id, per_page, offset))
        total = _val(conn.execute("SELECT COUNT(*) FROM risk_assessments WHERE patient_id = %s", (patient_id,)))
    else:
        cur = conn.execute("SELECT * FROM risk_assessments WHERE patient_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                           (patient_id, per_page, offset))
        total = _val(conn.execute("SELECT COUNT(*) FROM risk_assessments WHERE patient_id = ?", (patient_id,)))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("details") and isinstance(d["details"], str):
            try:
                d["details"] = json.loads(d["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result, total


def get_recent_assessments(limit=10):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM risk_assessments ORDER BY created_at DESC LIMIT %s", (limit,))
    else:
        cur = conn.execute("SELECT * FROM risk_assessments ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("details") and isinstance(d["details"], str):
            try:
                d["details"] = json.loads(d["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


def save_assessment(patient_id, assessment_type, risk_level, risk_score, details):
    conn = get_conn()
    details_json = json.dumps(details, default=str)
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO risk_assessments (patient_id, assessment_type, risk_level, risk_score, details) VALUES (%s,%s,%s,%s,%s)",
            (patient_id, assessment_type, risk_level, risk_score, details_json)
        )
    else:
        conn.execute(
            "INSERT INTO risk_assessments (patient_id, assessment_type, risk_level, risk_score, details) VALUES (?,?,?,?,?)",
            (patient_id, assessment_type, risk_level, risk_score, details_json)
        )
    conn.close()


def create_user(username, hashed_password, role="clinician"):
    conn = get_conn()
    # First user ever gets auto-approved as admin
    existing_count = _val(conn.execute("SELECT COUNT(*) FROM users"))
    approved = 1 if existing_count == 0 else 0
    admin_role = "admin" if existing_count == 0 else role
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO users (username, hashed_password, role, approved) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING",
            (username, hashed_password, admin_role, approved)
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, hashed_password, role, approved) VALUES (?, ?, ?, ?)",
            (username, hashed_password, admin_role, approved)
        )
    conn.close()


def get_user(username):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM users WHERE username = %s", (username,))
    else:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def approve_user(username):
    conn = get_conn()
    conn.execute("UPDATE users SET approved = 1 WHERE username = ?" if not USE_POSTGRES else
                 "UPDATE users SET approved = TRUE WHERE username = %s", (username,))
    conn.close()


def reject_user(username):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE username = ?" if not USE_POSTGRES else
                 "DELETE FROM users WHERE username = %s", (username,))
    conn.close()


def get_pending_users():
    conn = get_conn()
    cur = conn.execute("SELECT id, username, role, created_at FROM users WHERE approved = 0" if not USE_POSTGRES else
                       "SELECT id, username, role, created_at FROM users WHERE approved = FALSE")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_ultrasound_exam(patient_id, data):
    if not data:
        return
    conn = get_conn()
    cols = ", ".join(data.keys())
    vals = ", ".join([("%s" if USE_POSTGRES else "?") for _ in data])
    if USE_POSTGRES:
        conn.execute(
            f"INSERT INTO ultrasound_exams (patient_id, {cols}) VALUES (%s, {vals})",
            (patient_id, *data.values())
        )
    else:
        conn.execute(
            f"INSERT INTO ultrasound_exams (patient_id, {cols}) VALUES (?, {vals})",
            (patient_id, *data.values())
        )
    conn.close()


def update_ultrasound_exam(exam_id, data):
    if not data:
        return
    conn = get_conn()
    updates = []
    params = []
    for k, v in data.items():
        updates.append(f"{k} = {'%s' if USE_POSTGRES else '?'}")
        params.append(v)
    params.append(exam_id)
    sql = f"UPDATE ultrasound_exams SET {', '.join(updates)} WHERE id = {'%s' if USE_POSTGRES else '?'}"
    conn.execute(sql, params)
    conn.close()


def delete_ultrasound_exam(exam_id):
    conn = get_conn()
    conn.execute("DELETE FROM ultrasound_exams WHERE id = ?" if not USE_POSTGRES else
                 "DELETE FROM ultrasound_exams WHERE id = %s", (exam_id,))
    conn.close()


def get_ultrasound_exams(patient_id):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM ultrasound_exams WHERE patient_id = %s ORDER BY exam_date DESC", (patient_id,))
    else:
        cur = conn.execute("SELECT * FROM ultrasound_exams WHERE patient_id = ? ORDER BY exam_date DESC", (patient_id,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("findings"), str):
            try:
                d["findings"] = json.loads(d["findings"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


def get_ultrasound_exam(exam_id):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM ultrasound_exams WHERE id = %s", (exam_id,))
    else:
        cur = conn.execute("SELECT * FROM ultrasound_exams WHERE id = ?", (exam_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        d = dict(row)
        if isinstance(d.get("findings"), str):
            try:
                d["findings"] = json.loads(d["findings"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d
    return None


def upsert_maternal_history(patient_id, data):
    if not data:
        return
    conn = get_conn()
    cols = ", ".join(data.keys())
    ph = ", ".join(["%s" if USE_POSTGRES else "?" for _ in data])
    if USE_POSTGRES:
        conn.execute(
            f"INSERT INTO maternal_history (patient_id, {cols}) VALUES (%s, {ph}) "
            f"ON CONFLICT (patient_id) DO UPDATE SET {', '.join([f'{k} = %s' for k in data])}, updated_at = CURRENT_TIMESTAMP",
            (patient_id, *data.values(), *data.values())
        )
    else:
        existing = conn.execute("SELECT id FROM maternal_history WHERE patient_id = ?", (patient_id,)).fetchone()
        if existing:
            set_clause = ", ".join([f"{k} = ?" for k in data])
            conn.execute(f"UPDATE maternal_history SET {set_clause}, updated_at = datetime('now') WHERE patient_id = ?",
                         (*data.values(), patient_id))
        else:
            conn.execute(
                f"INSERT INTO maternal_history (patient_id, {cols}) VALUES (?, {ph})",
                (patient_id, *data.values())
            )
    conn.close()


def get_maternal_history(patient_id):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM maternal_history WHERE patient_id = %s", (patient_id,))
    else:
        cur = conn.execute("SELECT * FROM maternal_history WHERE patient_id = ?", (patient_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def upsert_paternal_history(patient_id, data):
    if not data:
        return
    conn = get_conn()
    cols = ", ".join(data.keys())
    ph = ", ".join(["%s" if USE_POSTGRES else "?" for _ in data])
    if USE_POSTGRES:
        conn.execute(
            f"INSERT INTO paternal_history (patient_id, {cols}) VALUES (%s, {ph}) "
            f"ON CONFLICT (patient_id) DO UPDATE SET {', '.join([f'{k} = %s' for k in data])}, updated_at = CURRENT_TIMESTAMP",
            (patient_id, *data.values(), *data.values())
        )
    else:
        existing = conn.execute("SELECT id FROM paternal_history WHERE patient_id = ?", (patient_id,)).fetchone()
        if existing:
            set_clause = ", ".join([f"{k} = ?" for k in data])
            conn.execute(f"UPDATE paternal_history SET {set_clause}, updated_at = datetime('now') WHERE patient_id = ?",
                         (*data.values(), patient_id))
        else:
            conn.execute(
                f"INSERT INTO paternal_history (patient_id, {cols}) VALUES (?, {ph})",
                (patient_id, *data.values())
            )
    conn.close()


def get_paternal_history(patient_id):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute("SELECT * FROM paternal_history WHERE patient_id = %s", (patient_id,))
    else:
        cur = conn.execute("SELECT * FROM paternal_history WHERE patient_id = ?", (patient_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def add_admission(patient_id, ward_type, bed_number=None, admission_reason=None, admitted_by=None):
    conn = get_conn()
    if USE_POSTGRES:
        cur = conn.execute(
            "INSERT INTO admissions (patient_id, ward_type, bed_number, admission_reason, admitted_by) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (patient_id, ward_type, bed_number, admission_reason, admitted_by)
        )
        admission_id = cur.fetchone()["id"]
    else:
        conn.execute(
            "INSERT INTO admissions (patient_id, ward_type, bed_number, admission_reason, admitted_by) "
            "VALUES (?,?,?,?,?)",
            (patient_id, ward_type, bed_number, admission_reason, admitted_by)
        )
        admission_id = conn._sqlite.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return admission_id


def discharge_patient(admission_id, discharge_summary=None):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    timestamp = "CURRENT_TIMESTAMP" if USE_POSTGRES else "datetime('now')"
    conn.execute(
        f"UPDATE admissions SET status = 'discharged', discharge_date = {timestamp}, discharge_summary = {ph} WHERE id = {ph}",
        (discharge_summary, admission_id)
    )
    conn.close()


def get_admissions(patient_id=None, status=None):
    conn = get_conn()
    sql = "SELECT a.*, p.name as patient_name FROM admissions a JOIN patients p ON a.patient_id = p.patient_id"
    params = []
    clauses = []
    if patient_id:
        clauses.append(f"a.patient_id = {'%s' if USE_POSTGRES else '?'}")
        params.append(patient_id)
    if status:
        clauses.append(f"a.status = {'%s' if USE_POSTGRES else '?'}")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY a.admission_date DESC"
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_delivery(patient_id, data):
    if not data:
        return
    conn = get_conn()
    cols = ", ".join(data.keys())
    vals = ", ".join([("%s" if USE_POSTGRES else "?") for _ in data])
    if USE_POSTGRES:
        conn.execute(f"INSERT INTO deliveries (patient_id, {cols}) VALUES (%s, {vals})", (patient_id, *data.values()))
    else:
        conn.execute(f"INSERT INTO deliveries (patient_id, {cols}) VALUES (?, {vals})", (patient_id, *data.values()))
    conn.close()


def get_deliveries(patient_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM deliveries WHERE patient_id = ? ORDER BY delivery_date DESC" if not USE_POSTGRES else
                       "SELECT * FROM deliveries WHERE patient_id = %s ORDER BY delivery_date DESC", (patient_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_newborn(patient_id, data):
    if not data:
        return
    conn = get_conn()
    cols = ", ".join(data.keys())
    vals = ", ".join([("%s" if USE_POSTGRES else "?") for _ in data])
    if USE_POSTGRES:
        conn.execute(f"INSERT INTO newborns (patient_id, {cols}) VALUES (%s, {vals})", (patient_id, *data.values()))
    else:
        conn.execute(f"INSERT INTO newborns (patient_id, {cols}) VALUES (?, {vals})", (patient_id, *data.values()))
    conn.close()


def get_newborns(patient_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM newborns WHERE patient_id = ? ORDER BY created_at DESC" if not USE_POSTGRES else
                       "SELECT * FROM newborns WHERE patient_id = %s ORDER BY created_at DESC", (patient_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_antenatal_visit(patient_id, data):
    if not data:
        return
    conn = get_conn()
    cols = ", ".join(data.keys())
    vals = ", ".join([("%s" if USE_POSTGRES else "?") for _ in data])
    if USE_POSTGRES:
        conn.execute(f"INSERT INTO antenatal_visits (patient_id, {cols}) VALUES (%s, {vals})", (patient_id, *data.values()))
    else:
        conn.execute(f"INSERT INTO antenatal_visits (patient_id, {cols}) VALUES (?, {vals})", (patient_id, *data.values()))
    conn.close()


def get_antenatal_visits(patient_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM antenatal_visits WHERE patient_id = ? ORDER BY visit_date DESC" if not USE_POSTGRES else
                       "SELECT * FROM antenatal_visits WHERE patient_id = %s ORDER BY visit_date DESC", (patient_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_investigation(patient_id, data):
    if not data:
        return None
    conn = get_conn()
    cols = ", ".join(data.keys())
    vals = ", ".join([("%s" if USE_POSTGRES else "?") for _ in data])
    if USE_POSTGRES:
        cur = conn.execute(f"INSERT INTO investigations (patient_id, {cols}) VALUES (%s, {vals}) RETURNING id", (patient_id, *data.values()))
        inv_id = cur.fetchone()[0]
    else:
        cur = conn.execute(f"INSERT INTO investigations (patient_id, {cols}) VALUES (?, {vals})", (patient_id, *data.values()))
        inv_id = cur.lastrowid
    conn.close()
    return inv_id


def update_investigation(inv_id, data):
    if not data:
        return
    conn = get_conn()
    set_clause = ", ".join([f"{k} = ?" for k in data])
    conn.execute(f"UPDATE investigations SET {set_clause} WHERE id = ?", (*data.values(), inv_id))
    conn.close()


def get_investigations(patient_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM investigations WHERE patient_id = ? ORDER BY test_date DESC" if not USE_POSTGRES else
                       "SELECT * FROM investigations WHERE patient_id = %s ORDER BY test_date DESC", (patient_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ward_stats():
    conn = get_conn()
    cur = conn.execute("SELECT ward_type, COUNT(*) as count FROM admissions WHERE status = 'active' GROUP BY ward_type")
    by_ward = {r["ward_type"]: r["count"] for r in cur.fetchall()} if not USE_POSTGRES else {}
    total = _val(conn.execute("SELECT COUNT(*) FROM admissions WHERE status = 'active'"))
    deliveries_today = _val(conn.execute(
        "SELECT COUNT(*) FROM deliveries WHERE DATE(delivery_date) = DATE('now')" if not USE_POSTGRES else
        "SELECT COUNT(*) FROM deliveries WHERE delivery_date::date = CURRENT_DATE"
    ))
    conn.close()
    return {
        "total_active": total or 0,
        "by_ward": by_ward,
        "deliveries_today": deliveries_today or 0,
    }


def add_medical_image(patient_id, image_type, file_path, description=None, notes=None):
    conn = get_conn()
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO medical_images (patient_id, image_type, file_path, description, notes) VALUES (%s,%s,%s,%s,%s)",
            (patient_id, image_type, file_path, description, notes)
        )
    else:
        conn.execute(
            "INSERT INTO medical_images (patient_id, image_type, file_path, description, notes) VALUES (?,?,?,?,?)",
            (patient_id, image_type, file_path, description, notes)
        )
    conn.close()


def get_medical_images(patient_id):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM medical_images WHERE patient_id = ? ORDER BY created_at DESC" if not USE_POSTGRES else
                       "SELECT * FROM medical_images WHERE patient_id = %s ORDER BY created_at DESC", (patient_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_medical_image(image_id):
    conn = get_conn()
    cur = conn.execute("SELECT file_path FROM medical_images WHERE id = ?" if not USE_POSTGRES else
                       "SELECT file_path FROM medical_images WHERE id = %s", (image_id,))
    row = cur.fetchone()
    if row:
        path = row["file_path"]
        if path and os.path.exists(path):
            os.remove(path)
    conn.execute("DELETE FROM medical_images WHERE id = ?" if not USE_POSTGRES else
                 "DELETE FROM medical_images WHERE id = %s", (image_id,))
    conn.close()




# ── Facility Management ──
def add_facility(code, name, type_='clinic', address=None, phone=None, governorate=None):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    try:
        conn.execute(f"INSERT INTO facilities (code, name, type, address, phone, governorate) VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
                     (code, name, type_, address, phone, governorate))
        conn.close()
        return True
    except Exception:
        conn.close()
        return False

def get_facility(code):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    cur = conn.execute(f"SELECT * FROM facilities WHERE code = {ph}", (code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_facilities():
    conn = get_conn()
    cur = conn.execute("SELECT * FROM facilities ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_facility(code, data):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    updates = [f"{k} = {ph}" for k in data]
    params = list(data.values()) + [code]
    conn.execute(f"UPDATE facilities SET {', '.join(updates)} WHERE code = {ph}", params)
    conn.close()


# ── Referral Functions ──
def add_referral(patient_id, from_facility, to_facility, reason=None, notes=None, urgency='routine'):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    conn.execute(f"INSERT INTO referrals (patient_id, from_facility, to_facility, referral_reason, referral_notes, urgency) VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
                 (patient_id, from_facility, to_facility, reason, notes, urgency))
    conn.close()

def get_referrals(patient_id=None, facility_code=None):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    sql = "SELECT r.*, p.name as patient_name FROM referrals r LEFT JOIN patients p ON r.patient_id = p.patient_id WHERE 1=1"
    args = []
    if patient_id:
        sql += f" AND r.patient_id = {ph}"
        args.append(patient_id)
    if facility_code:
        sql += f" AND (r.from_facility = {ph} OR r.to_facility = {ph})"
        args.append(facility_code)
    sql += " ORDER BY r.created_at DESC"
    cur = conn.execute(sql, args)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_referral(ref_id, data):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    updates = [f"{k} = {ph}" for k in data]
    params = list(data.values()) + [ref_id]
    conn.execute(f"UPDATE referrals SET {', '.join(updates)} WHERE id = {ph}", params)
    conn.close()


# ── Shift Handover Functions ──
def create_handover(facility_code, shift_date, shift_type, handed_over_by, active_patients=0, high_risk_patients=0, deliveries_count=0, notes=None):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    conn.execute(f"INSERT INTO shift_handovers (facility_code, shift_date, shift_type, handed_over_by, active_patients, high_risk_patients, deliveries_count, notes) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
                 (facility_code, shift_date, shift_type, handed_over_by, active_patients, high_risk_patients, deliveries_count, notes))
    conn.close()

def get_handovers(facility_code, limit=20):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    lim_ph = "?" if not USE_POSTGRES else "%s"
    cur = conn.execute(f"SELECT * FROM shift_handovers WHERE facility_code = {ph} ORDER BY created_at DESC LIMIT {lim_ph}", (facility_code, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── ICD-10 Functions ──
def seed_icd10_codes():
    """Seed common obstetric ICD-10 codes."""
    codes = [
        ('O10', 'ارتفاع ضغط الدم الموجود مسبقاً', 'Pre-existing hypertension', 'hypertension'),
        ('O11', 'ارتفاع ضغط الدم الموجود مسبقاً مع بروتينية', 'Pre-eclampsia superimposed', 'hypertension'),
        ('O13', 'ارتفاع ضغط الدم الحملي', 'Gestational hypertension', 'hypertension'),
        ('O14', 'تسمم الحمل', 'Pre-eclampsia', 'hypertension'),
        ('O15', 'تسمم الحمل المتشنج', 'Eclampsia', 'hypertension'),
        ('O20', 'نزف في بداية الحمل', 'Haemorrhage in early pregnancy', 'bleeding'),
        ('O21', 'القيء المفرط للحوامل', 'Excessive vomiting in pregnancy', 'other'),
        ('O24', 'السكري أثناء الحمل', 'Diabetes in pregnancy', 'metabolic'),
        ('O24.4', 'سكري الحمل', 'Gestational diabetes', 'metabolic'),
        ('O30', 'الحمل المتعدد', 'Multiple gestation', 'multiple'),
        ('O34', 'رعاية الأم بسبب اختلاف أعضاء الحوض', 'Maternal care for pelvic abnormality', 'obstetric'),
        ('O36', 'رعاية الأم بسبب مشاكل جنينية', 'Maternal care for fetal problems', 'fetal'),
        ('O41', 'اضطرابات السائل الأمنيوسي', 'Amniotic fluid disorders', 'obstetric'),
        ('O42', 'تمزق الأغشية المبكر', 'Premature rupture of membranes', 'obstetric'),
        ('O44', 'المشيمة المنزاحة', 'Placenta praevia', 'bleeding'),
        ('O45', 'الانفصال المبكر للمشيمة', 'Placental abruption', 'bleeding'),
        ('O48', 'الحمل المطول', 'Post-term pregnancy', 'obstetric'),
        ('O60', 'الولادة المبكرة', 'Preterm delivery', 'delivery'),
        ('O68', 'مخاض وولادة معقدة بسبب إجهاد جنيني', 'Labour complicated by fetal stress', 'delivery'),
        ('O70', 'تمزق العجان أثناء الولادة', 'Perineal laceration', 'delivery'),
        ('O71', 'رضح ولادي آخر', 'Other obstetric trauma', 'delivery'),
        ('O72', 'نزف ما بعد الولادة', 'Postpartum haemorrhage', 'bleeding'),
        ('O73', 'احتباس المشيمة', 'Retained placenta', 'delivery'),
        ('O80', 'ولادة طبيعية', 'Normal delivery', 'delivery'),
        ('O82', 'ولادة قيصرية', 'Caesarean delivery', 'delivery'),
        ('O86', 'عدوى النفاس', 'Puerperal infection', 'infection'),
        ('O90', 'مضاعفات النفاس', 'Puerperal complications', 'postpartum'),
        ('P07', 'اضطرابات مرتبطة بقصر الحمل', 'Disorders related to short gestation', 'neonatal'),
        ('P22', 'متلازمة ضيق التنفس عند المولود', 'Respiratory distress of newborn', 'neonatal'),
        ('Z33', 'الحمل', 'Pregnancy', 'encounter'),
        ('Z34', 'رعاية الحمل الطبيعي', 'Normal pregnancy supervision', 'encounter'),
        ('Z35', 'رعاية الحمل عالي الخطورة', 'High-risk pregnancy supervision', 'encounter'),
        ('Z37', 'نتيجة الولادة', 'Outcome of delivery', 'encounter'),
        ('Z39', 'رعاية ما بعد الولادة', 'Postnatal care', 'encounter'),
    ]
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    for code, ar, en, cat in codes:
        try:
            conn.execute(f"INSERT OR IGNORE INTO icd10_codes (code, title_ar, title_en, category) VALUES ({ph},{ph},{ph},{ph})",
                         (code, ar, en, cat))
        except Exception:
            pass
    conn.close()

def search_icd10(query='', category=None):
    conn = get_conn()
    ph = "%s" if USE_POSTGRES else "?"
    sql = "SELECT * FROM icd10_codes WHERE (code LIKE ? OR title_ar LIKE ? OR title_en LIKE ?)"
    args = [f'%{query}%', f'%{query}%', f'%{query}%']
    if category:
        sql += " AND category = ?"
        args.append(category)
    sql += " ORDER BY code LIMIT 30"
    if USE_POSTGRES:
        sql = sql.replace('?', '%s')
    cur = conn.execute(sql, args)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ensure_admin():
    """Create default admin if no users exist."""
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) FROM users")
    count = _val(cur)
    if count == 0:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        conn.execute(
            "INSERT INTO users (username, hashed_password, role, approved) VALUES (?,?,?,?)" if not USE_POSTGRES else
            "INSERT INTO users (username, hashed_password, role, approved) VALUES (%s,%s,%s,%s)",
            ("admin", ctx.hash("admin123"), "admin", 1)
        )
    conn.close()


# ── Follow-ups ──
def add_follow_up(patient_id, follow_up_date, type_="routine", notes=None):
    conn = get_conn()
    if USE_POSTGRES:
        conn.execute("INSERT INTO follow_ups (patient_id, follow_up_date, type, notes) VALUES (%s,%s,%s,%s)",
                     (patient_id, follow_up_date, type_, notes))
    else:
        conn.execute("INSERT INTO follow_ups (patient_id, follow_up_date, type, notes) VALUES (?,?,?,?)",
                     (patient_id, follow_up_date, type_, notes))
    conn.close()

def get_follow_ups(patient_id, status=None):
    conn = get_conn()
    sql = "SELECT * FROM follow_ups WHERE patient_id = ?" if not USE_POSTGRES else "SELECT * FROM follow_ups WHERE patient_id = %s"
    args = [patient_id]
    if status:
        sql += " AND status = ?" if not USE_POSTGRES else " AND status = %s"
        args.append(status)
    sql += " ORDER BY follow_up_date DESC"
    cur = conn.execute(sql, args)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_follow_up(fu_id, data):
    if not data:
        return
    conn = get_conn()
    set_clause = ", ".join([f"{k} = ?" for k in data])
    conn.execute(f"UPDATE follow_ups SET {set_clause} WHERE id = ?", (*data.values(), fu_id))
    conn.close()

def get_pending_follow_ups(limit=10):
    conn = get_conn()
    cur = conn.execute(
        "SELECT fu.*, p.name as patient_name FROM follow_ups fu LEFT JOIN patients p ON fu.patient_id = p.patient_id "
        "WHERE fu.status = 'pending' AND fu.follow_up_date <= date('now','+7 days') ORDER BY fu.follow_up_date LIMIT ?" if not USE_POSTGRES else
        "SELECT fu.*, p.name as patient_name FROM follow_ups fu LEFT JOIN patients p ON fu.patient_id = p.patient_id "
        "WHERE fu.status = 'pending' AND fu.follow_up_date <= CURRENT_DATE + INTERVAL '7 days' ORDER BY fu.follow_up_date LIMIT %s",
        (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Pregnancy Timeline ──
def get_pregnancy_timeline(patient_id):
    conn = get_conn()
    events = []
    # Antenatal visits
    for r in conn.execute("SELECT 'visit' as ev_type, visit_date as ev_date, 'Antenatal Visit #'||visit_number as title, notes as description FROM antenatal_visits WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'visit' as ev_type, visit_date as ev_date, 'Antenatal Visit #'||visit_number as title, notes as description FROM antenatal_visits WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    # Risk assessments
    for r in conn.execute("SELECT 'assessment' as ev_type, created_at as ev_date, assessment_type||' assessment' as title, risk_level||' risk - score '||printf('%.2f',risk_score) as description FROM risk_assessments WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'assessment' as ev_type, created_at as ev_date, assessment_type||' assessment' as title, risk_level||' risk - score '||printf('%.2f',risk_score) as description FROM risk_assessments WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    # Ultrasound
    for r in conn.execute("SELECT 'ultrasound' as ev_type, exam_date as ev_date, 'Ultrasound' as title, notes as description FROM ultrasound_exams WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'ultrasound' as ev_type, exam_date as ev_date, 'Ultrasound' as title, notes as description FROM ultrasound_exams WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    # Lab investigations
    for r in conn.execute("SELECT 'lab' as ev_type, test_date as ev_date, test_type as title, result||' ('||normal_range||')' as description FROM investigations WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'lab' as ev_type, test_date as ev_date, test_type as title, result||' ('||normal_range||')' as description FROM investigations WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    # Deliveries
    for r in conn.execute("SELECT 'delivery' as ev_type, delivery_date as ev_date, 'Delivery - '||mode_of_delivery as title, complications as description FROM deliveries WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'delivery' as ev_type, delivery_date as ev_date, 'Delivery - '||mode_of_delivery as title, complications as description FROM deliveries WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    # Follow-ups
    for r in conn.execute("SELECT 'follow_up' as ev_type, follow_up_date as ev_date, type||' follow-up' as title, notes as description FROM follow_ups WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'follow_up' as ev_type, follow_up_date as ev_date, type||' follow-up' as title, notes as description FROM follow_ups WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    # Admissions
    for r in conn.execute("SELECT 'admission' as ev_type, admission_date as ev_date, 'Admission' as title, admission_reason as description FROM admissions WHERE patient_id = ?" if not USE_POSTGRES else
                          "SELECT 'admission' as ev_type, admission_date as ev_date, 'Admission' as title, admission_reason as description FROM admissions WHERE patient_id = %s", (patient_id,)):
        events.append(dict(r))
    conn.close()
    # Sort by date descending (most recent first), put null dates last
    events.sort(key=lambda e: (e.get("ev_date") or "", e.get("ev_type", "")), reverse=True)
    return events
