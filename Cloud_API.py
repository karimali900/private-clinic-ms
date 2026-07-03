import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
import uvicorn

from classification import FetalHealthModel
from Postpartum import PostpartumRecoveryModel
from database import (
    init_db, add_patient, get_patient, get_all_patients, update_patient, delete_patient,
    add_measurement, update_measurement, delete_measurement, get_measurements,
    save_assessment, get_assessments, get_recent_assessments,
    create_user, get_user, approve_user, reject_user, get_pending_users, USE_POSTGRES,
    add_ultrasound_exam, update_ultrasound_exam, delete_ultrasound_exam,
    get_ultrasound_exams, get_ultrasound_exam,
    upsert_maternal_history, get_maternal_history,
    upsert_paternal_history, get_paternal_history,
    add_delivery, get_deliveries,
    add_newborn, get_newborns,
    add_antenatal_visit, get_antenatal_visits,
    add_investigation, update_investigation, get_investigations,
    add_medical_image, get_medical_images, delete_medical_image,
    add_follow_up, get_follow_ups, update_follow_up, get_pending_follow_ups,
    get_pregnancy_timeline, ensure_admin,
    add_facility, get_facility, get_all_facilities, update_facility,
    add_referral, get_referrals, update_referral,
    create_handover, get_handovers,
    seed_icd10_codes, search_icd10,
)

JWT_SECRET = os.getenv("JWT_SECRET", "maternal-health-secret-key-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 24

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_admin()
    yield


app = FastAPI(title="Private Clinic — Obstetrics Management", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
os.makedirs("data", exist_ok=True)
os.makedirs("data/images", exist_ok=True)
app.mount("/data", StaticFiles(directory="data"), name="data")

fetal_model = FetalHealthModel()
postpartum_model = PostpartumRecoveryModel()

ws_connections: List[WebSocket] = []


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_token(username: str, role: str = "clinician", facility_code: str = "DEFAULT") -> str:
    payload = {"sub": username, "role": role, "facility_code": facility_code, "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def broadcast_assessment(data: dict):
    dead = []
    for ws in ws_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_connections.remove(ws)


# ── Pydantic models ──

class FacilityCreate(BaseModel):
    code: str
    name: str
    type: Optional[str] = 'clinic'
    address: Optional[str] = None
    phone: Optional[str] = None
    governorate: Optional[str] = None

class ReferralCreate(BaseModel):
    patient_id: str
    from_facility: str
    to_facility: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    urgency: str = 'routine'

class HandoverCreate(BaseModel):
    facility_code: str
    shift_date: str
    shift_type: str
    handed_over_by: str
    active_patients: int = 0
    high_risk_patients: int = 0
    deliveries_count: int = 0
    notes: Optional[str] = None

class ICD10Search(BaseModel):
    query: str = ''
    category: Optional[str] = None

class LoginWithFacility(BaseModel):
    username: str
    password: str
    facility_code: str = ''


class PatientRegistration(BaseModel):
    patient_id: str
    name: str
    age: int
    bmi_pre_pregnancy: float
    expected_due_date: str
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    case_type: Optional[str] = 'follow-up'
    facility_code: Optional[str] = 'DEFAULT'

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    bmi_pre_pregnancy: Optional[float] = None
    expected_due_date: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    photo_path: Optional[str] = None
    case_type: Optional[str] = None
    facility_code: str = 'DEFAULT' 
    facility_code: Optional[str] = None

class ClinicalMeasurement(BaseModel):
    patient_id: str
    gestational_age: int = 0
    blood_pressure_sys: int = 0
    blood_pressure_dia: int = 0
    glucose_level: float = 0
    heart_rate: int = 0
    fetal_heart_rate: int = 0
    fetal_movement_count: int = 0
    temperature: Optional[float] = 37.0

    def to_dict(self):
        return self.model_dump()

class RiskRequest(BaseModel):
    patient_id: str
    clinical_data: dict

class UltrasoundExam(BaseModel):
    patient_id: str
    gestational_age: Optional[int] = None
    biparietal_diameter: Optional[float] = None
    femur_length: Optional[float] = None
    abdominal_circumference: Optional[float] = None
    head_circumference: Optional[float] = None
    estimated_weight: Optional[float] = None
    amniotic_fluid_index: Optional[float] = None
    placenta_position: Optional[str] = None
    presentation: Optional[str] = None
    heart_rate: Optional[int] = None
    crl: Optional[float] = None
    findings: Optional[dict] = None
    notes: Optional[str] = None

class MaternalHistoryData(BaseModel):
    patient_id: str
    gravida: Optional[int] = 0
    para: Optional[int] = 0
    previous_cesarean: Optional[bool] = False
    previous_miscarriages: Optional[int] = 0
    chronic_conditions: Optional[str] = None
    allergies: Optional[str] = None
    medications: Optional[str] = None
    family_history: Optional[str] = None
    blood_type: Optional[str] = None
    rh_factor: Optional[str] = None
    smoking: Optional[bool] = False
    alcohol: Optional[bool] = False

class PaternalHistoryData(BaseModel):
    patient_id: str
    age: Optional[int] = None
    blood_type: Optional[str] = None
    rh_factor: Optional[str] = None
    genetic_disorders: Optional[str] = None
    chronic_conditions: Optional[str] = None
    medications: Optional[str] = None
    smoking: Optional[bool] = False
    alcohol: Optional[bool] = False
    family_history: Optional[str] = None

class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "clinician"

class UserLogin(BaseModel):
    username: str
    password: str
    facility_code: str = ''

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int


# ── Events ──



# ── Auth endpoints ──
@app.post("/api/auth/register")
async def auth_register(u: UserRegister):
    existing = get_user(u.username)
    if existing:
        raise HTTPException(400, "Username already exists")
    hashed = pwd_ctx.hash(u.password)
    create_user(u.username, hashed, u.role)
    user = get_user(u.username)
    if user.get("approved"):
        token = create_token(u.username, user.get("role", "clinician"))
        return {"status": "success", "token": token, "username": u.username, "role": user.get("role", "clinician"), "approved": True}
    return {"status": "pending", "username": u.username, "approved": False, "message": "Account created. Awaiting admin approval."}

@app.get("/api/auth/me")
async def auth_me(token: dict = Depends(verify_token)):
    user = get_user(token.get("sub"))
    if not user:
        raise HTTPException(404, "User not found")
    return {"username": user["username"], "role": user.get("role", "clinician"), "approved": user.get("approved", True)}

@app.post("/api/auth/login")
async def auth_login(u: UserLogin):
    user = get_user(u.username)
    # Multi-facility: restrict only if user has explicit non-DEFAULT facility
    user_fc = user.get("facility_code") if user else None
    if user_fc and user_fc not in ('DEFAULT', None, '') and u.facility_code != user_fc:
        raise HTTPException(403, "User does not belong to this facility")
    if not user or not pwd_ctx.verify(u.password, user["hashed_password"]):
        raise HTTPException(401, "Invalid credentials")
    if not user.get("approved"):
        raise HTTPException(403, "Account pending approval. Contact administrator.")
    fc = u.facility_code or user.get("facility_code") or 'DEFAULT'
    token = create_token(u.username, user.get("role", "clinician"), fc)
    return {"status": "success", "token": token, "username": u.username, "role": user.get("role", "clinician"), "facility_code": fc}

@app.get("/api/admin/pending-users")
async def pending_users(token: dict = Depends(verify_token)):
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return get_pending_users()

@app.post("/api/admin/approve-user")
async def approve_user_endpoint(body: dict, token: dict = Depends(verify_token)):
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    username = body.get("username")
    if not username:
        raise HTTPException(400, "Username required")
    approve_user(username)
    return {"status": "success", "message": f"User {username} approved"}

@app.post("/api/admin/reject-user")
async def reject_user_endpoint(body: dict, token: dict = Depends(verify_token)):
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    username = body.get("username")
    if not username:
        raise HTTPException(400, "Username required")
    reject_user(username)
    return {"status": "success", "message": f"User {username} rejected and removed"}


# ── Patient endpoints ──
@app.post("/api/patients/register")
async def register_patient(p: PatientRegistration):
    add_patient(
        p.patient_id, p.name, p.age, p.bmi_pre_pregnancy, p.expected_due_date,
        phone=p.phone, email=p.email, date_of_birth=p.date_of_birth,
        address=p.address, emergency_contact_name=p.emergency_contact_name,
        emergency_contact_phone=p.emergency_contact_phone, blood_type=p.blood_type,
        case_type=p.case_type or 'follow-up',
        facility_code=p.facility_code or 'DEFAULT'
    )
    return {"status": "success", "patient_id": p.patient_id, "message": "Registered"}

@app.post("/api/patients/{patient_id}/photo")
async def upload_patient_photo(patient_id: str, file: UploadFile = File(...)):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    os.makedirs("data/photos", exist_ok=True)
    ext = Path(file.filename).suffix or ".jpg"
    path = f"data/photos/{patient_id}{ext}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    update_patient(patient_id, photo_path=path)
    return {"status": "success", "photo_path": path, "size": len(content)}

@app.get("/api/patients")
async def list_patients(page: int = 1, per_page: int = 20, token: dict = Depends(verify_token)):
    fc = token.get("facility_code")
    if fc and fc != 'DEFAULT':
        items, total = get_all_patients(page, per_page, facility_code=fc)
    else:
        items, total = get_all_patients(page, per_page)
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             pages=max(1, (total + per_page - 1) // per_page))

@app.get("/api/patients/{patient_id}")
async def read_patient(patient_id: str):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    return p

@app.put("/api/patients/{patient_id}")
async def update_patient_endpoint(patient_id: str, u: PatientUpdate):
    existing = get_patient(patient_id)
    if not existing:
        raise HTTPException(404, "Patient not found")
    kwargs = u.model_dump(exclude_none=True)
    if not kwargs:
        return {"status": "success", "patient_id": patient_id, "message": "No changes"}
    update_patient(patient_id, **kwargs)
    return {"status": "success", "patient_id": patient_id, "message": "Updated"}

@app.delete("/api/patients/{patient_id}")
async def delete_patient_endpoint(patient_id: str, token: dict = Depends(verify_token)):
    existing = get_patient(patient_id)
    if not existing:
        raise HTTPException(404, "Patient not found")
    fc = token.get("facility_code")
    delete_patient(patient_id, fc if fc and fc != 'DEFAULT' else None)
    return {"status": "success", "patient_id": patient_id, "message": "Deleted"}


# ── Measurement endpoints ──
@app.post("/api/measurements/record")
async def record_measurement(m: ClinicalMeasurement):
    p = get_patient(m.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    add_measurement(m.patient_id, m.to_dict())
    return {"status": "success", "message": "Measurement recorded"}

@app.get("/api/patients/{patient_id}/measurements")
async def list_measurements(patient_id: str, page: int = 1, per_page: int = 20):
    items, total = get_measurements(patient_id, page, per_page)
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             pages=max(1, (total + per_page - 1) // per_page))

@app.put("/api/measurements/{measurement_id}")
async def update_measurement_endpoint(measurement_id: int, data: dict):
    ok = update_measurement(measurement_id, data)
    if not ok:
        raise HTTPException(404, "Measurement not found or no fields to update")
    return {"status": "success", "message": "Measurement updated"}

@app.delete("/api/measurements/{measurement_id}")
async def delete_measurement_endpoint(measurement_id: int):
    delete_measurement(measurement_id)
    return {"status": "success", "message": "Measurement deleted"}


# ── Assessment endpoints ──
@app.post("/api/assess/fetal")
async def assess_fetal(req: RiskRequest, token: dict = Depends(verify_token)):
    try:
        p = get_patient(req.patient_id)
        if not p:
            raise HTTPException(404, "Patient not found")
        assessment = fetal_model.predict_risk(req.clinical_data)
        assessment["recommendations"] = fetal_model.generate_recommendations(assessment)
        save_assessment(req.patient_id, "fetal", assessment["risk_level"],
                        assessment["risk_score"], assessment)
        if assessment["risk_level"] in ("high", "medium"):
            days = 3 if assessment["risk_level"] == "high" else 7
            fu_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            add_follow_up(req.patient_id, fu_date, "high_risk" if assessment["risk_level"]=="high" else "routine",
                          f"Auto-scheduled after {assessment['risk_level']} fetal assessment")
        result = {"status": "success", "assessment": assessment,
                  "timestamp": datetime.now().isoformat()}
        await broadcast_assessment({"type": "new_assessment", "data": {
            "patient_id": req.patient_id, "assessment_type": "fetal",
            "risk_level": assessment["risk_level"], "risk_score": assessment["risk_score"],
            "method": assessment.get("method", "rule_based"),
        }})
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/api/assess/postpartum")
async def assess_postpartum(req: RiskRequest, token: dict = Depends(verify_token)):
    try:
        p = get_patient(req.patient_id)
        if not p:
            raise HTTPException(404, "Patient not found")
        assessment = postpartum_model.predict_risk(req.clinical_data)
        assessment["risk_factors"] = postpartum_model.get_risk_factors(req.clinical_data)
        assessment["recommendations"] = postpartum_model.generate_recommendations(req.clinical_data)
        save_assessment(req.patient_id, "postpartum", assessment["risk_level"],
                        assessment["risk_score"], assessment)
        if assessment["risk_level"] in ("high", "medium"):
            days = 3 if assessment["risk_level"] == "high" else 7
            fu_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            add_follow_up(req.patient_id, fu_date, "high_risk" if assessment["risk_level"]=="high" else "routine",
                          f"Auto-scheduled after {assessment['risk_level']} postpartum assessment")
        result = {"status": "success", "assessment": assessment,
                  "timestamp": datetime.now().isoformat()}
        await broadcast_assessment({"type": "new_assessment", "data": {
            "patient_id": req.patient_id, "assessment_type": "postpartum",
            "risk_level": assessment["risk_level"], "risk_score": assessment["risk_score"],
        }})
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/api/patients/{patient_id}/assessments")
async def patient_assessments(patient_id: str, page: int = 1, per_page: int = 20):
    items, total = get_assessments(patient_id, page, per_page)
    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page,
                             pages=max(1, (total + per_page - 1) // per_page))

@app.get("/api/assessments/recent")
async def recent_assessments(limit: int = 10):
    return get_recent_assessments(limit)


# ── Patient history (combined) ──
@app.get("/api/patients/{patient_id}/history")
async def patient_history(patient_id: str, page: int = 1, per_page: int = 20):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    measurements, m_total = get_measurements(patient_id, page, per_page)
    assessments, a_total = get_assessments(patient_id, page, per_page)
    return {"patient_id": patient_id, "patient": p,
            "measurements": measurements, "measurements_total": m_total,
            "assessments": assessments, "assessments_total": a_total,
            "page": page, "per_page": per_page}


# ── Comprehensive report ──
@app.get("/api/patients/{patient_id}/report")
async def comprehensive_report(patient_id: str):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    measurements, _ = get_measurements(patient_id, 1, 100)
    assessments, _ = get_assessments(patient_id, 1, 100)
    ultrasound = get_ultrasound_exams(patient_id)
    maternal = get_maternal_history(patient_id)
    paternal = get_paternal_history(patient_id)
    newborns = get_newborns(patient_id)
    deliveries = get_deliveries(patient_id)
    anc = get_antenatal_visits(patient_id)
    labs = get_investigations(patient_id)
    return {
        "patient": p,
        "measurements": measurements,
        "assessments": assessments,
        "ultrasound_exams": ultrasound,
        "maternal_history": maternal,
        "paternal_history": paternal,
        "deliveries": deliveries,
        "newborns": newborns,
        "antenatal_visits": anc,
        "investigations": labs,
        "generated_at": datetime.now().isoformat(),
    }
@app.post("/api/ultrasound/upload")
async def upload_ultrasound(patient_id: str, file: UploadFile = File(...)):
    os.makedirs("data/ultrasound", exist_ok=True)
    ext = Path(file.filename).suffix or ".png"
    path = f"data/ultrasound/{patient_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"status": "success", "file_path": path, "size": len(content),
            "timestamp": datetime.now().isoformat()}

@app.post("/api/ultrasound/exam")
async def record_ultrasound_exam(e: UltrasoundExam):
    p = get_patient(e.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    data = e.model_dump(exclude={"patient_id"}, exclude_none=True)
    if data.get("findings"):
        data["findings"] = json.dumps(data["findings"])
    add_ultrasound_exam(e.patient_id, data)
    return {"status": "success", "message": "Ultrasound exam recorded"}

@app.get("/api/patients/{patient_id}/ultrasound")
async def list_ultrasound_exams(patient_id: str):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    return get_ultrasound_exams(patient_id)

@app.get("/api/ultrasound/{exam_id}")
async def get_ultrasound_exam_endpoint(exam_id: int):
    exam = get_ultrasound_exam(exam_id)
    if not exam:
        raise HTTPException(404, "Ultrasound exam not found")
    return exam

@app.put("/api/ultrasound/{exam_id}")
async def update_ultrasound_exam_endpoint(exam_id: int, data: dict):
    existing = get_ultrasound_exam(exam_id)
    if not existing:
        raise HTTPException(404, "Ultrasound exam not found")
    if data.get("findings") and isinstance(data["findings"], dict):
        data["findings"] = json.dumps(data["findings"])
    update_ultrasound_exam(exam_id, data)
    return {"status": "success", "message": "Ultrasound exam updated"}

@app.delete("/api/ultrasound/{exam_id}")
async def delete_ultrasound_exam_endpoint(exam_id: int):
    existing = get_ultrasound_exam(exam_id)
    if not existing:
        raise HTTPException(404, "Ultrasound exam not found")
    delete_ultrasound_exam(exam_id)
    return {"status": "success", "message": "Ultrasound exam deleted"}


# ── Maternal / Paternal History ──
@app.post("/api/history/maternal")
async def save_maternal_history(h: MaternalHistoryData):
    p = get_patient(h.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    data = h.model_dump(exclude={"patient_id"}, exclude_none=True)
    upsert_maternal_history(h.patient_id, data)
    return {"status": "success", "message": "Maternal history saved"}

@app.get("/api/patients/{patient_id}/history/maternal")
async def get_maternal_history_endpoint(patient_id: str):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    h = get_maternal_history(patient_id)
    if not h:
        return {"status": "empty", "message": "No maternal history recorded"}
    return h

@app.post("/api/history/paternal")
async def save_paternal_history(h: PaternalHistoryData):
    p = get_patient(h.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    data = h.model_dump(exclude={"patient_id"}, exclude_none=True)
    upsert_paternal_history(h.patient_id, data)
    return {"status": "success", "message": "Paternal history saved"}

@app.get("/api/patients/{patient_id}/history/paternal")
async def get_paternal_history_endpoint(patient_id: str):
    p = get_patient(patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    h = get_paternal_history(patient_id)
    if not h:
        return {"status": "empty", "message": "No paternal history recorded"}
    return h


# ── Ward / Admission endpoints ──


# ── Delivery & Newborn endpoints ──
@app.post("/api/deliveries/record")
async def record_delivery(body: dict):
    pid = body.get("patient_id")
    if not pid or not get_patient(pid):
        raise HTTPException(404, "Patient not found")
    data = {k: v for k, v in body.items() if k != "patient_id" and v is not None}
    add_delivery(pid, data)
    return {"status": "success", "message": "Delivery recorded"}

@app.get("/api/patients/{patient_id}/deliveries")
async def patient_deliveries(patient_id: str):
    return get_deliveries(patient_id)

@app.post("/api/newborns/record")
async def record_newborn(body: dict):
    pid = body.get("patient_id")
    if not pid or not get_patient(pid):
        raise HTTPException(404, "Patient not found")
    data = {k: v for k, v in body.items() if k != "patient_id" and v is not None}
    add_newborn(pid, data)
    return {"status": "success", "message": "Newborn recorded"}

@app.get("/api/patients/{patient_id}/newborns")
async def patient_newborns(patient_id: str):
    return get_newborns(patient_id)


# ── Medical Imaging endpoints ──
@app.post("/api/imaging/upload")
async def upload_image(patient_id: str = Form(...), image_type: str = Form(""), description: str = Form(""), notes: str = Form(""), file: UploadFile = File(...)):
    if not patient_id or not get_patient(patient_id):
        raise HTTPException(404, "Patient not found")
    ext = Path(file.filename).suffix or ".png"
    filename = f"{patient_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}{ext}"
    path = f"data/images/{filename}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    add_medical_image(patient_id, image_type, f"/data/images/{filename}", description or None, notes or None)
    return {"status": "success", "file_path": f"/data/images/{filename}"}

@app.get("/api/patients/{patient_id}/imaging")
async def patient_images(patient_id: str):
    return get_medical_images(patient_id)

@app.delete("/api/imaging/{image_id}")
async def delete_image(image_id: int):
    delete_medical_image(image_id)

@app.post("/api/imaging/analyze")
async def analyze_medical_image(image_type: str = Form(""), file: UploadFile = File(...)):
    try:
        content = await file.read()
        # Try AI vision API if available (HuggingFace free tier)
        hf_token = os.environ.get('HF_TOKEN', '')
        if hf_token:
            try:
                import httpx
                resp = httpx.post(
                    "https://api-inference.huggingface.co/models/nlpconnect/vit-gpt2-image-captioning",
                    headers={"Authorization": f"Bearer {hf_token}"},
                    content=content, timeout=30
                )
                if resp.status_code == 200:
                    caption = resp.json()[0].get("generated_text", "")
                    if caption:
                        return _parse_ai_result(image_type, caption)
            except Exception:
                pass
        # Fallback: mock AI result based on image type
        return _mock_ai_result(image_type)
    except Exception as e:
        return {"error": str(e)}

def _parse_ai_result(img_type, caption):
    base = {"description": caption}
    if img_type in ("CT Scan", "MRI", "X-Ray"):
        base["findings"] = caption
        base["impression"] = "AI-generated impression — review by radiologist recommended."
    elif img_type == "Ultrasound":
        base["findings"] = caption
        base["measurements"] = "AI estimated — confirm manually."
    elif img_type == "Lab Photo":
        base["test_name"] = "Auto-detected"
        base["result"] = caption
    return base

def _mock_ai_result(img_type):
    mocks = {
        "CT Scan": {"findings": "No acute intracranial abnormality detected.", "impression": "Normal CT brain — no hemorrhage, mass effect, or midline shift.", "description": "CT Scan: No acute intracranial abnormality detected."},
        "MRI": {"findings": "Unremarkable MRI study.", "impression": "Normal MRI — no significant pathology identified.", "description": "MRI: Unremarkable study."},
        "X-Ray": {"findings": "Clear lung fields bilaterally. No consolidation, effusion, or pneumothorax.", "impression": "Normal chest X-ray.", "description": "X-Ray: Clear lung fields."},
        "Ultrasound": {"findings": "Single intrauterine pregnancy. Fetal heart rate 145 bpm. Normal amniotic fluid.", "measurements": "CRL 62mm, BPD 33mm, FL 22mm", "description": "Ultrasound: Single IUP, FHR 145 bpm."},
        "Lab Photo": {"test_name": "CBC", "result": "Within normal limits", "description": "Lab: CBC within normal limits."},
    }
    return mocks.get(img_type, {"description": "Image received for review.", "details": "Manual review pending."})
    return {"status": "success"}


# ── Follow-ups & Timeline endpoints ──
@app.post("/api/follow-ups")
async def create_follow_up(body: dict):
    pid = body.get("patient_id")
    if not pid or not get_patient(pid):
        raise HTTPException(404, "Patient not found")
    date = body.get("follow_up_date")
    if not date:
        raise HTTPException(400, "follow_up_date required")
    add_follow_up(pid, date, body.get("type", "routine"), body.get("notes"))
    return {"status": "success", "message": "Follow-up scheduled"}

@app.get("/api/patients/{patient_id}/follow-ups")
async def list_follow_ups(patient_id: str, status: str = None):
    return get_follow_ups(patient_id, status)

@app.put("/api/follow-ups/{fu_id}")
async def edit_follow_up(fu_id: int, body: dict):
    data = {k: v for k, v in body.items() if v is not None}
    if data:
        update_follow_up(fu_id, data)
    return {"status": "success"}

@app.get("/api/patients/{patient_id}/timeline")
async def pregnancy_timeline(patient_id: str):
    return get_pregnancy_timeline(patient_id)

@app.get("/api/follow-ups/pending")
async def pending_follow_ups(limit: int = 10):
    return get_pending_follow_ups(limit)


# ── Antenatal Care endpoints ──
@app.post("/api/antenatal/visit")
async def record_antenatal_visit(body: dict):
    pid = body.get("patient_id")
    if not pid or not get_patient(pid):
        raise HTTPException(404, "Patient not found")
    data = {k: v for k, v in body.items() if k != "patient_id" and v is not None}
    add_antenatal_visit(pid, data)
    return {"status": "success", "message": "Antenatal visit recorded"}

@app.get("/api/patients/{patient_id}/antenatal")
async def patient_antenatal_visits(patient_id: str):
    return get_antenatal_visits(patient_id)


# ── Investigations endpoints ──
@app.post("/api/investigations/add")
async def add_investigation_endpoint(body: dict):
    pid = body.get("patient_id")
    if not pid or not get_patient(pid):
        raise HTTPException(404, "Patient not found")
    data = {k: v for k, v in body.items() if k != "patient_id" and v is not None}
    inv_id = add_investigation(pid, data)
    return {"status": "success", "message": "Investigation recorded", "id": inv_id}

@app.post("/api/investigations/{inv_id}/file")
async def upload_investigation_file(inv_id: int, file: UploadFile = File(...)):
    os.makedirs("data/investigations", exist_ok=True)
    ext = Path(file.filename).suffix or ".jpg"
    path = f"data/investigations/{inv_id}{ext}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    update_investigation(inv_id, {"file_path": "/data/investigations/" + str(inv_id) + ext})
    return {"status": "success", "file_path": path}

@app.get("/api/patients/{patient_id}/investigations")
async def patient_investigations(patient_id: str):
    return get_investigations(patient_id)


# ── WebSocket ──
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.append(websocket)
    try:
        recent = get_recent_assessments(5)
        if recent:
            await websocket.send_json({"type": "recent", "data": recent})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_connections.remove(websocket)


# ── Health ──
@app.get("/health")
async def health():
    return {"status": "healthy", "models_loaded": {"fetal": True, "postpartum": True},
            "database": "postgresql" if USE_POSTGRES else "sqlite3"}


# ── Root ──
@app.get("/")
async def root():
    return {"name": "Private Clinic — Obstetrics Management",
            "version": "2.0.0", "status": "operational",
            "timestamp": datetime.now().isoformat()}


# ── Dashboard ──
DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private Clinic — Obstetrics Management</title>
<script>window.onerror=function(m){var e=document.getElementById('jsError');if(e){e.textContent='⚠ Application error: '+(m||'unknown')+'. Please refresh or contact support.';e.style.display='block'}};</script>
<script>var _fd=__FACILITY_DATA__;window.__FD__=_fd;</script>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
<noscript><div style="background:#ed4245;color:#fff;text-align:center;padding:2rem;font-size:1.2rem">⚠ JavaScript is required. Please enable it in your browser settings.</div></noscript>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a16;color:#e0e0e0;min-height:100vh}
.login-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;z-index:999}
.login-box{background:#16162a;border-radius:16px;padding:2.5rem;width:400px;max-width:90vw;border:1px solid #2a2a4a;box-shadow:0 8px 32px rgba(0,0,0,.5)}
.login-box .logo{text-align:center;margin-bottom:1rem;font-size:2rem}
.login-box h2{color:#7c6ff0;margin-bottom:.3rem;text-align:center;font-size:1.2rem}
.login-box .tagline{color:#555;text-align:center;font-size:.75rem;margin-bottom:1.5rem}
.login-box .fields label{display:block;font-size:.8rem;color:#888;margin:.8rem 0 .3rem}
.login-box .fields input{width:100%;padding:.6rem;border-radius:8px;border:1px solid #333;background:#0f0f1a;color:#e0e0e0;font-size:.9rem}
.login-box .row{margin-top:1.2rem;display:flex;gap:.8rem}
.login-box .btn{flex:1;padding:.7rem;border-radius:8px;border:none;font-size:.85rem;cursor:pointer;font-weight:700}
.login-box .error{color:#ed4245;font-size:.8rem;margin-top:.5rem;text-align:center;display:none}
.layout{display:flex;min-height:100vh}
.sidebar{width:220px;background:#12122a;padding:1.5rem 0;border-right:1px solid #1e1e3a;flex-shrink:0;position:sticky;top:0;height:100vh;overflow-y:auto}
.sidebar h2{color:#7c6ff0;font-size:1rem;padding:0 1.2rem 1.2rem;border-bottom:1px solid #1e1e3a}
.sidebar .nav-item{padding:.8rem 1.2rem;color:#999;cursor:pointer;font-size:.85rem;display:flex;align-items:center;gap:.6rem;transition:.2s}
.sidebar .nav-item:hover,.sidebar .nav-item.active{background:#1a1a3a;color:#e0e0e0}
.sidebar .nav-item .ico{width:18px;text-align:center}
.sidebar .user-info{padding:1rem 1.2rem;border-top:1px solid #1e1e3a;margin-top:auto;font-size:.75rem;color:#666}
.main{flex:1;padding:2rem;position:relative;background:radial-gradient(ellipse at 80% 90%,rgba(124,111,240,0.04) 0,transparent 60%)}
.back-btn{display:none;background:none;border:none;color:#7c6ff0;font-size:1.2rem;cursor:pointer;padding:.2rem .5rem;border-radius:6px;margin-bottom:.5rem}.back-btn:hover{background:#1a1a3a}.back-btn.show{display:inline-block}
.main::before{content:'';position:fixed;bottom:0;right:0;width:400px;height:420px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 320'%3E%3Ccircle cx='120' cy='38' r='24' fill='%237c6ff0' opacity='0.045'/%3E%3Cpath d='M96 62 c0 0-8 4-12 14 c-3 8-2 14-2 14 c0 0-18 22-20 52 c-2 32 10 66 26 84 c-4 10-8 24-10 36 c0 0 4 14 16 14 l10 0 c0 0-2 10 6 18 c6 6 20 6 26 0 c8-8 6-18 6-18 l10 0 c12 0 16-14 16-14 c-2-12-6-26-10-36 c16-18 28-52 26-84 c-2-30-20-52-20-52 c0 0 1-6-2-14 c-4-10-12-14-12-14z' fill='%237c6ff0' opacity='0.045'/%3E%3C/svg%3E") no-repeat bottom right;background-size:contain;pointer-events:none;z-index:0}
.main h1{color:#7c6ff0;font-size:1.4rem;margin-bottom:.5rem}
.main .sub{color:#555;margin-bottom:1.5rem;font-size:.85rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.2rem;margin-bottom:1.5rem}
.card{background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a}
.card h3{color:#7c6ff0;font-size:.9rem;margin-bottom:.8rem}
.fields label{display:block;font-size:.75rem;color:#888;margin:.5rem 0 .2rem}
.fields input,.fields select{width:100%;padding:.5rem;border-radius:6px;border:1px solid #333;background:#0f0f1a;color:#e0e0e0;font-size:.8rem}
.fields select{appearance:auto;cursor:pointer}
.btn{padding:.55rem 1.1rem;border-radius:6px;border:none;font-size:.8rem;cursor:pointer;font-weight:700}
.btn-primary{background:#7c6ff0;color:#fff}
.btn-primary:hover{background:#6b5fe0}
.btn-success{background:#3ba55c;color:#fff}
.btn-success:hover{background:#2d8a49}
.btn-danger{background:#ed4245;color:#fff}
.btn-danger:hover{background:#d83639}
.btn-outline{background:transparent;border:1px solid #333;color:#999}
.btn-outline:hover{background:#1a1a3a;color:#e0e0e0}
.btn-xs{padding:.3rem .6rem;font-size:.7rem}
.row{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;margin-top:.6rem}
.badge{padding:.2rem .7rem;border-radius:20px;font-size:.7rem;font-weight:700;display:inline-block}
.badge-high{background:#ed4245;color:#fff}
.badge-medium{background:#faa61a;color:#000}
.badge-low{background:#3ba55c;color:#fff}
.badge-default{background:#333;color:#999}
table{width:100%;border-collapse:collapse;font-size:.78rem}
th{color:#888;text-align:left;padding:.5rem .4rem;border-bottom:1px solid #333;font-weight:600}
td{padding:.45rem .4rem;border-bottom:1px solid #1e1e3a}
tr:hover td{background:#1a1a3a}
.chart-wrap{height:200px;margin-top:.3rem}
.pagination{display:flex;gap:.4rem;align-items:center;margin-top:.8rem;font-size:.75rem;flex-wrap:wrap}
.pagination .page-btn{padding:.3rem .6rem;border-radius:4px;border:1px solid #333;background:transparent;color:#999;cursor:pointer;font-size:.7rem}
.pagination .page-btn:hover{background:#1a1a3a;color:#e0e0e0}
.pagination .page-btn.active{background:#7c6ff0;border-color:#7c6ff0;color:#fff}
.pagination span{color:#666;font-size:.7rem}
#result{background:#1a1a30;border-radius:8px;padding:1.2rem;margin-top:1rem;border:1px solid #2a2a4a;border-left:4px solid transparent;display:none;font-size:.85rem;color:#f0f0f0}
#result.show{display:block}
#result.show.badge-low{border-left-color:#3ba55c}
#result.show.badge-medium{border-left-color:#faa61a}
#result.show.badge-high{border-left-color:#ed4245}
#result h3{color:#7c6ff0;font-size:.95rem;margin:0}
#result b{color:#fff}
#result ul{padding-left:1.2rem;margin:.4rem 0}
#result li{color:#eee;margin:.2rem 0;line-height:1.4}
.recent-list{max-height:300px;overflow-y:auto}
.recent-item{padding:.4rem 0;border-bottom:1px solid #1e1e3a;font-size:.78rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.tab-bar{display:flex;gap:.2rem;margin-bottom:.6rem}
.tab-bar .tab{padding:.35rem .8rem;border-radius:6px 6px 0 0;font-size:.75rem;cursor:pointer;background:#0f0f1a;color:#666;border:1px solid transparent;border-bottom:1px solid #333}
.tab-bar .tab.active{background:#16162a;border-color:#2a2a4a;border-bottom-color:#16162a;color:#e0e0e0}
.pw-wrap{position:relative;display:flex;align-items:center}
.pw-wrap input{flex:1;padding-right:35px}
.pw-wrap .eye-btn{position:absolute;right:8px;background:none;border:none;color:#888;cursor:pointer;font-size:1rem;padding:2px;line-height:1}
.pw-wrap .eye-btn:hover{color:#ccc}
.lang-bar{display:flex;gap:4px;padding:.6rem 1.2rem;border-top:1px solid #1e1e3a}
.lang-bar .lang-btn{padding:2px 10px;border-radius:4px;border:1px solid #333;background:transparent;color:#888;cursor:pointer;font-size:.7rem;font-weight:600}
.lang-bar .lang-btn.active{background:#7c6ff0;border-color:#7c6ff0;color:#fff}
[dir=rtl]{direction:rtl;text-align:right}
[dir=rtl] .sidebar .nav-item{flex-direction:row-reverse}
[dir=rtl] .login-box{direction:rtl}
[dir=rtl] .pw-wrap .eye-btn{right:auto;left:8px}
[dir=rtl] .pw-wrap input{padding-right:8px;padding-left:35px}
@keyframes pulse{0%{opacity:.4}50%{opacity:1}100%{opacity:.4}}
.loading{animation:pulse 1.2s infinite;color:#555}
@media(max-width:768px){.sidebar{width:56px}.sidebar h2,.sidebar .nav-item span,.sidebar .user-info{display:none}.main{padding:1rem}}
</style>
</head>
<body>
<div class="login-overlay" id="loginOverlay">
  <div class="login-box">
    <div class="logo">🏥</div>
    <img id="loginLogo" src="" style="max-width:120px;max-height:120px;margin:0 auto .5rem;display:none;border-radius:8px">
    <h2 id="lgnTitle">Private Clinic — Obstetrics Management</h2>
    <p class="tagline" id="lgnTagline">Maternity Care · Antenatal Visits · Follow-ups</p>
    <div class="fields">
      <label id="lblUser">Username</label><input id="loginUser" value="admin" autocomplete="username">
      <label id="lblPass">Password</label>
      <div class="pw-wrap"><input id="loginPass" type="password" value="admin123" autocomplete="current-password"><button class="eye-btn" onclick="togglePW('loginPass',this)" type="button">👁</button></div>
      <label>Facility Code / كود المنشأة</label>
      <div style="display:flex;gap:.5rem">
        <input id="loginFacility" type="text" class="form-input" placeholder="e.g. ALEX01" style="flex:1;padding:.6rem;border-radius:8px;border:1px solid #333;background:#0f0f1a;color:#e0e0e0;font-size:.9rem">
        <button type="button" class="btn btn-outline" onclick="document.getElementById('facilityPicker').style.display='block';loadFacilityList()" style="padding:.4rem .8rem;font-size:.75rem">🔍</button>
      </div>
    </div>
    <div class="error" id="loginError">Invalid credentials</div>
    <div id="jsError" style="display:none;background:#ed4245;color:#fff;padding:.5rem;border-radius:6px;font-size:.75rem;margin-top:.5rem;text-align:center"></div>
    <div class="row">
      <button class="btn btn-primary" id="btnSignin" onclick="doLogin()">Sign In</button>
      <button class="btn btn-outline" id="btnRegister" onclick="doRegister()">Register</button>
    </div>
    <div class="lang-bar" style="justify-content:center;margin-top:.8rem;border-top:none;padding:.5rem 0 0">
      <button class="lang-btn active" onclick="setLang('en')" id="langEn">EN</button>
      <button class="lang-btn" onclick="setLang('ar')" id="langAr">عربي</button>
    </div>
    <div style="text-align:center;margin-top:.6rem;padding-top:.6rem;border-top:1px solid #1e1e3a;font-size:.65rem;color:#444;line-height:1.4" id="loginBranding">
      Private Clinic MS · created by Karim Abdelaziz<br>00201029927276
    </div>
  </div>
</div>

<div id="facilityPicker" style="display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#16162a;border-radius:12px;padding:1.5rem;box-shadow:0 8px 32px rgba(0,0,0,.5);z-index:1000;width:400px;max-height:400px;overflow-y:auto;border:1px solid #2a2a4a">
  <h3 style="margin:0 0 1rem;font-size:1rem;color:#7c6ff0">Select Facility / اختر المنشأة</h3>
  <input id="facilitySearch" type="text" placeholder="Search..." class="form-input" style="margin-bottom:.8rem;padding:.5rem;border-radius:6px;border:1px solid #333;background:#0f0f1a;color:#e0e0e0;width:100%" oninput="loadFacilityList()">
  <div id="facilityList" style="color:#e0e0e0"></div>
  <button class="btn btn-outline" style="margin-top:.8rem;width:100%" onclick="document.getElementById('facilityPicker').style.display='none'">Cancel / إلغاء</button>
</div>
<div class="layout" id="appLayout" style="display:none">
  <nav class="sidebar">
    <img id="sidebarLogo" src="" style="max-width:100px;max-height:80px;margin:.5rem auto;display:none;border-radius:6px">
    <h2>🏥 OMS</h2>
    <div class="nav-item active" data-tab="dashboard" onclick="switchTab('dashboard')"><span class="ico">📊</span><span>Dashboard</span></div>
    <div class="nav-item" data-tab="patients" onclick="switchTab('patients')"><span class="ico">👤</span><span>Patients</span></div>
    <div class="nav-item" data-tab="ld" onclick="switchTab('ld')"><span class="ico">👶</span><span>L&amp;D</span></div>
    <div class="nav-item" data-tab="antenatal" onclick="switchTab('antenatal')"><span class="ico">📋</span><span>Antenatal</span></div>
    <div class="nav-item" data-tab="assess" onclick="switchTab('assess')"><span class="ico">🔬</span><span>Assess</span></div>
    <div class="nav-item" data-tab="ultrasound" onclick="switchTab('ultrasound')"><span class="ico">🫀</span><span>Ultrasound</span></div>
    <div class="nav-item" data-tab="imaging" onclick="switchTab('imaging')"><span class="ico">🔬</span><span>Imaging</span></div>
    <div class="nav-item" data-tab="followup" onclick="switchTab('followup')"><span class="ico">📅</span><span>Follow-up</span></div>
    <div class="nav-item" data-tab="investigations" onclick="switchTab('investigations')"><span class="ico">🧪</span><span>Lab Results</span></div>
    <div class="nav-item" data-tab="family" onclick="switchTab('family')"><span class="ico">👪</span><span>Family</span></div>
    <div class="nav-item" data-tab="history" onclick="switchTab('history')"><span class="ico">📜</span><span>History</span></div>
    <div class="nav-item" data-tab="realtime" onclick="switchTab('realtime')"><span class="ico">📡</span><span>Monitor</span></div>
    <div class="nav-item" data-tab="report" onclick="switchTab('report')"><span class="ico">📄</span><span>Report</span></div>
    <div class="nav-item" data-tab="admin" onclick="switchTab('admin')" id="adminNav" style="display:none"><span class="ico">⚙</span><span>Admin</span></div>
    <div class="lang-bar">
      <button class="lang-btn active" onclick="setLang('en')" id="langEnS">EN</button>
      <button class="lang-btn" onclick="setLang('ar')" id="langArS">عربي</button>
    </div>
    <div class="user-info"><span id="userDisplay">admin</span><br><span style="cursor:pointer;color:#7c6ff0" onclick="doLogout()">Sign out</span></div>
    <div style="padding:.6rem 1.2rem;font-size:.6rem;color:#333;border-top:1px solid #1e1e3a;text-align:center;line-height:1.3" id="sidebarBranding">
      Private Clinic MS · created by Karim Abdelaziz<br>00201029927276
    </div>
  </nav>

  <div class="main">
    <button class="back-btn" id="backBtn" onclick="goBack()" title="Go back">← Back</button>
    <div id="tab-dashboard">
      <h1 id="dashTitle">🏥 Private Clinic — Obstetrics Management</h1>
      <p class="sub">Patient overview · Antenatal care · Follow-ups</p>
      <div class="grid">
        <div class="card"><h3>Total Patients</h3><div id="totalPatients" style="font-size:2rem;color:#7c6ff0;font-weight:700">--</div></div>
        <div class="card"><h3>Follow-ups This Week</h3><div id="dashFollowUpsCount" style="font-size:2rem;color:#3ba55c;font-weight:700">--</div></div>
        <div class="card"><h3>High Risk</h3><div id="highRiskCount" style="font-size:2rem;color:#ed4245;font-weight:700">--</div></div>
      </div>
      <div class="grid">
        <div class="card"><h3>Risk Distribution</h3><div class="chart-wrap"><canvas id="overviewChart"></canvas></div></div>
        <div class="card"><h3>Upcoming Follow-ups (7 days)</h3><div id="dashFollowUps" style="font-size:.78rem;color:#999;max-height:150px;overflow-y:auto">Loading...</div></div>
      </div>
      <div class="card"><h3>Recent Assessments</h3><div id="recentList" class="recent-list"><i class="loading">Loading...</i></div></div>

      <div class="card" style="margin-top:1.2rem">
        <h3>BMI Calculator</h3>
        <div class="fields">
          <label>Height (cm)</label><input id="bmiHeight" value="165" type="number" step="0.1">
          <label>Weight (kg)</label><input id="bmiWeight" value="70" type="number" step="0.1">
        </div>
        <div class="row">
          <button class="btn btn-primary btn-xs" onclick="calcBMI()">Calculate</button>
          <span id="bmiResult" style="font-size:1.1rem;font-weight:700;color:#7c6ff0"></span>
        </div>
        <div id="bmiCategory" style="margin-top:.4rem;font-size:.8rem"></div>
      </div>
    </div>

    <div id="tab-patients" style="display:none">
      <h1>Patients</h1>
      <p class="sub">Register, edit, or remove patients</p>
      <div class="grid">
        <div class="card">
          <h3>Register Patient</h3>
          <div class="fields">
            <label>Patient ID</label><input id="pid" value="P001">
            <label>Name</label><input id="pname" value="Test Patient">
            <label>Age</label><input id="page" value="28" type="number" oninput="calcDob(this.value)">
            <label>Date of Birth</label><input id="pdob" value="1998-03-15" type="date" onchange="calcAge(this.value)">
            <label>BMI</label><input id="pbmi" value="22.5" type="number" step="0.1">
            <label>LMP (Last Menstrual Period)</label><input id="plmp" value="" type="date" onchange="calcEDD(this.value)" style="direction:ltr;color-scheme:dark">
            <label>Expected Due Date <span style="color:#888;font-size:.7rem">(LMP + 280 days — estimate)</span></label><input id="pdue" type="text" readonly style="direction:ltr;background:#0a0a16;color:#7c6ff0;cursor:default">
            <label>Phone</label><input id="pphone" value="" placeholder="+1-555-0123">
            <label>Email</label><input id="pemail" value="" placeholder="patient@example.com">
            <label>Address</label><input id="paddr" value="" placeholder="123 Main St, City">
            <label>Blood Type</label><select id="pblood"><option value="">--</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option><option>O+</option><option>O-</option></select>
            <label>Case Type</label><select id="pcase"><option value="follow-up">Follow-up</option><option value="delivery">Delivery</option><option value="both">Both</option></select>
            <label>Emergency Contact Name</label><input id="pecName" value="" placeholder="Spouse / Parent">
            <label>Emergency Contact Phone</label><input id="pecPhone" value="" placeholder="+1-555-9999">
            <label>Profile Photo</label><input id="pphoto" type="file" accept="image/*">
          </div>
          <div class="row"><button class="btn btn-primary" onclick="register()">Register</button></div>
        </div>
        <div class="card">
          <h3>Patient List</h3>
          <div class="fields"><label>Search</label><input id="patientSearch" oninput="loadPatientTable()" placeholder="Filter by ID or name..."></div>
           <table><thead><tr><th>ID</th><th>Name</th><th>Age</th><th>BMI</th><th>Blood</th><th>Case</th><th>Actions</th></tr></thead><tbody id="patientTableBody"></tbody></table>
          <div class="pagination" id="patientPagination"></div>
        </div>
      </div>
    </div>

    <div id="tab-ld" style="display:none">
      <h1>👶 Labor & Delivery</h1>
      <p class="sub">Record deliveries and newborn information</p>
      <div class="grid">
        <div class="card">
          <h3>Delivery Record</h3>
          <div class="fields">
            <label>Patient ID</label><input id="ldPid" value="P001" list="patientList">
            <label>Gestational Age (weeks)</label><input id="ldGa" type="number" placeholder="e.g. 39">
            <label>Mode of Delivery</label><select id="ldMode"><option>Vaginal</option><option>Cesarean Section</option><option>Vacuum Assisted</option><option>Forceps Assisted</option><option>VBAC</option></select>
            <label>Presentation</label><select id="ldPres"><option>Cephalic</option><option>Breech</option><option>Transverse</option><option>Oblique</option></select>
            <label>Labor Duration (minutes)</label><input id="ldDuration" type="number" placeholder="e.g. 480">
            <label>Complications</label><textarea id="ldComp" rows="2" placeholder="PPH, pre-eclampsia, cord prolapse..."></textarea>
            <label>Blood Loss (ml)</label><input id="ldBloodLoss" type="number" placeholder="e.g. 300">
            <label>Perineal Status</label><select id="ldPerineal"><option value="">--</option><option>Intact</option><option>1st Degree Tear</option><option>2nd Degree Tear</option><option>3rd Degree Tear</option><option>4th Degree Tear</option><option>Episiotomy</option></select>
            <label>Placenta Delivery</label><select id="ldPlacenta"><option value="">--</option><option>Spontaneous</option><option>Manual Removal</option><option>Retained (MROP)</option></select>
            <label>Attended By</label><input id="ldBy" value="Dr. Smith">
            <label>Notes</label><textarea id="ldNotes" rows="2" placeholder="Additional delivery notes..."></textarea>
          </div>
          <div class="row"><button class="btn btn-success" onclick="recordDelivery()">Record Delivery</button><span id="ldResult" style="font-size:.78rem;color:#3ba55c"></span></div>
        </div>
        <div class="card">
          <h3>Newborn Record</h3>
          <div class="fields">
            <label>Patient ID</label><input id="nbPid" value="P001" list="patientList">
            <label>Baby Name</label><input id="nbName" placeholder="e.g. Baby Smith">
            <label>Gender</label><select id="nbGender"><option>Male</option><option>Female</option><option>Unknown</option></select>
            <label>Birth Weight (kg)</label><input id="nbWeight" type="number" step="0.01" placeholder="e.g. 3.2">
            <label>Birth Length (cm)</label><input id="nbLength" type="number" step="0.1" placeholder="e.g. 50">
            <label>Head Circumference (cm)</label><input id="nbHead" type="number" step="0.1" placeholder="e.g. 34">
            <label>APGAR 1 min</label><input id="nbApgar1" type="number" min="0" max="10" placeholder="e.g. 8">
            <label>APGAR 5 min</label><input id="nbApgar5" type="number" min="0" max="10" placeholder="e.g. 9">
            <label>APGAR 10 min</label><input id="nbApgar10" type="number" min="0" max="10" placeholder="e.g. 10">
            <label>Feeding Method</label><select id="nbFeed"><option>Breastfeeding</option><option>Formula</option><option>Mixed</option></select>
            <label>Immunizations Given</label><textarea id="nbImmun" rows="2" placeholder="BCG, HepB, Vitamin K..."></textarea>
            <label>Notes</label><textarea id="nbNotes" rows="2" placeholder="Newborn notes..."></textarea>
          </div>
          <div class="row"><button class="btn btn-primary" onclick="recordNewborn()">Record Newborn</button><span id="nbResult" style="font-size:.78rem;color:#3ba55c"></span></div>
        </div>
      </div>
      <div class="grid">
        <div class="card"><h3>Delivery History</h3><div class="fields"><label>Patient ID</label><input id="ldHistPid" value="P001" list="patientList"></div><div class="row"><button class="btn btn-primary btn-xs" onclick="loadDeliveryHistory()">Load</button></div><div id="ldHistoryList" style="font-size:.78rem;color:#999;margin-top:.5rem"></div></div>
        <div class="card"><h3>Newborn Records</h3><div class="fields"><label>Patient ID</label><input id="nbHistPid" value="P001" list="patientList"></div><div class="row"><button class="btn btn-primary btn-xs" onclick="loadNewbornHistory()">Load</button></div><div id="nbHistoryList" style="font-size:.78rem;color:#999;margin-top:.5rem"></div></div>
      </div>
    </div>

    <div id="tab-antenatal" style="display:none">
      <h1>📋 Antenatal Care</h1>
      <p class="sub">Record and track antenatal visits</p>
      <div class="grid">
        <div class="card">
          <h3>New Visit</h3>
          <div class="fields">
            <label>Patient ID</label><input id="ancPid" value="P001" list="patientList">
            <label>Visit Number</label><input id="ancVisit" type="number" value="1">
            <label>Gestational Age (weeks)</label><input id="ancGa" type="number" placeholder="e.g. 24">
            <label>BP Systolic</label><input id="ancBps" type="number" placeholder="120">
            <label>BP Diastolic</label><input id="ancBpd" type="number" placeholder="80">
            <label>Weight (kg)</label><input id="ancWeight" type="number" step="0.1" placeholder="e.g. 65.5">
            <label>Fundal Height (cm)</label><input id="ancFh" type="number" step="0.1" placeholder="e.g. 26">
            <label>Fetal Presentation</label><select id="ancPres"><option value="">--</option><option>Cephalic</option><option>Breech</option><option>Transverse</option><option>Oblique</option></select>
            <label>Fetal Heart Rate</label><input id="ancFhr" type="number" placeholder="e.g. 140">
            <label>Urine Protein</label><select id="ancUp"><option value="">--</option><option>Negative</option><option>Trace</option><option>+1</option><option>+2</option><option>+3</option></select>
            <label>Urine Glucose</label><select id="ancUg"><option value="">--</option><option>Negative</option><option>Trace</option><option>+1</option><option>+2</option><option>+3</option></select>
            <label>Notes</label><textarea id="ancNotes" rows="2" placeholder="Clinical notes for this visit..."></textarea>
          </div>
          <div class="row"><button class="btn btn-primary" onclick="recordANC()">Record Visit</button></div>
        </div>
        <div class="card">
          <h3>Visit History</h3>
          <div class="fields"><label>Patient ID</label><input id="ancHistPid" value="P001" list="patientList"></div>
          <div class="row"><button class="btn btn-primary btn-xs" onclick="loadANCHistory()">Load</button></div>
          <div id="ancHistoryList" style="font-size:.78rem;color:#999;margin-top:.5rem"></div>
        </div>
      </div>
    </div>

    <div id="tab-assess" style="display:none">
      <h1>Assessment</h1>
      <p class="sub">Record vitals and run risk assessment</p>
      <div class="grid">
        <div class="card">
          <h3>🧬 Fetal Vitals</h3>
          <div class="fields">
            <label>Patient ID</label><div class="row" style="gap:4px;margin:0"><input id="apid" value="P001" list="patientList" style="flex:1"><button class="btn btn-outline btn-xs" onclick="openScanner('apid')" title="Scan QR/Barcode">📷</button></div>
            <datalist id="patientList"></datalist>
            <label>Gestational Age (weeks)</label><input id="ga" value="24" type="number">
            <label>BP Systolic</label><input id="bps" value="120" type="number">
            <label>BP Diastolic</label><input id="bpd" value="80" type="number">
            <label>Glucose (mg/dL)</label><input id="glu" value="95" type="number">
            <label>Fetal Heart Rate</label><input id="fhr" value="140" type="number">
            <label>Fetal Movements/hr</label><input id="fmv" value="10" type="number">
          </div>
          <div class="row">
            <button class="btn btn-success" onclick="assess('fetal')">Assess Fetal</button>
          </div>
        </div>
        <div class="card">
          <h3>🤱 Postpartum Vitals</h3>
          <div class="fields">
            <label>Patient ID</label><div class="row" style="gap:4px;margin:0"><input id="ppPid" value="P001" list="patientList" oninput="loadPatientData(this.value)" onchange="loadPatientData(this.value)" style="flex:1"><button class="btn btn-outline btn-xs" onclick="openScanner('ppPid')" title="Scan QR/Barcode">📷</button></div>
            <label>Maternal Age <span id="ppAgeDisplay" style="color:#888;font-size:.75rem">(auto-fills from patient record)</span></label><input id="ppAge" type="number" readonly style="background:#0a0a16;color:#7c6ff0;cursor:default" placeholder="--">
            <label>BMI (pre-pregnancy)</label><input id="ppBmi" type="number" step="0.1" readonly style="background:#0a0a16;color:#7c6ff0;cursor:default" placeholder="e.g. 24.5">
            <label>Parity</label><input id="ppParity" type="number" placeholder="e.g. 1">
            <label>Gestational Age at Delivery</label><input id="ppGa" type="number" placeholder="e.g. 39">
            <label>Pain Score (3 days postpartum)</label><input id="ppPain" type="number" min="0" max="10" placeholder="0-10">
            <label>Back Pain During Gestation</label><select id="ppBackPain"><option value="false">No</option><option value="true">Yes</option></select>
            <label>Delivery Type</label><select id="ppDelivery"><option value="0">Spontaneous Vaginal</option><option value="1">Cesarean Section</option><option value="2">Assisted Vaginal</option></select>
            <label>Newborn Weight (kg)</label><input id="ppNewbornWt" type="number" step="0.1" placeholder="e.g. 3.2">
            <label>Previous Cesarean</label><select id="ppPrevCS"><option value="false">No</option><option value="true">Yes</option></select>
            <label style="margin-top:.5rem;font-weight:700;font-size:.78rem">Medical History</label>
            <label><input type="checkbox" id="ppHistDep"> History of Depression</label>
            <label><input type="checkbox" id="ppHistAnx"> History of Anxiety</label>
            <label><input type="checkbox" id="ppHistDia"> History of Diabetes</label>
            <label><input type="checkbox" id="ppHistHtn"> History of Hypertension</label>
          </div>
          <div class="row">
            <button class="btn btn-success" onclick="assessPostpartum()">Assess Postpartum</button>
          </div>
        </div>
        <div class="card">
          <h3>Risk History</h3>
          <div class="fields"><label>Patient ID</label><input id="hpid" value="P001"></div>
          <div class="row">
            <button class="btn btn-primary" onclick="loadAssessments()">Load Assessments</button>
            <button class="btn btn-danger" onclick="clearAssessments()">Clear</button>
          </div>
          <div id="assessResult"></div>
        </div>
      </div>
      <div id="result"></div>
    </div>

    <div id="tab-history" style="display:none">
      <h1>Patient History</h1>
      <p class="sub">Full patient record with pagination</p>
      <div class="card">
        <div class="fields">
          <label>Patient ID</label>
          <div class="row"><input id="historyPid" value="P001" style="flex:1;max-width:300px"><button class="btn btn-primary btn-xs" onclick="loadFullHistory()">Load</button></div>
        </div>
        <div class="tab-bar">
          <div class="tab active" data-htab="assessments" data-i18n="historyAssessments" onclick="switchHistTab('assessments')">Assessments</div>
          <div class="tab" data-htab="measurements" data-i18n="historyMeasurements" onclick="switchHistTab('measurements')">Measurements</div>
          <div class="tab" data-htab="info" data-i18n="historyInfo" onclick="switchHistTab('info')">Patient Info</div>
        </div>
        <div id="htab-assessments">
          <table><thead><tr><th>Date</th><th>Type</th><th>Risk</th><th>Score</th></tr></thead><tbody id="historyBodyA"></tbody></table>
          <div class="pagination" id="assessPagination"></div>
        </div>
        <div id="htab-measurements" style="display:none">
          <table><thead><tr><th>Date</th><th>GA</th><th>BP</th><th>Glucose</th><th>FHR</th><th>Movements</th><th>Actions</th></tr></thead><tbody id="historyBodyM"></tbody></table>
          <div class="pagination" id="measPagination"></div>
        </div>
        <div id="htab-info" style="display:none">
          <div id="patientInfo" style="padding:.5rem 0;font-size:.85rem;color:#999"></div>
        </div>
      </div>
    </div>

    <div id="tab-realtime" style="display:none">
      <h1>Real-Time Monitor</h1>
      <p class="sub">Live assessment feed via WebSocket</p>
      <div class="card">
        <div class="row">
          <span class="badge badge-low" id="wsStatus">Disconnected</span>
          <span style="font-size:.75rem;color:#666">WebSocket status</span>
        </div>
        <div id="realtimeFeed" class="recent-list" style="max-height:500px;margin-top:1rem">
          <i style="color:#555;font-size:.8rem">Waiting for assessments...</i>
        </div>
      </div>
    </div>

    <div id="tab-ultrasound" style="display:none">
      <h1>Ultrasound Examination</h1>
      <p class="sub">Record and review ultrasound findings</p>
      <div class="grid">
        <div class="card">
          <h3>New Exam</h3>
          <div class="fields">
            <label>Patient ID</label><input id="usPid" value="P001" list="patientList">
            <label>Gestational Age (weeks)</label><input id="usGa" type="number" placeholder="e.g. 24">
            <label>Biparietal Diameter (mm)</label><input id="usBpd" type="number" step="0.1" placeholder="e.g. 60.5">
            <label>Femur Length (mm)</label><input id="usFl" type="number" step="0.1" placeholder="e.g. 45.2">
            <label>Abdominal Circumference (mm)</label><input id="usAc" type="number" step="0.1" placeholder="e.g. 200.0">
            <label>Head Circumference (mm)</label><input id="usHc" type="number" step="0.1" placeholder="e.g. 220.0">
            <label>Estimated Weight (g)</label><input id="usEw" type="number" step="0.1" placeholder="e.g. 2500">
            <label>Amniotic Fluid Index</label><input id="usAfi" type="number" step="0.1" placeholder="e.g. 12.5">
            <label>Placenta Position</label><select id="usPlac"><option value="">--</option><option>Anterior</option><option>Posterior</option><option>Fundal</option><option>Lateral</option><option>Previa</option><option>Low-lying</option></select>
            <label>Presentation</label><select id="usPres"><option value="">--</option><option>Cephalic</option><option>Breech</option><option>Transverse</option><option>Oblique</option></select>
            <label>Fetal Heart Rate (bpm)</label><input id="usHr" type="number" placeholder="e.g. 140">
            <label>CRL (mm)</label><input id="usCrl" type="number" step="0.1" placeholder="e.g. 85.0">
            <label>Findings (JSON)</label><textarea id="usFindings" rows="2" placeholder='{"anomalies":[],"comments":"..."}'></textarea>
            <label>Notes</label><textarea id="usNotes" rows="2" placeholder="Additional notes..."></textarea>
          </div>
          <div class="row"><button class="btn btn-primary" onclick="saveUltrasound()">Save Exam</button></div>
        </div>
        <div class="card">
          <h3>Ultrasound History</h3>
          <div class="fields"><label>Patient ID</label><input id="usHistPid" value="P001" list="patientList"></div>
          <div class="row"><button class="btn btn-primary" onclick="loadUltrasoundHistory()">Load</button></div>
          <div id="usResult" style="margin-top:.8rem"></div>
        </div>
      </div>
    </div>

    <div id="tab-imaging" style="display:none">
      <h1>🔬 Medical Imaging</h1>
      <p class="sub">Upload and review CT scans, X-rays, MRIs, and other medical images</p>
      <div class="grid">
        <div class="card">
          <h3>Upload Image</h3>
          <div class="fields">
            <label>Patient ID</label><input id="imgPid" value="P001" list="patientList">
            <label>Image Type</label><select id="imgType" onchange="toggleImgFields()">
              <option value="CT Scan">CT Scan</option>
              <option value="MRI">MRI</option>
              <option value="X-Ray">X-Ray</option>
              <option value="Ultrasound">Ultrasound</option>
              <option value="Lab Photo">Lab Photo</option>
              <option value="Other">Other</option>
            </select>
            <label>Image File</label><input id="imgFile" type="file" accept="image/*,.dcm">
            <div id="imgStructuredFields"></div>
            <label>Description</label><input id="imgDesc" placeholder="Auto-filled from structured fields">
            <label>Notes</label><textarea id="imgNotes" rows="2" placeholder="Clinical notes..."></textarea>
          </div>
          <div class="row" style="gap:4px;flex-wrap:wrap">
            <button class="btn btn-primary" onclick="uploadImage()">Upload</button>
            <button class="btn btn-outline" onclick="analyzeImage()" id="btnAnalyzeImg" style="display:none">🤖 AI Analyze</button>
            <span id="imgResult" style="font-size:.78rem;color:#3ba55c"></span>
          </div>
        </div>
        <div class="card">
          <h3>Image Gallery</h3>
          <div class="fields"><label>Patient ID</label><input id="imgGalPid" value="P001" list="patientList"></div>
          <div class="row"><button class="btn btn-primary" onclick="loadImages()">Load</button></div>
          <div id="imgGallery" style="margin-top:.8rem"></div>
        </div>
      </div>
    </div>

    <div id="tab-investigations" style="display:none">
      <h1>🧪 <span data-i18n="labResults"></span></h1>
      <p class="sub"><span data-i18n="recordTrackLabResults"></span></p>
      <div class="grid">
        <div class="card">
          <h3 data-i18n="newLabResult"></h3>
          <div class="fields">
            <label data-i18n="patientId"></label><input id="invPid" value="P001" list="patientList">
            <label data-i18n="testType"></label><select id="invType">
              <option>Complete Blood Count (CBC)</option>
              <option>Blood Group & Rh</option>
              <option>OGTT (Glucose Tolerance)</option>
              <option>Urinalysis</option>
              <option>HbA1c</option>
              <option>Hepatitis B (HBsAg)</option>
              <option>HIV Serology</option>
              <option>VDRL/RPR (Syphilis)</option>
              <option>Thyroid Function (TSH)</option>
              <option>Iron Studies</option>
              <option>Vitamin D</option>
              <option>Group B Strep (GBS)</option>
              <option>COVID-19</option>
              <option>Other</option>
            </select>
            <label data-i18n="resultLabel"></label><textarea id="invResultVal" rows="2" data-i18n-placeholder="enterResult"></textarea>
            <label data-i18n="normalRange"></label><input id="invRange" data-i18n-placeholder="egNormalRange">
            <label data-i18n="notesLabel"></label><textarea id="invNotes" rows="2" data-i18n-placeholder="clinicalNotes"></textarea>
            <label>File</label><input id="invFile" type="file" accept="image/*,.pdf" style="font-size:.78rem">
          </div>
          <div class="row"><button class="btn btn-primary" onclick="recordInvestigation()" data-i18n="recordResult">Record Result</button></div>
        </div>
        <div class="card">
          <h3 data-i18n="labHistory"></h3>
          <div class="fields"><label data-i18n="patientId"></label><input id="invHistPid" value="P001" list="patientList"></div>
          <div class="row"><button class="btn btn-primary btn-xs" onclick="loadInvestigationHistory()" data-i18n="loadBtn">Load</button></div>
          <div id="invHistoryList" style="font-size:.78rem;color:#999;margin-top:.5rem"></div>
          <div id="invResultMsg" style="margin-top:.5rem"></div>
        </div>
      </div>
    </div>

    <div id="tab-family" style="display:none">
      <h1>Family Medical History</h1>
      <p class="sub">Maternal and paternal health records</p>
      <div class="grid">
        <div class="card">
          <h3>Maternal History</h3>
          <div class="fields">
            <label>Patient ID</label><div class="row" style="gap:4px;margin:0"><input id="mhPid" value="P001" list="patientList" oninput="loadPatientMaternalData(this.value)" style="flex:1"><button class="btn btn-outline btn-xs" onclick="openScanner('mhPid')" title="Scan QR/Barcode">📷</button></div>
            <label>Gravida (pregnancies)</label><input id="mhGrav" type="number" value="0">
            <label>Para (deliveries)</label><input id="mhPara" type="number" value="0">
            <label>Previous Cesarean</label><select id="mhCs"><option value="false">No</option><option value="true">Yes</option></select>
            <label>Previous Miscarriages</label><input id="mhMis" type="number" value="0">
            <label>Blood Type</label><select id="mhBt"><option value="">--</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option><option>O+</option><option>O-</option></select>
            <label>Rh Factor</label><select id="mhRh"><option value="">--</option><option>Positive</option><option>Negative</option></select>
            <label>Chronic Conditions</label><textarea id="mhCc" rows="2" placeholder="Diabetes, hypertension, etc."></textarea>
            <label>Allergies</label><textarea id="mhAll" rows="2" placeholder="Medication allergies..."></textarea>
            <label>Medications</label><textarea id="mhMed" rows="2" placeholder="Current medications..."></textarea>
            <label>Family History</label><textarea id="mhFh" rows="2" placeholder="Genetic disorders, family diseases..."></textarea>
            <label>Smoking</label><select id="mhSmk"><option value="false">No</option><option value="true">Yes</option></select>
            <label>Alcohol</label><select id="mhAlc"><option value="false">No</option><option value="true">Yes</option></select>
          </div>
          <div class="row"><button class="btn btn-success" onclick="saveMaternalHistory()">Save Maternal</button></div>
        </div>
        <div class="card">
          <h3>Paternal History</h3>
          <div class="fields">
            <label>Patient ID</label><input id="phPid" value="P001" list="patientList">
            <label>Age</label><input id="phAge" type="number" placeholder="e.g. 32">
            <label>Blood Type</label><select id="phBt"><option value="">--</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option><option>O+</option><option>O-</option></select>
            <label>Rh Factor</label><select id="phRh"><option value="">--</option><option>Positive</option><option>Negative</option></select>
            <label>Genetic Disorders</label><textarea id="phGd" rows="2" placeholder="Known genetic conditions..."></textarea>
            <label>Chronic Conditions</label><textarea id="phCc" rows="2" placeholder="Diabetes, hypertension, etc."></textarea>
            <label>Medications</label><textarea id="phMed" rows="2" placeholder="Current medications..."></textarea>
            <label>Smoking</label><select id="phSmk"><option value="false">No</option><option value="true">Yes</option></select>
            <label>Alcohol</label><select id="phAlc"><option value="false">No</option><option value="true">Yes</option></select>
            <label>Family History</label><textarea id="phFh" rows="2" placeholder="Genetic disorders, family diseases..."></textarea>
          </div>
          <div class="row"><button class="btn btn-success" onclick="savePaternalHistory()">Save Paternal</button></div>
        </div>
      </div>
      <div id="familyResult"></div>
    </div>

    <div id="tab-report" style="display:none">
      <h1>Comprehensive Medical Report</h1>
      <p class="sub">Complete patient record — all examinations, assessments, and history</p>
      <div class="card">
        <div class="fields"><label>Patient ID</label><div class="row"><input id="reportPid" value="P001" style="flex:1;max-width:300px" list="patientList"><button class="btn btn-primary btn-xs" onclick="loadReport()">Generate</button><button class="btn btn-outline btn-xs" onclick="printReport()">Print</button></div></div>
      </div>
      <div id="reportContent" style="margin-top:1rem"></div>
    </div>

    <div id="tab-followup" style="display:none">
      <h1>📅 Pregnancy Follow-up</h1>
      <p class="sub">Schedule follow-ups, track high-risk patients, and view pregnancy timeline</p>
      <div class="grid">
        <div class="card">
          <h3>Schedule Follow-up</h3>
          <div class="fields">
            <label>Patient ID</label><div class="row" style="gap:4px;margin:0"><input id="fuPid" value="P001" list="patientList" style="flex:1"><button class="btn btn-outline btn-xs" onclick="openScanner('fuPid')" title="Scan QR">📷</button></div>
            <label>Follow-up Date</label><input id="fuDate" type="date">
            <label>Type</label><select id="fuType"><option value="routine">Routine</option><option value="high_risk">High Risk</option><option value="postpartum">Postpartum</option><option value="specialist">Specialist Referral</option></select>
            <label>Notes</label><textarea id="fuNotes" rows="2" placeholder="e.g. Check BP, glucose, fetal growth..."></textarea>
          </div>
          <div class="row"><button class="btn btn-primary" onclick="scheduleFollowUp()">Schedule</button><span id="fuResult" style="font-size:.78rem;color:#3ba55c"></span></div>
        </div>
        <div class="card">
          <h3>Pending Follow-ups (next 7 days)</h3>
          <div id="pendingFuList" style="font-size:.78rem;color:#999;margin-top:.5rem"><i class="loading">Loading...</i></div>
        </div>
      </div>
      <div class="card" style="margin-top:1rem">
        <h3>📜 Pregnancy Timeline</h3>
        <div class="fields"><label>Patient ID</label><div class="row"><input id="tlPid" value="P001" list="patientList" style="flex:1;max-width:300px"><button class="btn btn-primary btn-xs" onclick="loadTimeline()">Load Timeline</button></div></div>
        <div id="timelineContent" style="margin-top:.8rem"></div>
      </div>
    </div>

    <div id="tab-admin" style="display:none">
      <h1>⚙ Admin Panel</h1>
      <p class="sub">Manage user approvals and system settings</p>
      <div class="card">
        <h3>Pending User Approvals</h3>
        <div id="pendingUsersList"><i class="loading">Loading...</i></div>
      
  <div class="card" style="margin-top:1.5rem">
    <h3>🏥 Facility Management / إدارة المنشآت</h3>
    <div class="row" style="margin-bottom:.8rem">
      <input id="facCode" type="text" class="form-input" placeholder="Code e.g. ALEX01" style="flex:1">
      <input id="facName" type="text" class="form-input" placeholder="Name / الاسم" style="flex:2">
      <input id="facGov" type="text" class="form-input" placeholder="Governorate / المحافظة" style="flex:1">
    </div>
    <div class="row" style="margin-bottom:.8rem">
      <input id="facType" type="text" class="form-input" placeholder="Type e.g. hospital" value="clinic" style="flex:1">
      <input id="facPhone" type="text" class="form-input" placeholder="Phone" style="flex:1">
      <input id="facAddr" type="text" class="form-input" placeholder="Address" style="flex:2">
    </div>
    <button class="btn btn-primary" onclick="addNewFacility()">+ Add Facility / إضافة</button>
    <div id="facilityAdminList" style="margin-top:.8rem"></div>
    <div style="margin-top:1.2rem;border-top:1px solid #2a2a4a;padding-top:1rem">
      <h4>Clinic Branding / العلامة التجارية</h4>
      <p style="font-size:.7rem;color:#666">Customize the name and phone shown in the login box, sidebar, and footer</p>
      <div class="row" style="margin-bottom:.6rem">
        <input id="brandFacCode" type="text" class="form-input" placeholder="Facility code" style="flex:1">
        <input id="brandName" type="text" class="form-input" placeholder="Branding name / الاسم التجاري" style="flex:2">
        <input id="brandPhone" type="text" class="form-input" placeholder="Support phone / رقم الدعم" style="flex:1">
      </div>
      <button class="btn btn-primary" onclick="updateBranding()">Update Branding / تحديث</button>
      <div id="brandingMessage" style="font-size:.7rem;margin-top:.4rem"></div>
      <div style="margin-top:.8rem">
        <label style="font-size:.75rem;color:#999">Upload Logo / رفع الشعار</label>
        <input id="logoUpload" type="file" accept="image/*" style="display:block;margin:.3rem 0;font-size:.75rem">
        <button class="btn btn-primary" onclick="uploadLogo()">Upload Logo / رفع</button>
        <div id="logoMessage" style="font-size:.7rem;margin-top:.4rem"></div>
      </div>
    </div>
  </div>
  <script>
    async function updateBranding(){
      const code=document.getElementById('brandFacCode').value;
      if(!code){alert('Enter facility code');return}
      try{
        await api('/api/facilities/'+code+'/branding','PUT',{
          branding_name:document.getElementById('brandName').value,
          support_phone:document.getElementById('brandPhone').value
        });
        document.getElementById('brandingMessage').innerHTML='<span style="color:#3ba55c">Branding updated!</span>';
      }catch(e){document.getElementById('brandingMessage').innerHTML='<span style="color:#ed4245">Error: '+e.message+'</span>';}
    }
    async function uploadLogo(){
      const code=document.getElementById('brandFacCode').value;
      if(!code){alert('Enter facility code');return}
      const fileInput=document.getElementById('logoUpload');
      if(!fileInput.files.length){alert('Select an image');return}
      const fd=new FormData();
      fd.append('facility_code',code);
      fd.append('file',fileInput.files[0]);
      try{
        const j=await fetch('/api/upload-logo',{method:'POST',body:fd,headers:{'Authorization':'Bearer '+localStorage.getItem('token')}}).then(r=>r.json());
        document.getElementById('logoMessage').innerHTML='<span style="color:#3ba55c">Logo uploaded!</span>';
        loadBranding();
      }catch(e){document.getElementById('logoMessage').innerHTML='<span style="color:#ed4245">Error: '+e.message+'</span>';}
    }
    async function addNewFacility(){
      const code=document.getElementById('facCode').value;
      if(!code){alert('Enter facility code');return}
      try{
        await api('/api/facilities','POST',{
          code, name:document.getElementById('facName').value,
          type:document.getElementById('facType').value,
          governorate:document.getElementById('facGov').value,
          phone:document.getElementById('facPhone').value,
          address:document.getElementById('facAddr').value
        });
        alert('Facility added!');
        document.getElementById('facCode').value='';
        document.getElementById('facName').value='';
        document.getElementById('facGov').value='';
        document.getElementById('facPhone').value='';
        document.getElementById('facAddr').value='';
        loadFacilityAdminList();
      }catch(e){alert('Error: '+e.message);}
    }
    async function loadFacilityAdminList(){
      try{
        const j=await api('/api/facilities');
        const el=document.getElementById('facilityAdminList');
        if(!j||!j.length){el.innerHTML='<i style="color:#555">No facilities</i>';return;}
        el.innerHTML='<table class="table"><tr><th>Code</th><th>Name</th><th>Branding</th><th>Type</th><th>Governorate</th></tr>'+
          j.map(f=>'<tr><td>'+f.code+'</td><td>'+f.name+'</td><td>'+(f.branding_name||'-')+'</td><td>'+f.type+'</td><td>'+(f.governorate||'-')+'</td></tr>').join('')+'</table>';
      }catch(e){/* pass */}
    }
    if(document.querySelector('#tab-admin[style*="block"]')) loadFacilityAdminList();
  </script>
</div>
      <div class="card">
        <h3>System Info</h3>
        <div style="font-size:.8rem;color:#999">
          <div id="sysInfoDb">Database: SQLite3</div>
          <div id="sysInfoUsers">Total Users: --</div>
          <div id="sysInfoPatients">Total Patients: --</div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const WS_URL = location.origin.replace(/^http/, 'ws') + '/ws';
const API = '';
let TOKEN = localStorage.getItem('token') || '';
let USER = localStorage.getItem('user') || '';
let ws = null;
let riskCounts = {high:0,medium:0,low:0};
let overviewChart = null;
let currentLang = localStorage.getItem('lang') || 'en';

const LANG = {
  en: {
    loginTitle: 'Private Clinic — Obstetrics Management',
    loginTagline: 'Maternity Care · Antenatal Visits · Follow-ups',
    username: 'Username',
    password: 'Password',
    signIn: 'Sign In',
    register: 'Register',
    invalidCred: 'Invalid credentials',
    pendingApproval: 'Account pending approval. Contact admin.',
    userExists: 'Username already exists',
    accCreated: 'Account created! Awaiting admin approval.',
    dashboard: 'Dashboard',
    patients: 'Patients',
    admissions: 'Admissions',
    ld: 'L&D',
    antenatal: 'Antenatal',
    assess: 'Assess',
    ultrasound: 'Ultrasound',
    investigations: 'Lab Results',
    labResults: 'Lab Results',
    imaging: 'Imaging',
    followup: 'Follow-up',
    family: 'Family',
    history: 'History',
    monitor: 'Monitor',
    report: 'Report',
    admin: 'Admin',
    signOut: 'Sign out',
    pendingUsers: 'Pending User Approvals',
    approve: 'Approve',
    reject: 'Reject',
    noPending: 'No pending approvals',
    patientId: 'Patient ID',
    testType: 'Test Type',
    resultLabel: 'Result',
    normalRange: 'Normal Range',
    notesLabel: 'Notes',
    newLabResult: 'New Lab Result',
    labHistory: 'Lab History',
    recordResult: 'Record Result',
    loadBtn: 'Load',
    noInvestigations: 'No investigations',
    enterPatientId: 'Enter Patient ID',
    recordTrackLabResults: 'Record and track lab results for obstetric patients',
    enterResult: 'Enter result...',
    egNormalRange: 'e.g. 12-16 g/dL',
    clinicalNotes: 'Clinical notes...',
    historyAssessments: 'Assessments',
    historyMeasurements: 'Measurements',
    historyInfo: 'Patient Info',
    dashTitle: '🏥 Obstetrics Dashboard',
    dashSubtitle: 'Ward overview · Active patients · Today\'s deliveries',
    totalPatients: 'Total Patients',
    activeAdmissions: 'Active Admissions',
    deliveriesToday: 'Deliveries Today',
    highRisk: 'High Risk',
    wardCensus: 'Ward Census',
    riskDist: 'Risk Distribution',
    upcomingFU7: 'Upcoming Follow-ups (7 days)',
    recentAssessments: 'Recent Assessments',
    bmiCalc: 'BMI Calculator',
    heightCm: 'Height (cm)',
    weightKg: 'Weight (kg)',
    calculate: 'Calculate',
    patientSub: 'Register, edit, or remove patients',
    registerPatient: 'Register Patient',
    name: 'Name',
    age: 'Age',
    dob: 'Date of Birth',
    bmi: 'BMI',
    dueDate: 'Expected Due Date',
    phone: 'Phone',
    email: 'Email',
    address: 'Address',
    bloodType: 'Blood Type',
    caseType: 'Case Type',
    emergContactName: 'Emergency Contact Name',
    emergContactPhone: 'Emergency Contact Phone',
    profilePhoto: 'Profile Photo',
    patientList: 'Patient List',
    search: 'Search',
    idCol: 'ID',
    bloodCol: 'Blood',
    caseCol: 'Case',
    actionsCol: 'Actions',
    selectBtn: 'Select',
    delBtn: 'Del',
    admitTitle: '🛏 Admissions & Ward Management',
    admitSub: 'Admit patients · Manage beds · Discharge',
    admitPatient: 'Admit Patient',
    wardType: 'Ward Type',
    bedNumber: 'Bed Number',
    reasonAdmission: 'Reason for Admission',
    admittedBy: 'Admitted By',
    filterPID: 'Filter by Patient ID',
    dischargePatient: 'Discharge Patient',
    admissionId: 'Admission ID',
    dischargeSummary: 'Discharge Summary',
    discharge: 'Discharge',
    statusActive: 'active',
    statusDischarged: 'discharged',
    ldTitle: '👶 Labor & Delivery',
    ldSubtitle: 'Record deliveries and newborn information',
    deliveryRecord: 'Delivery Record',
    gestAgeWks: 'Gestational Age (weeks)',
    modeDelivery: 'Mode of Delivery',
    presentation: 'Presentation',
    laborDuration: 'Labor Duration (minutes)',
    complications: 'Complications',
    bloodLoss: 'Blood Loss (ml)',
    perinealStatus: 'Perineal Status',
    placentaDelivery: 'Placenta Delivery',
    attendedBy: 'Attended By',
    notes: 'Notes',
    recordDelivery: 'Record Delivery',
    newbornRecord: 'Newborn Record',
    babyName: 'Baby Name',
    gender: 'Gender',
    birthWeight: 'Birth Weight (kg)',
    birthLength: 'Birth Length (cm)',
    headCirc: 'Head Circumference (cm)',
    apgar1: 'APGAR 1 min',
    apgar5: 'APGAR 5 min',
    apgar10: 'APGAR 10 min',
    feedingMethod: 'Feeding Method',
    immunizations: 'Immunizations Given',
    recordNewborn: 'Record Newborn',
    deliveryHistory: 'Delivery History',
    newbornRecords: 'Newborn Records',
    loadBtn2: 'Load',
    male: 'Male',
    female: 'Female',
    spontVaginal: 'Spontaneous Vaginal',
    cSection: 'Cesarean Section',
    assistVaginal: 'Assisted Vaginal',
    breastfeeding: 'Breastfeeding',
    formula: 'Formula',
    bothFeed: 'Both (Breast & Formula)',
    antenatalTitle: '📋 Antenatal Care',
    antenatalSub: 'Record and track antenatal visits',
    newVisit: 'New Visit',
    visitNum: 'Visit Number',
    bpSystolic: 'BP Systolic',
    bpDiastolic: 'BP Diastolic',
    weightKg2: 'Weight (kg)',
    fundalHeight: 'Fundal Height (cm)',
    fetalPresentation: 'Fetal Presentation',
    fetalHR: 'Fetal Heart Rate',
    urineProtein: 'Urine Protein',
    urineGlucose: 'Urine Glucose',
    recordVisit: 'Record Visit',
    visitHistory: 'Visit History',
    assessTitle: 'Assessment',
    assessSub: 'Record vitals and run risk assessment',
    fetalVitals: '🧬 Fetal Vitals',
    gestAgeWks2: 'Gestational Age (weeks)',
    glucose: 'Glucose (mg/dL)',
    fetalHR2: 'Fetal Heart Rate',
    fetalMovements: 'Fetal Movements/hr',
    assessFetal: 'Assess Fetal',
    postpartumVitals: '🤱 Postpartum Vitals',
    maternalAge: 'Maternal Age',
    bmiPrepreg: 'BMI (pre-pregnancy)',
    parity: 'Parity',
    gestAgeDelivery: 'Gestational Age at Delivery',
    painScore3: 'Pain Score (3 days postpartum)',
    backPainGest: 'Back Pain During Gestation',
    deliveryType: 'Delivery Type',
    newbornWeight: 'Newborn Weight (kg)',
    prevCesarean: 'Previous Cesarean',
    medicalHistory: 'Medical History',
    histDepression: 'History of Depression',
    histAnxiety: 'History of Anxiety',
    histDiabetes: 'History of Diabetes',
    histHypertension: 'History of Hypertension',
    assessPostpartum: 'Assess Postpartum',
    riskHistory: 'Risk History',
    loadAssessments: 'Load Assessments',
    clearBtn: 'Clear',
    historyTitle: 'Patient History',
    historySub: 'Full patient record with pagination',
    dateCol: 'Date',
    typeCol: 'Type',
    riskCol: 'Risk',
    scoreCol: 'Score',
    gaCol: 'GA',
    bpCol: 'BP',
    glucoseCol: 'Glucose',
    fhrCol: 'FHR',
    movementsCol: 'Movements',
    monitorTitle: 'Real-Time Monitor',
    monitorSub: 'Live assessment feed via WebSocket',
    usTitle: 'Ultrasound Examination',
    usSubtitle: 'Record and review ultrasound findings',
    newExam: 'New Exam',
    bpd: 'Biparietal Diameter (mm)',
    femurLen: 'Femur Length (mm)',
    abdominalCirc: 'Abdominal Circumference (mm)',
    headCirc2: 'Head Circumference (mm)',
    estWeight: 'Estimated Weight (g)',
    amnioticFluid: 'Amniotic Fluid Index',
    placentaPos: 'Placenta Position',
    usFetalHR: 'Fetal Heart Rate (bpm)',
    crl: 'CRL (mm)',
    findingsJson: 'Findings (JSON)',
    saveExam: 'Save Exam',
    usHistory: 'Ultrasound History',
    imagingTitle: '🔬 Medical Imaging',
    imagingSub: 'Upload and review CT scans, X-rays, MRIs, and other medical images',
    uploadImage: 'Upload Image',
    imageType: 'Image Type',
    imageFile: 'Image File',
    description: 'Description',
    upload: 'Upload',
    imageGallery: 'Image Gallery',
    ctType: 'CT',
    mriType: 'MRI',
    xrayType: 'X-Ray',
    usType: 'Ultrasound',
    labPhoto: 'Lab Photo',
    otherType: 'Other',
    familyTitle: 'Family Medical History',
    familySub: 'Maternal and paternal health records',
    maternalHistory: 'Maternal History',
    gravida: 'Gravida (pregnancies)',
    para: 'Para (deliveries)',
    prevCS: 'Previous Cesarean',
    prevMisc: 'Previous Miscarriages',
    rhFactor: 'Rh Factor',
    chronicCond: 'Chronic Conditions',
    allergies: 'Allergies',
    medications: 'Medications',
    familyHx: 'Family History',
    smoking: 'Smoking',
    alcohol: 'Alcohol',
    saveMaternal: 'Save Maternal',
    paternalHistory: 'Paternal History',
    geneticDisorders: 'Genetic Disorders',
    savePaternal: 'Save Paternal',
    reportTitle: 'Comprehensive Medical Report',
    reportSub: 'Complete patient record — all examinations, assessments, and history',
    generate: 'Generate',
    printBtn: 'Print',
    fuTitle: '📅 Pregnancy Follow-up',
    fuSubtitle: 'Schedule follow-ups, track high-risk patients, and view pregnancy timeline',
    scheduleFU: 'Schedule Follow-up',
    fuDate: 'Follow-up Date',
    schedule: 'Schedule',
    pendingFU7: 'Pending Follow-ups (next 7 days)',
    timelineTitle: '📜 Pregnancy Timeline',
    loadTimeline: 'Load Timeline',
    routine: 'Routine',
    adminTitle: '⚙ Admin Panel',
    adminSub: 'Manage user approvals and system settings',
    sysInfo: 'System Info',
    scanQR: 'Scan QR / Barcode',
    cancel: 'Cancel',
    backBtn: '← Back',
    loading: 'Loading...',
    today: 'Today',
    thisWeek: 'This Week',
    thisMonth: 'This Month',
    noData: 'No data',
    positive: 'Positive',
    negative: 'Negative',
    normal: 'Normal',
    abnormal: 'Abnormal',
    present: 'Present',
    absent: 'Absent',
    vertex: 'Vertex',
    breech: 'Breech',
    transverse: 'Transverse',
    anterior: 'Anterior',
    posterior: 'Posterior',
    fundal: 'Fundal',
    previa: 'Previa',
    abruption: 'Abruption',
    complete: 'Complete',
    incomplete: 'Incomplete',
    followUp: 'Follow-up',
    delivery: 'Delivery',
    both: 'Both',
    postnatal: 'Postnatal',
    laborDelivery: 'Labor & Delivery',
    nicu: 'NICU',
    observation: 'Observation',
    inProgress: 'In Progress',
    completed: 'Completed',
    cancelled: 'Cancelled',
    yes: 'Yes',
    no: 'No',
    noneOpt: 'None',
    bmiStatus: 'BMI',
    idleStatus: 'Enter a Patient ID',
    patientNotFound: 'Patient not found',
    noEvents: 'No events found for this patient',
    generatingReport: 'Generating report...',
    savedMaternal: '✓ Saved: Maternal history',
    savedPaternal: '✓ Saved: Paternal history',
    errorLabel: 'Error:',
    enterPID: 'Enter Patient ID',
    aPos: 'A+',
    bPos: 'B+',
    abPos: 'AB+',
    oPos: 'O+',
    aNeg: 'A-',
    bNeg: 'B-',
    abNeg: 'AB-',
    oNeg: 'O-',
    aPosShort: 'A+',
    bPosShort: 'B+',
    abPosShort: 'AB+',
    oPosShort: 'O+'
  },
  ar: {
    loginTitle: 'العيادة الخاصة — إدارة التوليد',
    loginTagline: 'رعاية الأمومة · زيارات الحمل · المتابعات',
    username: 'اسم المستخدم',
    password: 'كلمة المرور',
    signIn: 'تسجيل الدخول',
    register: 'تسجيل',
    invalidCred: 'بيانات الدخول غير صحيحة',
    pendingApproval: 'الحساب قيد المراجعة. اتصل بالإدارة.',
    userExists: 'اسم المستخدم موجود بالفعل',
    accCreated: 'تم إنشاء الحساب! في انتظار موافقة الإدارة.',
    dashboard: 'لوحة التحكم',
    patients: 'الحالات',
    admissions: 'الدخول',
    ld: 'الولادة',
    antenatal: 'رعاية الحمل',
    assess: 'التقييم',
    ultrasound: 'الموجات فوق الصوتية',
    investigations: 'نتيجة المختبر',
    labResults: 'نتائج المختبرات',
    imaging: 'الاشعة',
    followup: 'متابعة حمل',
    family: 'التاريخ العائلي',
    history: 'السجل',
    monitor: 'المراقبة',
    report: 'التقرير',
    admin: 'الإدارة',
    signOut: 'تسجيل الخروج',
    pendingUsers: 'المستخدمون في انتظار الموافقة',
    approve: 'موافقة',
    reject: 'رفض',
    noPending: 'لا يوجد مستخدمون في انتظار الموافقة',
    patientId: 'رقم المريض',
    testType: 'نوع التحليل',
    resultLabel: 'النتيجة',
    normalRange: 'النطاق الطبيعي',
    notesLabel: 'ملاحظات',
    newLabResult: 'نتيجة مختبر جديدة',
    labHistory: 'سجل المختبرات',
    recordResult: 'تسجيل النتيجة',
    loadBtn: 'تحميل',
    noInvestigations: 'لا توجد نتائج',
    enterPatientId: 'أدخل رقم المريض',
    recordTrackLabResults: 'تسجيل وتتبع نتائج المختبرات للحوامل',
    enterResult: 'أدخل النتيجة...',
    egNormalRange: 'مثال 12-16 جم/ديسيلتر',
    clinicalNotes: 'ملاحظات سريرية...',
    historyAssessments: 'التقييمات',
    historyMeasurements: 'القياسات',
    historyInfo: 'معلومات المريض',
    dashTitle: '🏥 لوحة تحكم التوليد',
    dashSubtitle: 'نظرة عامة · المرضى النشطون · ولادات اليوم',
    totalPatients: 'إجمالي المرضى',
    activeAdmissions: 'الدخول النشط',
    deliveriesToday: 'ولادات اليوم',
    highRisk: 'عالية الخطورة',
    wardCensus: 'إحصاء الجناح',
    riskDist: 'توزيع المخاطر',
    upcomingFU7: 'المتابعات القادمة (7 أيام)',
    recentAssessments: 'آخر التقييمات',
    bmiCalc: 'حاسبة مؤشر كتلة الجسم',
    heightCm: 'الطول (سم)',
    weightKg: 'الوزن (كجم)',
    calculate: 'حساب',
    patientSub: 'تسجيل أو تعديل أو حذف المرضى',
    registerPatient: 'تسجيل مريض',
    name: 'الاسم',
    age: 'العمر',
    dob: 'تاريخ الميلاد',
    bmi: 'مؤشر كتلة الجسم',
    dueDate: 'تاريخ الولادة المتوقع',
    phone: 'الهاتف',
    email: 'البريد الإلكتروني',
    address: 'العنوان',
    bloodType: 'فصيلة الدم',
    caseType: 'نوع الحالة',
    emergContactName: 'اسم جهة الاتصال للطوارئ',
    emergContactPhone: 'هاتف جهة الاتصال للطوارئ',
    profilePhoto: 'الصورة الشخصية',
    patientList: 'قائمة المرضى',
    search: 'بحث',
    idCol: 'المعرف',
    bloodCol: 'فصيلة الدم',
    caseCol: 'الحالة',
    actionsCol: 'إجراءات',
    selectBtn: 'اختيار',
    delBtn: 'حذف',
    admitTitle: '🛏 الدخول وإدارة الجناح',
    admitSub: 'دخول المرضى · إدارة الأسرة · الخروج',
    admitPatient: 'دخول مريض',
    wardType: 'نوع الجناح',
    bedNumber: 'رقم السرير',
    reasonAdmission: 'سبب الدخول',
    admittedBy: 'بواسطة',
    filterPID: 'تصفية برقم المريض',
    dischargePatient: 'خروج مريض',
    admissionId: 'معرف الدخول',
    dischargeSummary: 'ملخص الخروج',
    discharge: 'خروج',
    statusActive: 'نشط',
    statusDischarged: 'خرج',
    ldTitle: '👶 المخاض والولادة',
    ldSubtitle: 'تسجيل الولادات ومعلومات المولود',
    deliveryRecord: 'سجل الولادة',
    gestAgeWks: 'عمر الحمل (أسابيع)',
    modeDelivery: 'طريقة الولادة',
    presentation: 'وضعية الجنين',
    laborDuration: 'مدة المخاض (دقائق)',
    complications: 'المضاعفات',
    bloodLoss: 'فقدان الدم (مل)',
    perinealStatus: 'حالة العجان',
    placentaDelivery: 'ولادة المشيمة',
    attendedBy: 'بواسطة',
    notes: 'ملاحظات',
    recordDelivery: 'تسجيل الولادة',
    newbornRecord: 'سجل المولود',
    babyName: 'اسم المولود',
    gender: 'الجنس',
    birthWeight: 'وزن الولادة (كجم)',
    birthLength: 'طول الولادة (سم)',
    headCirc: 'محيط الرأس (سم)',
    apgar1: 'أبغار دقيقة 1',
    apgar5: 'أبغار دقائق 5',
    apgar10: 'أبغار دقائق 10',
    feedingMethod: 'طريقة التغذية',
    immunizations: 'التطعيمات المعطاة',
    recordNewborn: 'تسجيل المولود',
    deliveryHistory: 'سجل الولادات',
    newbornRecords: 'سجلات المواليد',
    male: 'ذكر',
    female: 'أنثى',
    spontVaginal: 'ولادة طبيعية',
    cSection: 'ولادة قيصرية',
    assistVaginal: 'ولادة طبيعية مُساعدة',
    breastfeeding: 'رضاعة طبيعية',
    formula: 'حليب صناعي',
    bothFeed: 'رضاعة طبيعية وصناعية',
    antenatalTitle: '📋 رعاية الحمل',
    antenatalSub: 'تسجيل ومتابعة زيارات الحمل',
    newVisit: 'زيارة جديدة',
    visitNum: 'رقم الزيارة',
    bpSystolic: 'الضغط الانقباضي',
    bpDiastolic: 'الضغط الانبساطي',
    weightKg2: 'الوزن (كجم)',
    fundalHeight: 'ارتفاع قاع الرحم (سم)',
    fetalPresentation: 'وضعية الجنين',
    fetalHR: 'معدل ضربات قلب الجنين',
    urineProtein: 'بروتين البول',
    urineGlucose: 'جلوكوز البول',
    recordVisit: 'تسجيل الزيارة',
    visitHistory: 'سجل الزيارات',
    assessTitle: 'التقييم',
    assessSub: 'تسجيل العلامات الحيوية وتقييم المخاطر',
    fetalVitals: '🧬 العلامات الحيوية للجنين',
    gestAgeWks2: 'عمر الحمل (أسابيع)',
    glucose: 'الجلوكوز (مجم/ديسيلتر)',
    fetalHR2: 'معدل ضربات قلب الجنين',
    fetalMovements: 'حركات الجنين/ساعة',
    assessFetal: 'تقييم الجنين',
    postpartumVitals: '🤱 العلامات الحيوية بعد الولادة',
    maternalAge: 'عمر الأم',
    bmiPrepreg: 'مؤشر كتلة الجسم (قبل الحمل)',
    parity: 'عدد الولادات',
    gestAgeDelivery: 'عمر الحمل عند الولادة',
    painScore3: 'درجة الألم (3 أيام بعد الولادة)',
    backPainGest: 'آلام الظهر أثناء الحمل',
    deliveryType: 'نوع الولادة',
    newbornWeight: 'وزن المولود (كجم)',
    prevCesarean: 'ولادة قيصرية سابقة',
    medicalHistory: 'التاريخ الطبي',
    histDepression: 'تاريخ من الاكتئاب',
    histAnxiety: 'تاريخ من القلق',
    histDiabetes: 'تاريخ من السكري',
    histHypertension: 'تاريخ من ارتفاع الضغط',
    assessPostpartum: 'تقييم ما بعد الولادة',
    riskHistory: 'تاريخ المخاطر',
    loadAssessments: 'تحميل التقييمات',
    clearBtn: 'مسح',
    historyTitle: 'تاريخ المريض',
    historySub: 'سجل كامل للمريض مع الترقيم',
    dateCol: 'التاريخ',
    typeCol: 'النوع',
    riskCol: 'المخاطر',
    scoreCol: 'الدرجة',
    gaCol: 'عمر الحمل',
    bpCol: 'ضغط الدم',
    glucoseCol: 'الجلوكوز',
    fhrCol: 'معدل ضربات قلب الجنين',
    movementsCol: 'الحركات',
    monitorTitle: 'المراقبة المباشرة',
    monitorSub: 'بث مباشر للتقييم عبر WebSocket',
    usTitle: 'فحص الموجات فوق الصوتية',
    usSubtitle: 'تسجيل ومراجعة نتائج الموجات فوق الصوتية',
    newExam: 'فحص جديد',
    bpd: 'القطر ثنائي الجداري (مم)',
    femurLen: 'طول عظم الفخذ (مم)',
    abdominalCirc: 'محيط البطن (مم)',
    headCirc2: 'محيط الرأس (مم)',
    estWeight: 'الوزن المقدر (جم)',
    amnioticFluid: 'مؤشر السائل الأمنيوسي',
    placentaPos: 'موقع المشيمة',
    usFetalHR: 'معدل ضربات قلب الجنين (نبضة/دقيقة)',
    crl: 'طول الجنين (مم)',
    findingsJson: 'النتائج (JSON)',
    saveExam: 'حفظ الفحص',
    usHistory: 'سجل الموجات فوق الصوتية',
    imagingTitle: '🔬 التصوير الطبي',
    imagingSub: 'رفع ومراجعة الأشعة المقطعية والرنين المغناطيسي وغيرها',
    uploadImage: 'رفع صورة',
    imageType: 'نوع الصورة',
    imageFile: 'ملف الصورة',
    description: 'الوصف',
    upload: 'رفع',
    imageGallery: 'معرض الصور',
    ctType: 'أشعة مقطعية',
    mriType: 'رنين مغناطيسي',
    xrayType: 'أشعة سينية',
    usType: 'موجات فوق صوتية',
    labPhoto: 'صورة مختبر',
    otherType: 'أخرى',
    familyTitle: 'التاريخ العائلي الطبي',
    familySub: 'سجلات الصحة للأم والأب',
    maternalHistory: 'تاريخ الأم',
    gravida: 'عدد الحمول',
    para: 'عدد الولادات',
    prevCS: 'ولادة قيصرية سابقة',
    prevMisc: 'الإجهاض السابق',
    rhFactor: 'عامل ريسوس',
    chronicCond: 'الأمراض المزمنة',
    allergies: 'الحساسية',
    medications: 'الأدوية',
    familyHx: 'التاريخ العائلي',
    smoking: 'التدخين',
    alcohol: 'الكحول',
    saveMaternal: 'حفظ تاريخ الأم',
    paternalHistory: 'تاريخ الأب',
    geneticDisorders: 'الاضطرابات الوراثية',
    savePaternal: 'حفظ تاريخ الأب',
    reportTitle: 'التقرير الطبي الشامل',
    reportSub: 'سجل كامل للمريض - جميع الفحوصات والتقييمات والتاريخ',
    generate: 'إنشاء',
    printBtn: 'طباعة',
    fuTitle: '📅 متابعة الحمل',
    fuSubtitle: 'جدولة المتابعات وتتبع المرضى عاليي الخطورة وعرض الجدول الزمني للحمل',
    scheduleFU: 'جدولة متابعة',
    fuDate: 'تاريخ المتابعة',
    schedule: 'جدولة',
    pendingFU7: 'المتابعات المعلقة (الأيام السبعة القادمة)',
    timelineTitle: '📜 الجدول الزمني للحمل',
    loadTimeline: 'تحميل الجدول الزمني',
    routine: 'روتيني',
    adminTitle: '⚙ لوحة الإدارة',
    adminSub: 'إدارة موافقات المستخدمين وإعدادات النظام',
    sysInfo: 'معلومات النظام',
    scanQR: 'مسح رمز الاستجابة السريعة / الباركود',
    cancel: 'إلغاء',
    backBtn: '→ رجوع',
    today: 'اليوم',
    thisWeek: 'هذا الأسبوع',
    thisMonth: 'هذا الشهر',
    noData: 'لا توجد بيانات',
    positive: 'إيجابي',
    negative: 'سلبي',
    normal: 'طبيعي',
    abnormal: 'غير طبيعي',
    present: 'موجود',
    absent: 'غائب',
    vertex: 'قمة الرأس',
    breech: 'مقعدي',
    transverse: 'مستعرض',
    anterior: 'أمامي',
    posterior: 'خلفي',
    fundal: 'قاعي',
    previa: 'منزلق',
    abruption: 'انفصال',
    complete: 'كامل',
    incomplete: 'غير كامل',
    followUp: 'متابعة حمل',
    delivery: 'ولادة',
    both: 'كلاهما',
    postnatal: 'ما بعد الولادة',
    laborDelivery: 'المخاض والولادة',
    nicu: 'العناية المركزة لحديثي الولادة',
    observation: 'المراقبة',
    inProgress: 'قيد التنفيذ',
    completed: 'مكتمل',
    cancelled: 'ملغي',
    yes: 'نعم',
    no: 'لا',
    noneOpt: 'لا يوجد',
    bmiStatus: 'مؤشر كتلة الجسم',
    idleStatus: 'أدخل رقم المريض',
    patientNotFound: 'المريض غير موجود',
    noEvents: 'لا توجد أحداث لهذا المريض',
    generatingReport: 'جاري إنشاء التقرير...',
    savedMaternal: '✓ تم الحفظ: تاريخ الأم',
    savedPaternal: '✓ تم الحفظ: تاريخ الأب',
    errorLabel: 'خطأ:',
    enterPID: 'أدخل رقم المريض',
    aPos: 'A+',
    bPos: 'B+',
    abPos: 'AB+',
    oPos: 'O+',
    aNeg: 'A-',
    bNeg: 'B-',
    abNeg: 'AB-',
    oNeg: 'O-',
    aPosShort: 'A+',
    bPosShort: 'B+',
    abPosShort: 'AB+',
    oPosShort: 'O+'
  }
};

function t(key){return LANG[currentLang]?.[key]||LANG.en[key]||key;}

async function loadBranding(){
  try{
    const fc=window.__FACILITY__||'DEFAULT';
    const j=await api('/api/facilities/'+fc+'/branding');
    const bn=j.branding_name||j.facility_name||'';
    const sp=j.support_phone||'';
    const logoPath=j.branding_logo_path||'';
    if(bn||sp){
      const txt=bn+(sp?' &mdash; '+sp:'');
      const el=document.getElementById('loginBranding');if(el){el.innerHTML=txt;el.dataset.enText=txt}
      const el2=document.getElementById('sidebarBranding');if(el2){el2.innerHTML=txt;el2.dataset.enText=txt}
      const el3=document.getElementById('footerBranding');if(el3){el3.innerHTML=txt;el3.dataset.enText=txt}
    }
    if(bn){
      const dt=document.getElementById('dashTitle');if(dt){dt.innerHTML='🏥 '+bn;dt.dataset.enText=bn}
    }
    // Show logo
    const ll=document.getElementById('loginLogo');
    const sl=document.getElementById('sidebarLogo');
    if(logoPath){
      if(ll){ll.src=logoPath;ll.style.display='block'}
      if(sl){sl.src=logoPath;sl.style.display='block'}
    }else{
      // Try default logo
      const defLogo='/data/logos/default.jpg';
      if(ll){ll.src=defLogo;ll.style.display='block'}
      if(sl){sl.src=defLogo;sl.style.display='block'}
    }
  }catch(e){/* branding fallback silently */}
}
function setLang(lang){
  currentLang = lang;
  localStorage.setItem('lang', lang);
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.toggle('active',b.id.includes(lang)));
  document.documentElement.dir = lang==='ar'?'rtl':'ltr';
  const title=document.getElementById('lgnTitle');if(title)title.textContent=t('loginTitle');
  const tag=document.getElementById('lgnTagline');if(tag)tag.textContent=t('loginTagline');
  const lblU=document.getElementById('lblUser');if(lblU)lblU.textContent=t('username');
  const lblP=document.getElementById('lblPass');if(lblP)lblP.textContent=t('password');
  const btnSi=document.getElementById('btnSignin');if(btnSi)btnSi.textContent=t('signIn');
  const btnRe=document.getElementById('btnRegister');if(btnRe)btnRe.textContent=t('register');
  translateSidebar();
  translateContent();
  autoTranslateAll();
  const so=document.querySelector('.user-info span:last-child');
  if(so) so.textContent=t('signOut');
}

function translateSidebar(){
  document.querySelectorAll('.nav-item').forEach(el=>{
    const tab=el.dataset?.tab;
    const textSpan=el.querySelector('span:not(.ico)');
    if(tab && t(tab) && textSpan) textSpan.textContent=t(tab);
  });
}

function translateContent(){
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    const key=el.dataset.i18n;
    if(t(key)) el.textContent=t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>{
    const key=el.dataset.i18nPlaceholder;
    if(t(key)) el.placeholder=t(key);
  });
}



function autoTranslateAll(){
  const sel = 'h1,h2,h3,h4,h5,label,button,th,span:not(.ico),p,.tab,.sub,option,dt,dd,legend,div';
  const en = LANG.en;
  const ar = LANG.ar || {};
  if(currentLang==='en'){
    document.querySelectorAll(sel).forEach(el=>{
      if(el.dataset.i18n) return;
      if(el.dataset.enText!==undefined){
        el.textContent=el.dataset.enText;
        delete el.dataset.enText;
      }
    });
    return;
  }
  const rev={};
  for(const k of Object.keys(en)){const v=en[k];if(typeof v==='string'&&v.length>1)rev[v]=k;}
  document.querySelectorAll(sel).forEach(el=>{
    if(el.dataset.i18n) return;
    let txt=el.textContent.trim();
    if(!txt||txt.length<2) return;
    let key=rev[txt]||(el.dataset.enText?rev[el.dataset.enText.trim()]:null);
    if(!key) return;
    const arText=ar[key];
    if(!arText||arText===txt) return;
    if(el.dataset.enText===undefined) el.dataset.enText=txt;
    el.textContent=arText;
  });
}

function togglePW(inputId,btn){
  const inp=document.getElementById(inputId);
  if(!inp) return;
  if(inp.type==='password'){inp.type='text';btn.textContent='🙈';}else{inp.type='password';btn.textContent='👁';}
}

if(TOKEN){
  document.getElementById('loginOverlay').style.display='none';
  document.getElementById('appLayout').style.display='flex';
  document.getElementById('userDisplay').textContent = USER || 'User';
  initApp();
}

async function api(path,method='GET',body=null,noAuth=false){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(!noAuth && TOKEN) opts.headers['Authorization']='Bearer '+TOKEN;
  if(body) opts.body=JSON.stringify(body);
  const r=await fetch(API+path,opts);
  if(r.status===401 && !noAuth){alert('Session expired');doLogout();return null}
  if(!r.ok) throw new Error((await r.json()).detail||r.statusText);
  if(r.status===204) return null;
  return r.json();
}

async function doLogin(){
  const u=document.getElementById('loginUser').value;
  const p=document.getElementById('loginPass').value;
  try{
    const j=await api('/api/auth/login','POST',{username:u,password:p,facility_code:document.getElementById('loginFacility').value||''});
    TOKEN=j.token;USER=j.username;
    localStorage.setItem('token',TOKEN);localStorage.setItem('user',USER);
    document.getElementById('loginOverlay').style.display='none';
    document.getElementById('appLayout').style.display='flex';
    document.getElementById('userDisplay').textContent=USER;
    langToSidebar();
    initApp();
    loadBranding();
  }catch(e){
    const el=document.getElementById('loginError');
    if(e.message.includes('pending')) el.textContent=t('pendingApproval');
    else el.textContent=t('invalidCred');
    el.style.display='block';
  }
}

function langToSidebar(){
  translateSidebar();
  translateContent();
  const so=document.querySelector('.user-info span:last-child');
  if(so) so.textContent=t('signOut');
}

async function doRegister(){
  const u=document.getElementById('loginUser').value;
  const p=document.getElementById('loginPass').value;
  try{
    const j=await api('/api/auth/register','POST',{username:u,password:p},true);
    if(j.approved){
      TOKEN=j.token;USER=j.username;
      localStorage.setItem('token',TOKEN);localStorage.setItem('user',USER);
      document.getElementById('loginOverlay').style.display='none';
      document.getElementById('appLayout').style.display='flex';
      document.getElementById('userDisplay').textContent=USER;
      initApp();
    }else{
      document.getElementById('loginError').textContent=t('accCreated');
      document.getElementById('loginError').style.display='block';
    }
  }catch(e){
    const el=document.getElementById('loginError');
    if(e.message.includes('exists')) el.textContent=t('userExists');
    else el.textContent=e.message;
    el.style.display='block';
  }
}

function doLogout(){
  TOKEN='';localStorage.removeItem('token');localStorage.removeItem('user');
  if(ws) ws.close();
  document.getElementById('appLayout').style.display='none';
  document.getElementById('loginOverlay').style.display='flex';
}

// ── Multi-facility functions ──
function showFacilityPicker(){
  const picker=document.getElementById('facilityPicker');
  if(picker) picker.style.display=picker.style.display==='none'?'block':'none';
  if(!document.getElementById('facilityList').children.length) loadFacilityList();
}

async function loadFacilityList(){
  try{
    const j=await api('/api/facilities');
    const list=document.getElementById('facilityList');
    if(!list) return;
    if(!j||!j.length){list.innerHTML='<div style="color:#555;padding:.5rem">No facilities configured</div>';return;}
    list.innerHTML=j.map(f=>`<div class="recent-item" onclick="selectFacility('${f.code}','${f.name.replace(/'/g,"\\'")}')" style="cursor:pointer"><b>${f.code}</b> — ${f.name} <span style="color:#666;font-size:.8rem">(${f.governorate||''})</span></div>`).join('');
  }catch(e){/* pass */}
}

function selectFacility(code,name){
  document.getElementById('loginFacility').value=code;
  document.getElementById('facilityPicker').style.display='none';
}



function initApp(){
  setLang(localStorage.getItem('lang')||'en');
  // Show admin nav if admin role
  checkAdmin();
  connectWS();
  loadDashboard();
  loadPatientTable();
  loadPatientDropdown();
  calcEDD(document.getElementById('plmp')?.value);
  loadPatientData(document.getElementById('ppPid')?.value);
  getNextPatientId();
  // Set facility code from dashboard injection
  try{window.__FACILITY__=(window.__FD__||{}).code||'DEFAULT';}catch(e){window.__FACILITY__='DEFAULT';}
  loadBranding();
}

async function checkAdmin(){
  try{
    const u=await api('/api/auth/me');
    if(u&&u.role==='admin'){
      document.getElementById('adminNav').style.display='flex';
      loadPendingUsers();
    }
  }catch(e){}
}

let prevTab=null;

function switchTab(tab){
  if(tab!==prevTab) prevTab=document.querySelector('.nav-item.active')?.dataset?.tab||null;
  document.querySelectorAll('.main > div').forEach(el=>el.style.display='none');
  document.getElementById('tab-'+tab).style.display='block';
  document.querySelectorAll('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.tab===tab));
  if(tab==='dashboard') loadDashboard();
  if(tab==='patients'){loadPatientTable();calcEDD(document.getElementById('plmp')?.value);}
  if(tab==='investigations') loadInvestigationHistory();
  if(tab==='followup'){loadPendingFollowUps();document.getElementById('fuDate').value=new Date().toISOString().slice(0,10);}
  if(tab==='assess'){loadPatientData(document.getElementById('ppPid')?.value);}
  if(tab==='family') loadPatientMaternalData(document.getElementById('mhPid')?.value);
  document.getElementById('backBtn').classList.toggle('show',tab!=='dashboard');
  autoTranslateAll();
}

function goBack(){
  if(prevTab) switchTab(prevTab);
}

// ── WebSocket ──
function connectWS(){
  if(ws) ws.close();
  ws=new WebSocket(WS_URL);
  ws.onopen=()=>{
    document.getElementById('wsStatus').textContent='Connected';
    document.getElementById('wsStatus').className='badge badge-low';
  };
  ws.onmessage=(e)=>{
    const msg=JSON.parse(e.data);
    if(msg.type==='recent'){
      msg.data.forEach(a=>addRealtimeItem(a));
    }else if(msg.type==='new_assessment'){
      addRealtimeItem(msg.data);
      updateRiskCounts(msg.data.risk_level);
    }
  };
  ws.onclose=()=>{
    document.getElementById('wsStatus').textContent='Disconnected';
    document.getElementById('wsStatus').className='badge badge-high';
    setTimeout(connectWS,3000);
  };
}

function addRealtimeItem(a){
  const feed=document.getElementById('realtimeFeed');
  const first=feed.querySelector('i');
  if(first) first.remove();
  const d=document.createElement('div');d.className='recent-item';
  const time=new Date().toLocaleTimeString();
  d.innerHTML='<span class="badge badge-'+a.risk_level+'">'+a.risk_level+'</span> '+
    (a.assessment_type||'fetal')+' — '+a.patient_id+' <span style="color:#666;font-size:.7rem">'+
    (a.risk_score*100).toFixed(0)+'% · '+time+'</span>';
  feed.prepend(d);
  if(feed.children.length>50) feed.lastChild.remove();
}

// ── Dashboard ──
async function loadDashboard(){
  try{
    const patients=await api('/api/patients?per_page=1');
    document.getElementById('totalPatients').textContent=patients.total||0;
    // Count follow-ups this week
    try{
      const fu=await api('/api/follow-ups/pending?limit=100');
      const weekFromNow=new Date(Date.now()+7*24*60*60*1000);
      const weekFu=(fu||[]).filter(f=>new Date(f.follow_up_date)<=weekFromNow).length;
      const el=document.getElementById('dashFollowUpsCount');
      if(el) el.textContent=weekFu;
    }catch(e){}
    const recent=await api('/api/assessments/recent?limit=50');
    const list=document.getElementById('recentList');
    if(recent&&recent.length){
      riskCounts={high:0,medium:0,low:0};
      list.innerHTML=recent.slice(0,10).map(a=>
        '<div class="recent-item"><span class="badge badge-'+a.risk_level+'">'+a.risk_level+
        '</span> '+a.assessment_type+' — '+a.patient_id+'</div>'
      ).join('');
      recent.forEach(a=>{if(a.risk_level) riskCounts[a.risk_level]++});
    }else list.innerHTML='<i style="color:#555">No assessments yet</i>';
    document.getElementById('highRiskCount').textContent=riskCounts.high||0;
    // Follow-ups
    try{
      const fu=await api('/api/follow-ups/pending?limit=10');
      const fuEl=document.getElementById('dashFollowUps');
      if(fu&&fu.length) fuEl.innerHTML=fu.map(f=>'<div class="recent-item"><b>'+(f.follow_up_date||'').slice(0,10)+'</b> <span style="color:#7c6ff0">'+(f.patient_id||'')+'</span>'+(f.patient_name?' - '+f.patient_name:'')+' | '+(f.type||'')+'</div>').join('');
      else fuEl.innerHTML='<span style="color:#555">No pending follow-ups</span>';
    }catch(e){}
    drawOverviewChart();
  }catch(e){}
}

function drawOverviewChart(){
  const ctx=document.getElementById('overviewChart').getContext('2d');
  if(overviewChart) overviewChart.destroy();
  overviewChart=new Chart(ctx,{type:'doughnut',data:{
    labels:['High','Medium','Low'],
    datasets:[{data:[riskCounts.high||0,riskCounts.medium||0,riskCounts.low||0],backgroundColor:['#ed4245','#faa61a','#3ba55c']}]
  },options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#ccc',font:{size:10}}}}}});
}

function updateRiskCounts(level){
  if(level) riskCounts[level]=(riskCounts[level]||0)+1;
  document.getElementById('highRiskCount').textContent=riskCounts.high||0;
  drawOverviewChart();
}

// ── Patients ──
async function loadPatientTable(page=1){
  const search=document.getElementById('patientSearch').value.toLowerCase();
  try{
    const data=await api('/api/patients?page='+page+'&per_page=10');
    const body=document.getElementById('patientTableBody');
    if(!data||!data.items.length){
      body.innerHTML='<tr><td colspan="7" style="text-align:center;color:#555">No patients</td></tr>';
      document.getElementById('patientPagination').innerHTML='';
      return;
    }
    const filtered=data.items.filter(p=>p.patient_id.toLowerCase().includes(search)||(p.name||'').toLowerCase().includes(search));
    body.innerHTML=filtered.map(p=>
      '<tr><td>'+p.patient_id+'</td><td>'+(p.name||'')+'</td><td>'+(p.age||'-')+'</td><td>'+
      (p.bmi_pre_pregnancy||'-')+'</td><td>'+(p.blood_type||'-')+'</td><td><span class="badge badge-'+(p.case_type==='delivery'?'low':p.case_type==='both'?'medium':'default')+'">'+(p.case_type||'follow-up')+'</span></td><td><button class="btn btn-primary btn-xs" onclick="selectPatient(\''+
      p.patient_id+'\')">Select</button> <button class="btn btn-danger btn-xs" onclick="deletePatient(\''+
      p.patient_id+'\')">Del</button></td></tr>'
    ).join('');
    renderPagination('patientPagination',data.page,data.pages,(p)=>loadPatientTable(p));
  }catch(e){}
}

function selectPatient(pid){
  document.getElementById('apid').value=pid;
  document.getElementById('hpid').value=pid;
  document.getElementById('historyPid').value=pid;
  document.getElementById('mhPid').value=pid;
  loadPatientMaternalData(pid);
  switchTab('assess');
}

async function deletePatient(pid){
  if(!confirm('Delete patient '+pid+'?')) return;
  try{
    await api('/api/patients/'+pid,'DELETE');
    loadPatientTable();
  }catch(e){alert(e.message);}
}

async function getNextPatientId(){
  try{
    const res=await api('/api/patients?per_page=9999');
    const list=res?.items||res||[];
    const ids=list.map(p=>p.patient_id).filter(Boolean);
    let max=0;
    ids.forEach(id=>{
      const n=parseInt(id.replace(/\D/g,''),10);
      if(n>max) max=n;
    });
    const prefix='P0';
    document.getElementById('pid').value=prefix+String(max+1).padStart(3,'0');
  }catch(e){}
}
async function register(){
  const b={patient_id:U('pid'),name:U('pname'),age:+U('page'),bmi_pre_pregnancy:+U('pbmi'),expected_due_date:U('pdue'),
    phone:U('pphone')||null,email:U('pemail')||null,date_of_birth:U('pdob')||null,address:U('paddr')||null,
    emergency_contact_name:U('pecName')||null,emergency_contact_phone:U('pecPhone')||null,blood_type:U('pblood')||null,
    case_type:U('pcase')||'follow-up', facility_code:window.__FACILITY__||'DEFAULT'};
  try{
    const j=await api('/api/patients/register','POST',b);
    // Upload photo if selected
    const photoInput=document.getElementById('pphoto');
    if(photoInput&&photoInput.files&&photoInput.files[0]){
      const fd=new FormData();
      fd.append('file',photoInput.files[0]);
      const r=await fetch('/api/patients/'+b.patient_id+'/photo',{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd});
      if(!r.ok) console.warn('Photo upload failed');
    }
    showResult('<b>Registered:</b> '+j.patient_id,'');
    // Reset form for next registration
    const num = parseInt(j.patient_id.replace(/\D/g,'')) || 0;
    const prefix = 'P0';
    document.getElementById('pid').value = prefix + String(num + 1).padStart(3,'0');
    ['pname','pphone','pemail','paddr','pecName','pecPhone'].forEach(id=>{
      const el=document.getElementById(id);
      if(el) el.value='';
    });
    ['page','pbmi','pdue','pdob','plmp'].forEach(id=>{
      const el=document.getElementById(id);
      if(el) el.value='';
    });
    document.getElementById('pblood').value='';
    document.getElementById('pcase').value='follow-up';
    if(photoInput) photoInput.value='';
    // Auto-create records based on case type
    const ct=b.case_type||'follow-up';
    if(ct==='follow-up'||ct==='both'){
      const fuDate=U('pdue')||new Date().toISOString().slice(0,10);
      api('/api/follow-ups','POST',{patient_id:j.patient_id,follow_up_date:fuDate,type:'routine',notes:'Auto-scheduled from registration'}).catch(()=>{});
    }
    if(ct==='delivery'||ct==='both'){
      // Auto-create delivery record (clinic version — no ward admission)
    }
    loadPatientTable();loadPatientDropdown();
  }catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

// ── Assessment ──
function showAssessmentResult(a){
  const level=a.risk_level;
  updateRiskCounts(level);
  const factors=(a.risk_factors||[]).map(f=>'<li>'+f+'</li>').join('');
  const recs=(a.recommendations||[]).map(r=>'<li>'+(r.text||r)+'</li>').join('');
  const mode=a.method||'rule_based';
  showResult(
    '<div class="row"><h3>Risk Level: <span class="badge badge-'+level+'">'+level.toUpperCase()+
    '</span></h3><span>Score: '+(a.risk_score*100).toFixed(0)+'% | Method: '+mode+'</span></div>'+
    (factors?'<p style="margin-top:.5rem"><b>Risk Factors:</b></p><ul>'+factors+'</ul>':'')+
    (recs?'<p style="margin-top:.5rem"><b>Recommendations:</b></p><ul>'+recs+'</ul>':''),
    'badge-'+level
  );
}

async function assess(type){
  const pid=U('apid');hideResult();
  if(!pid){showResult('<b>Error:</b> Enter a Patient ID','badge-high');return}
  const clinical={
    gestational_age:+U('ga'),blood_pressure_sys:+U('bps'),blood_pressure_dia:+U('bpd'),
    glucose_level:+U('glu'),fetal_heart_rate:+U('fhr'),fetal_movement_count:+U('fmv'),
    heart_rate:80,temperature:37
  };
  try{
    const j=await api('/api/assess/'+type,'POST',{patient_id:pid,clinical_data:clinical});
    showAssessmentResult(j.assessment);
    api('/api/measurements/record','POST',{patient_id:pid,...clinical}).catch(()=>{});
  }catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

let pdTimer=null;
async function loadPatientData(pid){
  clearTimeout(pdTimer);
  const ageInp=document.getElementById('ppAge');
  const ageLbl=document.getElementById('ppAgeDisplay');
  const bmiInp=document.getElementById('ppBmi');
  if(!pid){
    ageInp.value='';ageInp.placeholder='--';ageLbl.textContent='(auto-fills from patient record)';
    bmiInp.value='';bmiInp.placeholder='e.g. 24.5';
    return
  }
  pdTimer=setTimeout(async ()=>{
    ageInp.placeholder='Loading...';
    try{
      const p=await api('/api/patients/'+pid);
      if(p){
        if(p.age!=null){ageInp.value=p.age;ageLbl.textContent='✓ Age '+p.age+' from record';}
        else{ageInp.value='';ageInp.placeholder='No age in record';ageLbl.textContent='(no age found)';}
        if(p.bmi_pre_pregnancy!=null){bmiInp.value=p.bmi_pre_pregnancy;bmiInp.placeholder='✓ from record';}
        else{bmiInp.value='';bmiInp.placeholder='No BMI in record';}
      }else{
        ageInp.value='';ageInp.placeholder='Patient not found';ageLbl.textContent='(enter valid Patient ID)';
        bmiInp.value='';bmiInp.placeholder='Patient not found';
      }
    }catch(e){
      ageInp.value='';ageInp.placeholder='Patient not found';ageLbl.textContent='(enter valid Patient ID)';
      bmiInp.value='';bmiInp.placeholder='Patient not found';
    }
  },400);
}

let mhTimer=null;
async function loadPatientMaternalData(pid){
  clearTimeout(mhTimer);
  const bt=document.getElementById('mhBt');
  const rh=document.getElementById('mhRh');
  bt.value='';rh.value='';
  if(!pid) return;
  mhTimer=setTimeout(async ()=>{
    try{
      const p=await api('/api/patients/'+pid);
      if(p && p.blood_type){
        bt.value=p.blood_type;
        rh.value=p.blood_type.endsWith('+')?'Positive':'Negative';
      }
    }catch(e){}
  },400);
}

async function assessPostpartum(){
  const pid=U('ppPid');hideResult();
  if(!pid){showResult('<b>Error:</b> Enter a Patient ID','badge-high');return}
  const clinical={
    age:+U('ppAge')||0, bmi_pre_pregnancy:+U('ppBmi')||22, gestational_age:+U('ppGa')||39,
    parity:+U('ppParity')||0, previous_cesarean:U('ppPrevCS')==='true',
    pain_score_3days:+U('ppPain')||0, back_pain_gestation:U('ppBackPain')==='true',
    delivery_type:+U('ppDelivery')||0, newborn_weight:+U('ppNewbornWt')||3.0,
    history_depression:document.getElementById('ppHistDep').checked,
    history_anxiety:document.getElementById('ppHistAnx').checked,
    history_diabetes:document.getElementById('ppHistDia').checked,
    history_hypertension:document.getElementById('ppHistHtn').checked,
  };
  try{
    const j=await api('/api/assess/postpartum','POST',{patient_id:pid,clinical_data:clinical});
    showAssessmentResult(j.assessment);
  }catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

async function loadAssessments(page=1){
  const pid=U('hpid');
  try{
    const data=await api('/api/patients/'+pid+'/assessments?page='+page+'&per_page=10');
    const el=document.getElementById('assessResult');
    if(!data||!data.items.length){el.innerHTML='<i style="color:#555">No assessments</i>';return}
    el.innerHTML='<table><thead><tr><th>Date</th><th>Type</th><th>Risk</th><th>Score</th></tr></thead><tbody>'+
      data.items.map(a=>'<tr><td>'+(a.created_at||'').slice(0,16)+'</td><td>'+(a.assessment_type||'')+'</td><td><span class="badge badge-'+(a.risk_level||'default')+'">'+
      (a.risk_level||'-')+'</span></td><td>'+(a.risk_score?a.risk_score.toFixed(2):'-')+'</td></tr>').join('')+
      '</tbody></table>';
  }catch(e){document.getElementById('assessResult').innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

function clearAssessments(){document.getElementById('assessResult').innerHTML='';}

// ── History ──
let histState={tab:'assessments',pageA:1,pageM:1};

function switchHistTab(tab){
  histState.tab=tab;
  document.querySelectorAll('[data-htab]').forEach(el=>el.classList.toggle('active',el.dataset.htab===tab));
  document.querySelectorAll('[id^=htab-]').forEach(el=>el.style.display='none');
  document.getElementById('htab-'+tab).style.display='block';
  loadFullHistory();
}

async function loadFullHistory(){
  const pid=document.getElementById('historyPid').value;
  if(!pid) return;
  const t=histState.tab;
  if(t==='assessments') await loadHistAssessments(pid,histState.pageA);
  else if(t==='measurements') await loadHistMeasurements(pid,histState.pageM);
  else if(t==='info') await loadHistInfo(pid);
}

async function loadHistAssessments(pid,page){
  try{
    const data=await api('/api/patients/'+pid+'/assessments?page='+page+'&per_page=10');
    const body=document.getElementById('historyBodyA');
    if(!data||!data.items.length){body.innerHTML='<tr><td colspan="4" style="text-align:center;color:#555">None</td></tr>';return}
    body.innerHTML=data.items.map(a=>'<tr><td>'+(a.created_at||'').slice(0,16)+'</td><td>'+(a.assessment_type||'')+
      '</td><td><span class="badge badge-'+(a.risk_level||'default')+'">'+(a.risk_level||'-')+'</span></td><td>'+
      (a.risk_score?a.risk_score.toFixed(2):'-')+'</td></tr>').join('');
    renderPagination('assessPagination',data.page,data.pages,(p)=>{histState.pageA=p;loadHistAssessments(pid,p)});
  }catch(e){}
}

async function loadHistMeasurements(pid,page){
  try{
    const data=await api('/api/patients/'+pid+'/measurements?page='+page+'&per_page=10');
    const body=document.getElementById('historyBodyM');
    if(!data||!data.items.length){body.innerHTML='<tr><td colspan="7" style="text-align:center;color:#555">None</td></tr>';return}
    body.innerHTML=data.items.map(m=>'<tr><td>'+(m.recorded_at||'').slice(0,16)+'</td><td>'+(m.gestational_age||'-')+
      '</td><td>'+(m.blood_pressure_sys||'-')+'/'+(m.blood_pressure_dia||'-')+'</td><td>'+(m.glucose_level||'-')+
      '</td><td>'+(m.fetal_heart_rate||'-')+'</td><td>'+(m.fetal_movement_count||'-')+'</td><td>'+
      '<button class="btn btn-danger btn-xs" onclick="deleteMeas(\''+m.id+'\',\''+pid+'\')">Del</button></td></tr>').join('');
    renderPagination('measPagination',data.page,data.pages,(p)=>{histState.pageM=p;loadHistMeasurements(pid,p)});
  }catch(e){}
}

async function loadHistInfo(pid){
  try{
    const p=await api('/api/patients/'+pid);
    const el=document.getElementById('patientInfo');
    if(p) el.innerHTML='<table><tbody>'+Object.entries(p).map(([k,v])=>
      '<tr><td style="color:#888;width:180px">'+k+'</td><td>'+(v||'-')+'</td></tr>'
    ).join('')+'</tbody></table>';
  }catch(e){document.getElementById('patientInfo').innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// ── Patient dropdown ──
async function loadPatientDropdown(){
  try{
    const data=await api('/api/patients?per_page=500');
    const dl=document.getElementById('patientList');
    if(data&&data.items) dl.innerHTML=data.items.map(p=>'<option value="'+p.patient_id+'">'+(p.name?p.patient_id+' - '+p.name:p.patient_id)+'</option>').join('');
  }catch(e){}
}

// ── Ultrasound ──
async function saveUltrasound(){
  const pid=U('usPid');
  if(!pid){showResult('<b>Error:</b> Enter Patient ID','badge-high');return}
  const findings=document.getElementById('usFindings').value;
  let parsedFindings=null;
  if(findings){try{parsedFindings=JSON.parse(findings)}catch(e){}}
  const body={
    patient_id:pid,gestational_age:+U('usGa')||null,
    biparietal_diameter:+U('usBpd')||null,femur_length:+U('usFl')||null,
    abdominal_circumference:+U('usAc')||null,head_circumference:+U('usHc')||null,
    estimated_weight:+U('usEw')||null,amniotic_fluid_index:+U('usAfi')||null,
    placenta_position:U('usPlac')||null,presentation:U('usPres')||null,
    heart_rate:+U('usHr')||null,crl:+U('usCrl')||null,
    findings:parsedFindings,notes:U('usNotes')||null
  };
  try{const j=await api('/api/ultrasound/exam','POST',body);showResult('<b>Saved:</b> Ultrasound exam recorded','');}catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

async function loadUltrasoundHistory(){
  const pid=U('usHistPid');
  const el=document.getElementById('usResult');
  try{
    const j=await api('/api/patients/'+pid+'/ultrasound');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No exams</i>';return}
    el.innerHTML=j.map(e=>
      '<div class="recent-item"><b>'+(e.exam_date||'').slice(0,10)+'</b> GA '+(e.gestational_age||'-')+
      'w | BPD:'+(e.biparietal_diameter||'-')+' FL:'+(e.femur_length||'-')+
      ' | EFW:'+(e.estimated_weight||'-')+'g'+
      ' | HR:'+(e.heart_rate||'-')+
      ' | '+(e.presentation||'')+
      ' | '+(e.placenta_position||'')+
      ' <button class="btn btn-danger btn-xs" onclick="deleteUltrasoundExam('+e.id+')">Del</button>'+
      '</div>'
    ).join('');
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// ── Maternal History ──
async function saveMaternalHistory(){
  const pid=U('mhPid');
  if(!pid){showResult('<b>Error:</b> Enter Patient ID','badge-high');return}
  const body={
    patient_id:pid,gravida:+U('mhGrav'),para:+U('mhPara'),
    previous_cesarean:U('mhCs')==='true',previous_miscarriages:+U('mhMis'),
    blood_type:U('mhBt')||null,rh_factor:U('mhRh')||null,
    chronic_conditions:U('mhCc')||null,allergies:U('mhAll')||null,
    medications:U('mhMed')||null,family_history:U('mhFh')||null,
    smoking:U('mhSmk')==='true',alcohol:U('mhAlc')==='true'
  };
  try{const j=await api('/api/history/maternal','POST',body);document.getElementById('familyResult').innerHTML='<span style="color:#3ba55c">✓ Saved: Maternal history</span>';}catch(e){document.getElementById('familyResult').innerHTML='<span style="color:#ed4245">✗ Error: '+e.message+'</span>';}
}

// ── Paternal History ──
async function savePaternalHistory(){
  const pid=U('phPid');
  if(!pid){showResult('<b>Error:</b> Enter Patient ID','badge-high');return}
  const body={
    patient_id:pid,age:+U('phAge')||null,
    blood_type:U('phBt')||null,rh_factor:U('phRh')||null,
    genetic_disorders:U('phGd')||null,chronic_conditions:U('phCc')||null,
    medications:U('phMed')||null,
    smoking:U('phSmk')==='true',alcohol:U('phAlc')==='true',
    family_history:U('phFh')||null
  };
  try{const j=await api('/api/history/paternal','POST',body);document.getElementById('familyResult').innerHTML='<span style="color:#3ba55c">✓ Saved: Paternal history</span>';}catch(e){document.getElementById('familyResult').innerHTML='<span style="color:#ed4245">✗ Error: '+e.message+'</span>';}
}

async function deleteMeas(id,pid){
  if(!confirm('Delete this measurement?')) return;
  try{await api('/api/measurements/'+id,'DELETE');showResult('Measurement deleted','');histState.pageM=1;loadFullHistory();}catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

async function deleteUltrasoundExam(id){
  if(!confirm('Delete this ultrasound exam?')) return;
  try{await api('/api/ultrasound/'+id,'DELETE');showResult('Ultrasound exam deleted','');loadUltrasoundHistory();}catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

// ── L&D ──
async function recordDelivery(){
  const pid=U('ldPid');const el=document.getElementById('ldResult');
  if(!pid){el.innerHTML='<b style="color:#ed4245">Enter Patient ID</b>';return}
  try{
    const body={patient_id:pid,gestational_age:+U('ldGa')||null,mode_of_delivery:U('ldMode'),presentation:U('ldPres'),labor_duration_minutes:+U('ldDuration')||null,complications:U('ldComp')||null,blood_loss_ml:+U('ldBloodLoss')||null,perineal_status:U('ldPerineal')||null,episiotomy:U('ldPerineal')==='Episiotomy',placenta_delivery:U('ldPlacenta')||null,attended_by:U('ldBy')||null,notes:U('ldNotes')||null};
    await api('/api/deliveries/record','POST',body);
    el.innerHTML='<b>✓ Delivery recorded</b>';loadDeliveryHistory();
  }catch(e){el.innerHTML='<b style="color:#ed4245">✗ '+e.message+'</b>';}
}

async function loadDeliveryHistory(){
  const pid=U('ldHistPid');
  const el=document.getElementById('ldHistoryList');
  if(!pid){el.innerHTML='<i style="color:#555">Enter Patient ID</i>';return}
  try{
    const j=await api('/api/patients/'+pid+'/deliveries');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No deliveries recorded</i>';return}
    el.innerHTML=j.map(d=>'<div class="recent-item"><b>'+(d.delivery_date||'').slice(0,10)+'</b> '+
      d.mode_of_delivery+' at GA '+(d.gestational_age||'-')+'w'+
      (d.complications?' | <span style="color:#ed4245">'+d.complications+'</span>':'')+
      (d.blood_loss_ml?' | BL:'+d.blood_loss_ml+'ml':'')+
      ' | '+d.presentation+' | '+d.attended_by+
      '</div>').join('');
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

async function recordNewborn(){
  const pid=U('nbPid');const el=document.getElementById('nbResult');
  if(!pid){el.innerHTML='<b style="color:#ed4245">Enter Patient ID</b>';return}
  try{
    const body={patient_id:pid,name:U('nbName')||null,gender:U('nbGender'),birth_weight:+U('nbWeight')||null,birth_length:+U('nbLength')||null,head_circumference:+U('nbHead')||null,apgar_1min:+U('nbApgar1')||null,apgar_5min:+U('nbApgar5')||null,apgar_10min:+U('nbApgar10')||null,feeding_method:U('nbFeed'),immunizations:U('nbImmun')||null,notes:U('nbNotes')||null};
    await api('/api/newborns/record','POST',body);
    el.innerHTML='<b>✓ Newborn recorded</b>';loadNewbornHistory();
  }catch(e){el.innerHTML='<b style="color:#ed4245">✗ '+e.message+'</b>';}
}

async function loadNewbornHistory(){
  const pid=U('nbHistPid');
  const el=document.getElementById('nbHistoryList');
  if(!pid){el.innerHTML='<i style="color:#555">Enter Patient ID</i>';return}
  try{
    const j=await api('/api/patients/'+pid+'/newborns');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No newborns recorded</i>';return}
    el.innerHTML=j.map(n=>'<div class="recent-item"><b>'+(n.name||'Baby')+'</b> ('+n.gender+') — '+
      (n.birth_weight?n.birth_weight+'kg':'')+(n.birth_length?' | '+n.birth_length+'cm':'')+
      ' | APGAR: '+(n.apgar_1min||'-')+'/'+(n.apgar_5min||'-')+(n.apgar_10min?'/'+n.apgar_10min:'')+
      ' | Feed: '+n.feeding_method+
      (n.immunizations?' | 💉 '+n.immunizations:'')+
      '</div>').join('');
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// ── Antenatal Care ──
async function recordANC(){
  const pid=U('ancPid');
  if(!pid){showResult('<b>Error:</b> Enter Patient ID','badge-high');return}
  try{
    const body={patient_id:pid,visit_number:+U('ancVisit')||1,gestational_age:+U('ancGa')||null,blood_pressure_sys:+U('ancBps')||null,blood_pressure_dia:+U('ancBpd')||null,weight:+U('ancWeight')||null,fundal_height:+U('ancFh')||null,fetal_presentation:U('ancPres')||null,fetal_heart_rate:+U('ancFhr')||null,urine_protein:U('ancUp')||null,urine_glucose:U('ancUg')||null,notes:U('ancNotes')||null};
    await api('/api/antenatal/visit','POST',body);
    showResult('<b>ANC visit recorded</b> for '+pid,'');loadANCHistory();
  }catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

async function loadANCHistory(){
  const pid=U('ancHistPid');
  const el=document.getElementById('ancHistoryList');
  if(!pid){el.innerHTML='<i style="color:#555">Enter Patient ID</i>';return}
  try{
    const j=await api('/api/patients/'+pid+'/antenatal');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No visits recorded</i>';return}
    el.innerHTML=j.map(v=>'<div class="recent-item"><b>Visit #'+v.visit_number+'</b> '+
      ((v.visit_date||'').slice(0,10)||'')+' | GA '+(v.gestational_age||'-')+'w'+
      ' | BP '+(v.blood_pressure_sys||'-')+'/'+(v.blood_pressure_dia||'-')+
      (v.weight?' | Wt:'+v.weight:'')+
      (v.fundal_height?' | FH:'+v.fundal_height+'cm':'')+
      (v.fetal_heart_rate?' | FHR:'+v.fetal_heart_rate:'')+
      (v.fetal_presentation?' | '+v.fetal_presentation:'')+
      '</div>').join('');
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// ── Investigations ──
async function recordInvestigation(){
  const pid=U('invPid');
  const r=document.getElementById('invResultMsg');
  if(!pid){if(r)r.innerHTML='<i style="color:#ed4245">Enter Patient ID</i>';return}
  try{
    const body={patient_id:pid,test_type:U('invType'),result:U('invResultVal')||null,normal_range:U('invRange')||null,notes:U('invNotes')||null};
    const j=await api('/api/investigations/add','POST',body);
    const invId=j.id;
    const fileInput=document.getElementById('invFile');
    if(fileInput&&fileInput.files&&fileInput.files[0]){
      const fd=new FormData();
      fd.append('file',fileInput.files[0]);
      await fetch('/api/investigations/'+invId+'/file',{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd});
    }
    if(r)r.innerHTML='<i style="color:#3ba55c">Recorded for '+pid+'</i>';
    loadInvestigationHistory();
  }catch(e){if(r)r.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

async function loadInvestigationHistory(){
  const pid=U('invHistPid');
  const el=document.getElementById('invHistoryList');
    if(!pid){el.innerHTML='<i style="color:#555">'+t('enterPatientId')+'</i>';return}
  try{
    const j=await api('/api/patients/'+pid+'/investigations');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">'+t('noInvestigations')+'</i>';return}
    el.innerHTML=j.map(t=>'<div class="recent-item"><b>'+(t.test_type||'')+'</b> '+
      ' <span style="color:#999">'+(t.test_date||'').slice(0,10)+'</span>'+
      ' | Result: '+(t.result||'-')+
      (t.normal_range?' | Normal: '+t.normal_range:'')+
      (t.file_path?' <a href="'+t.file_path+'" target="_blank" style="color:#5865f2">📎File</a>':'')+
      '</div>').join('');
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// ── Admin ──
async function loadPendingUsers(){
  const el=document.getElementById('pendingUsersList');
  if(!el) return;
  try{
    const j=await api('/api/admin/pending-users');
    if(!j||!j.length){el.innerHTML='<i style="color:#3ba55c">'+t('noPending')+'</i>';return}
    el.innerHTML='<table><thead><tr><th>Username</th><th>Role</th><th>Date</th><th>Actions</th></tr></thead><tbody>'+
      j.map(u=>'<tr><td>'+u.username+'</td><td>'+(u.role||'clinician')+'</td><td>'+(u.created_at||'').slice(0,10)+'</td><td>'+
        '<button class="btn btn-success btn-xs" onclick="approveUser(\''+u.username+'\')">'+t('approve')+'</button> '+
        '<button class="btn btn-danger btn-xs" onclick="rejectUser(\''+u.username+'\')">'+t('reject')+'</button></td></tr>'
      ).join('')+'</tbody></table>';
  }catch(e){if(el)el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

async function approveUser(username){
  try{await api('/api/admin/approve-user','POST',{username});showResult('<b>Approved:</b> '+username,'');loadPendingUsers();}catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

async function rejectUser(username){
  try{await api('/api/admin/reject-user','POST',{username});showResult('<b>Rejected:</b> '+username,'');loadPendingUsers();}catch(e){showResult('<b>Error:</b> '+e.message,'badge-high');}
}

// ── Comprehensive Report ──
async function loadReport(){
  const pid=U('reportPid');
  const el=document.getElementById('reportContent');
  if(!pid){el.innerHTML='<i style="color:#ed4245">Enter a Patient ID</i>';return}
  el.innerHTML='<i class="loading">Generating report...</i>';
  try{
    const j=await api('/api/patients/'+pid+'/report');
    const p=j.patient;
    let html='';
    // Header
    html+='<div style="background:#16162a;border-radius:12px;padding:1.5rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
    html+='<div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap">';
    html+='<div style="display:flex;gap:1rem;align-items:start">';
    if(p.photo_path) html+='<img src="/'+p.photo_path+'" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid #7c6ff0" alt="photo">';
    html+='<div><h2 style="color:#7c6ff0;margin:0">'+(p.name||'')+'</h2>';
    html+='<p style="color:#666;font-size:.8rem">Patient ID: '+p.patient_id+' | Age: '+(p.age||'-')+' | BMI: '+(p.bmi_pre_pregnancy||'-')+' | Due: '+(p.expected_due_date||'-')+' | Case: '+(p.case_type||'follow-up')+'</p>';
    if(p.phone||p.email||p.blood_type) html+='<p style="color:#555;font-size:.75rem">'+
      (p.phone?'📞 '+p.phone+' ':'')+(p.email?'✉ '+p.email+' ':'')+(p.blood_type?'🩸 '+p.blood_type:'')+'</p>';
    if(p.address) html+='<p style="color:#555;font-size:.75rem">📍 '+p.address+'</p>';
    if(p.emergency_contact_name) html+='<p style="color:#555;font-size:.75rem">🆘 Emergency: '+p.emergency_contact_name+(p.emergency_contact_phone?' ('+p.emergency_contact_phone+')':'')+'</p>';
    html+='</div></div>';
    html+='<div style="text-align:right;font-size:.7rem;color:#555">Generated: '+j.generated_at.slice(0,16)+'</div>';
    html+='</div></div>';

    // Risk assessments (deduplicated)
    if(j.assessments&&j.assessments.length){
      const seen=new Set();
      const uniq=j.assessments.filter(a=>{
        const d=a.details||{};
        const key=(a.created_at||'').slice(0,10)+'|'+(a.assessment_type||'')+'|'+(a.risk_level||'')+'|'+(a.risk_score||'')+'|'+((d.risk_factors||[]).join(',')||(d.method||''));
        if(seen.has(key)) return false;
        seen.add(key); return true;
      });
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Risk Assessments</h3><table><thead><tr><th>Date</th><th>Type</th><th>Risk Level</th><th>Score</th><th>Details</th></tr></thead><tbody>';
      uniq.forEach(a=>{
        const d=a.details||{};
        const factors=(d.risk_factors||[]).join(', ')||(d.method||'');
        html+='<tr><td>'+(a.created_at||'').slice(0,10)+'</td><td>'+(a.assessment_type||'')+'</td><td><span class="badge badge-'+(a.risk_level||'default')+'">'+(a.risk_level||'-')+'</span></td><td>'+(a.risk_score?a.risk_score.toFixed(2):'-')+'</td><td style="font-size:.7rem;color:#999">'+factors+'</td></tr>';
      });
      html+='</tbody></table></div>';
    }

    // Ultrasound exams
    if(j.ultrasound_exams&&j.ultrasound_exams.length){
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Ultrasound Examinations ('+j.ultrasound_exams.length+')</h3>';
      j.ultrasound_exams.forEach(u=>{
        html+='<div style="border-bottom:1px solid #1e1e3a;padding:.5rem 0;font-size:.78rem">';
        html+='<b>'+(u.exam_date||'').slice(0,10)+'</b> — GA '+(u.gestational_age||'-')+'w';
        if(u.biparietal_diameter) html+=' | BPD: '+u.biparietal_diameter+'mm';
        if(u.femur_length) html+=' | FL: '+u.femur_length+'mm';
        if(u.head_circumference) html+=' | HC: '+u.head_circumference+'mm';
        if(u.abdominal_circumference) html+=' | AC: '+u.abdominal_circumference+'mm';
        if(u.estimated_weight) html+=' | EFW: '+u.estimated_weight+'g';
        if(u.heart_rate) html+=' | FHR: '+u.heart_rate+'bpm';
        if(u.presentation) html+=' | Presentation: '+u.presentation;
        if(u.placenta_position) html+=' | Placenta: '+u.placenta_position;
        if(u.amniotic_fluid_index) html+=' | AFI: '+u.amniotic_fluid_index;
        if(u.notes) html+='<br><span style="color:#888">Notes: '+u.notes+'</span>';
        html+='</div>';
      });
      html+='</div>';
    }

    // Measurements
    if(j.measurements&&j.measurements.length){
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Vitals & Measurements ('+j.measurements.length+')</h3><table><thead><tr><th>Date</th><th>GA</th><th>BP</th><th>Glucose</th><th>FHR</th><th>Movements</th></tr></thead><tbody>';
      j.measurements.forEach(m=>{
        html+='<tr><td>'+(m.recorded_at||'').slice(0,10)+'</td><td>'+(m.gestational_age||'-')+'w</td><td>'+(m.blood_pressure_sys||'-')+'/'+(m.blood_pressure_dia||'-')+'</td><td>'+(m.glucose_level||'-')+'</td><td>'+(m.fetal_heart_rate||'-')+'</td><td>'+(m.fetal_movement_count||'-')+'</td></tr>';
      });
      html+='</tbody></table></div>';
    }

    // Maternal history
    if(j.maternal_history){
      const m=j.maternal_history;
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Maternal History</h3>';
      html+='<table><tbody>';
      html+=row('Gravida/Para',m.gravida+' / '+m.para);
      html+=row('Previous Cesarean',m.previous_cesarean?'Yes':'No');
      html+=row('Miscarriages',m.previous_miscarriages);
      html+=row('Blood Type',m.blood_type||'-');
      html+=row('Rh Factor',m.rh_factor||'-');
      html+=row('Chronic Conditions',m.chronic_conditions||'None');
      html+=row('Allergies',m.allergies||'None');
      html+=row('Medications',m.medications||'None');
      html+=row('Family History',m.family_history||'None');
      html+=row('Smoking',m.smoking?'Yes':'No');
      html+=row('Alcohol',m.alcohol?'Yes':'No');
      html+='</tbody></table></div>';
    }

    // Paternal history
    if(j.paternal_history){
      const f=j.paternal_history;
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Paternal History</h3>';
      html+='<table><tbody>';
      html+=row('Age',f.age||'-');
      html+=row('Blood Type',f.blood_type||'-');
      html+=row('Rh Factor',f.rh_factor||'-');
      html+=row('Genetic Disorders',f.genetic_disorders||'None');
      html+=row('Chronic Conditions',f.chronic_conditions||'None');
      html+=row('Medications',f.medications||'None');
      html+=row('Smoking',f.smoking?'Yes':'No');
      html+=row('Alcohol',f.alcohol?'Yes':'No');
      html+=row('Family History',f.family_history||'None');
      html+='</tbody></table></div>';
    }

    // Admissions
    // Deliveries
    if(j.deliveries&&j.deliveries.length){
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Delivery Records ('+j.deliveries.length+')</h3>';
      j.deliveries.forEach(d=>{
        html+='<div style="border-bottom:1px solid #1e1e3a;padding:.4rem 0;font-size:.78rem">';
        html+='<b>'+(d.delivery_date||'').slice(0,10)+'</b> — '+d.mode_of_delivery+
          ' at GA '+(d.gestational_age||'-')+'w | '+d.presentation+
          (d.labor_duration_minutes?' | Labor: '+d.labor_duration_minutes+'min':'')+
          (d.blood_loss_ml?' | Blood Loss: '+d.blood_loss_ml+'ml':'')+
          (d.complications?'<br><span style="color:#ed4245">Complications: '+d.complications+'</span>':'')+
          (d.attended_by?'<br><span style="color:#888">Attended by: '+d.attended_by+'</span>':'');
        html+='</div>';
      });
      html+='</div>';
    }

    // Newborns
    if(j.newborns&&j.newborns.length){
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Newborn Records ('+j.newborns.length+')</h3>';
      j.newborns.forEach(n=>{
        html+='<div style="border-bottom:1px solid #1e1e3a;padding:.4rem 0;font-size:.78rem">';
        html+='<b>'+(n.name||'Baby')+'</b> ('+n.gender+')'+
          (n.birth_weight?' | Weight: '+n.birth_weight+'kg':'')+
          (n.birth_length?' | Length: '+n.birth_length+'cm':'')+
          (n.head_circumference?' | HC: '+n.head_circumference+'cm':'')+
          ' | APGAR: '+(n.apgar_1min||'-')+'/'+(n.apgar_5min||'-')+
          (n.apgar_10min?'/'+n.apgar_10min:'')+
          ' | Feeding: '+n.feeding_method+
          (n.immunizations?' | Immunizations: '+n.immunizations:'');
        html+='</div>';
      });
      html+='</div>';
    }

    // Antenatal visits
    if(j.antenatal_visits&&j.antenatal_visits.length){
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Antenatal Visits ('+j.antenatal_visits.length+')</h3><table><thead><tr><th>Date</th><th>Visit</th><th>GA</th><th>BP</th><th>Weight</th><th>FH</th><th>FHR</th><th>Presentation</th></tr></thead><tbody>';
      j.antenatal_visits.forEach(v=>{
        html+='<tr><td>'+(v.visit_date||'').slice(0,10)+'</td><td>#'+v.visit_number+'</td><td>'+(v.gestational_age||'-')+'w</td><td>'+(v.blood_pressure_sys||'-')+'/'+(v.blood_pressure_dia||'-')+'</td><td>'+(v.weight||'-')+'</td><td>'+(v.fundal_height||'-')+'</td><td>'+(v.fetal_heart_rate||'-')+'</td><td>'+(v.fetal_presentation||'-')+'</td></tr>';
      });
      html+='</tbody></table></div>';
    }

    // Investigations
    if(j.investigations&&j.investigations.length){
      html+='<div style="background:#16162a;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem">';
      html+='<h3 style="color:#7c6ff0;font-size:.95rem;margin-bottom:.6rem">Laboratory Results ('+j.investigations.length+')</h3><table><thead><tr><th>Date</th><th>Test</th><th>Result</th><th>Normal Range</th></tr></thead><tbody>';
      j.investigations.forEach(t=>{
        html+='<tr><td>'+(t.test_date||'').slice(0,10)+'</td><td>'+(t.test_type||'')+'</td><td>'+(t.result||'-')+'</td><td>'+(t.normal_range||'-')+'</td></tr>';
      });
      html+='</tbody></table></div>';
    }

    if(!html) html='<i style="color:#555">No data available for this patient</i>';
    el.innerHTML=html;
  }catch(e){el.innerHTML='<i style="color:#ed4245">Error: '+e.message+'</i>';}
}

function row(l,v){return '<tr><td style="color:#888;width:220px;padding:.25rem .4rem;font-size:.78rem">'+l+'</td><td style="padding:.25rem .4rem;font-size:.78rem">'+v+'</td></tr>';}

function printReport(){
  const content=document.getElementById('reportContent');
  if(!content||!content.innerHTML) return;
  const w=window.open('','','width=900,height=700');
  w.document.write('<html><head><title>Medical Report</title><style>body{font-family:Arial,sans-serif;padding:2rem;color:#333}table{width:100%;border-collapse:collapse;margin:.5rem 0}th,td{padding:.4rem;text-align:left;border-bottom:1px solid #ddd;font-size:13px}th{background:#f5f5f5}h2{color:#4a3f8a}h3{color:#4a3f8a;margin-top:1.5rem}.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}.badge-high{background:#ed4245;color:#fff}.badge-medium{background:#faa61a}.badge-low{background:#3ba55c;color:#fff}.badge-default{background:#ccc}@media print{body{padding:1rem}}</style></head><body>');
  w.document.write(content.innerHTML);
  w.document.write('</body></html>');
  w.document.close();
  setTimeout(()=>{w.print();w.close()},300);
}

// ── Pagination ──
function renderPagination(containerId,page,pages,onClick){
  const el=document.getElementById(containerId);
  if(pages<=1){el.innerHTML='<span>1 page</span>';return}
  let html='<button class="page-btn" onclick="if('+(page-1)+'>0)('+onClick+')('+(page-1)+')" '+(page<=1?'disabled':'')+'>&#9664;</button>';
  const start=Math.max(1,page-2),end=Math.min(pages,page+2);
  for(let i=start;i<=end;i++){
    html+='<button class="page-btn'+(i===page?' active':'')+'" onclick="('+onClick+')('+i+')">'+i+'</button>';
  }
  html+='<button class="page-btn" onclick="if('+(page+1)+'<='+pages+')('+onClick+')('+(page+1)+')" '+(page>=pages?'disabled':'')+'>&#9654;</button>';
  html+='<span>Page '+page+' of '+pages+'</span>';
  el.innerHTML=html;
}

function calcDob(age){
  const dob=new Date();
  dob.setFullYear(dob.getFullYear()-age);
  document.getElementById('pdob').value=dob.toISOString().slice(0,10);
}
function calcAge(dobStr){
  if(!dobStr) return;
  const bd=new Date(dobStr);
  const today=new Date();
  let age=today.getFullYear()-bd.getFullYear();
  const m=today.getMonth()-bd.getMonth();
  if(m<0||(m===0&&today.getDate()<bd.getDate())) age--;
  document.getElementById('page').value=age;
}
function calcEDD(lmp){
  if(!lmp) return;
  const d=new Date(lmp);
  if(isNaN(d.getTime())) return;
  d.setDate(d.getDate()+280);
  const dd=String(d.getDate()).padStart(2,'0');
  const mm=String(d.getMonth()+1).padStart(2,'0');
  const yyyy=d.getFullYear();
  document.getElementById('pdue').value=dd+'/'+mm+'/'+yyyy;
}
function calcBMI(){
  const hCm=+document.getElementById('bmiHeight').value;
  const w=+document.getElementById('bmiWeight').value;
  const h=hCm/100;
  if(!h||!w){document.getElementById('bmiResult').textContent='';document.getElementById('bmiCategory').textContent='';return}
  const bmi=w/(h*h);
  const idealMin=18.5*h*h, idealMax=24.9*h*h;
  let cat,color,advice,delta;
  if(bmi<18.5){
    cat='Underweight';color='#faa61a';
    delta=idealMin-w;
    advice='<b>Gain '+(delta).toFixed(1)+' kg</b> to reach minimum healthy weight ('+idealMin.toFixed(1)+' kg). Increase caloric intake with nutrient-dense foods, add healthy fats, and consider strength training.'
  }else if(bmi<25){
    cat='Normal';color='#3ba55c';
    delta=w-idealMin;
    advice='Your weight is within the healthy range. Maintain with a balanced diet (veggies, lean protein, whole grains) and regular physical activity (150 min/week moderate exercise).'
  }else if(bmi<30){
    cat='Overweight';color='#faa61a';
    delta=w-idealMax;
    advice='<b>Lose '+(delta).toFixed(1)+' kg</b> to reach maximum healthy weight ('+idealMax.toFixed(1)+' kg). Focus on portion control, reduce processed foods/sugar, and aim for 30 min daily aerobic activity.'
  }else{
    cat='Obese';color='#ed4245';
    delta=w-idealMax;
    advice='<b>Lose '+(delta).toFixed(1)+' kg</b> to reach healthy range. Consult a healthcare provider for a personalized plan. Prioritize whole foods, avoid sugary drinks, and gradually increase physical activity.'
  }
  document.getElementById('bmiResult').textContent=bmi.toFixed(1);
  document.getElementById('bmiCategory').innerHTML=
    '<div style="margin-top:.3rem"><span class="badge" style="background:'+color+'">'+cat+'</span></div>'+
    '<div style="margin-top:.4rem;font-size:.8rem;color:#999">Ideal range: <b>'+idealMin.toFixed(1)+' – '+idealMax.toFixed(1)+' kg</b> for '+hCm.toFixed(0)+' cm</div>'+
    '<div style="margin-top:.2rem;font-size:.8rem;color:#ccc">'+advice+'</div>';
}

// ── Utilities ──
function showResult(html,cssClass){
  const el=document.getElementById('result');
  el.innerHTML=html;el.className='show '+(cssClass||'');
  el.scrollIntoView({behavior:'smooth',block:'nearest'});
}

function hideResult(){document.getElementById('result').className='';document.getElementById('result').innerHTML='';}
function U(id){return document.getElementById(id).value;}

// ── QR / Barcode Scanner ──
let scanTargetId=null;let html5Qr=null;
function openScanner(inputId){
  scanTargetId=inputId;
  const ov=document.getElementById('scanOverlay');
  ov.style.display='flex';
  document.getElementById('scanStatus').textContent='Starting camera...';
  setTimeout(()=>{
    try{
      if(!html5Qr) html5Qr=new Html5Qrcode('scanReader');
      html5Qr.start({facingMode:'environment'},{fps:10,qrbox:{width:250,height:250}},
        r=>{
          document.getElementById(scanTargetId).value=r;
          document.getElementById(scanTargetId).dispatchEvent(new Event('input'));
          closeScanner();
        },
        ()=>{}
      ).catch(err=>{
        document.getElementById('scanStatus').textContent='Camera error: '+(err.message||'Unable to access camera. Ensure camera permissions are granted.');
      });
    }catch(e){
      document.getElementById('scanStatus').textContent='Error: '+(e.message||'Camera not available');
    }
  },300);
}
function closeScanner(){
  try{if(html5Qr){html5Qr.stop().catch(()=>{});html5Qr=null;}}catch(e){}
  document.getElementById('scanOverlay').style.display='none';
  document.getElementById('scanStatus').textContent='';
}

// ── Imaging ──
const IMG_FIELDS={
  'CT Scan':['findings:Findings:text','impression:Impression:text'],
  'MRI':['findings:Findings:text','impression:Impression:text'],
  'X-Ray':['findings:Findings:text','impression:Impression:text'],
  'Ultrasound':['measurements:Measurements:text','findings:Findings:text'],
  'Lab Photo':['test_name:Test Name:text','result:Result:text'],
  'Other':['details:Details:text']
};
function toggleImgFields(){
  const type=document.getElementById('imgType').value;
  const container=document.getElementById('imgStructuredFields');
  const fields=IMG_FIELDS[type]||[];
  container.innerHTML=fields.map(f=>{
    const [id,label]=f.split(':');
    return '<label>'+label+'</label><input id="img_'+id+'" placeholder="Enter '+label.toLowerCase()+'">';
  }).join('');
  document.getElementById('btnAnalyzeImg').style.display=(type!=='Other')?'inline-block':'none';
}
async function uploadImage(){
  const pid=U('imgPid');const el=document.getElementById('imgResult');
  if(!pid){el.innerHTML='<b style="color:#ed4245">Enter Patient ID</b>';return}
  const fileInput=document.getElementById('imgFile');
  if(!fileInput.files.length){el.innerHTML='<b style="color:#ed4245">Select a file</b>';return}
  // Build description from structured fields
  const type=document.getElementById('imgType').value;
  const structured=document.getElementById('imgStructuredFields');
  const fields=IMG_FIELDS[type]||[];
  const parts=fields.map(f=>{
    const id=f.split(':')[0];
    const val=document.getElementById('img_'+id)?.value?.trim();
    return val?id+': '+val:null;
  }).filter(Boolean);
  const descInput=document.getElementById('imgDesc');
  if(parts.length) descInput.value=parts.join(' | ');
  const fd=new FormData();
  fd.append('patient_id',pid);
  fd.append('image_type',type);
  fd.append('description',descInput.value);
  fd.append('notes',U('imgNotes'));
  fd.append('file',fileInput.files[0]);
  try{
    const r=await fetch('/api/imaging/upload',{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd});
    if(!r.ok) throw new Error((await r.json()).detail||'Upload failed');
    el.innerHTML='<b>✓ Image uploaded</b>';
    document.getElementById('imgFile').value='';
    document.getElementById('imgDesc').value='';
    document.getElementById('imgNotes').value='';
    toggleImgFields();
    loadImages();
  }catch(e){el.innerHTML='<b style="color:#ed4245">✗ '+e.message+'</b>';}
}
async function analyzeImage(){
  const fileInput=document.getElementById('imgFile');
  if(!fileInput.files.length){alert('Select an image file first');return}
  const btn=document.getElementById('btnAnalyzeImg');
  btn.textContent='🤖 Analyzing...';btn.disabled=true;
  const fd=new FormData();
  fd.append('file',fileInput.files[0]);
  fd.append('image_type',document.getElementById('imgType').value);
  try{
    const j=await (await fetch('/api/imaging/analyze',{method:'POST',headers:{'Authorization':'Bearer '+TOKEN},body:fd})).json();
    if(j.error){alert(j.error);return}
    // Fill structured fields
    const type=document.getElementById('imgType').value;
    const fields=IMG_FIELDS[type]||[];
    fields.forEach(f=>{
      const id=f.split(':')[0];
      const el=document.getElementById('img_'+id);
      if(el && j[id]) el.value=j[id];
    });
    // Build and set description
    const parts=fields.map(f=>{
      const id=f.split(':')[0];
      const val=document.getElementById('img_'+id)?.value?.trim();
      return val?id+': '+val:null;
    }).filter(Boolean);
    document.getElementById('imgDesc').value=parts.join(' | ')||j.description||'';
  }catch(e){alert('AI analysis failed: '+(e.message||'Check internet connection'));}
  btn.textContent='🤖 AI Analyze';btn.disabled=false;
}
async function loadImages(){
  const pid=U('imgGalPid');const el=document.getElementById('imgGallery');
  if(!pid){el.innerHTML='<i style="color:#555">Enter Patient ID</i>';return}
  try{
    const j=await api('/api/patients/'+pid+'/imaging');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No images</i>';return}
    el.innerHTML='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px">'+
      j.map(img=>'<div style="background:#0f0f1a;border-radius:8px;overflow:hidden;border:1px solid #2a2a4a;cursor:pointer" onclick="window.open(\''+img.file_path+'\')">'+
        '<img src="'+img.file_path+'" style="width:100%;height:100px;object-fit:cover" loading="lazy" onerror="this.style.display=\'none\'">'+
        '<div style="padding:4px 6px;font-size:.7rem">'+
        '<b style="color:#7c6ff0;font-size:.65rem">'+(img.image_type||'')+'</b>'+
        (img.description?'<br><span style="color:#ccc">'+img.description+'</span>':'')+
        '<br><span style="color:#555;font-size:.6rem">'+(img.created_at||'').slice(0,10)+'</span>'+
        '</div></div>').join('')+'</div>';
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// ── Follow-ups ──
async function scheduleFollowUp(){
  const pid=U('fuPid');const el=document.getElementById('fuResult');
  if(!pid){el.innerHTML='<b style="color:#ed4245">Enter Patient ID</b>';return}
  const date=U('fuDate');
  if(!date){el.innerHTML='<b style="color:#ed4245">Select a date</b>';return}
  try{
    const j=await api('/api/follow-ups','POST',{patient_id:pid,follow_up_date:date,type:U('fuType'),notes:U('fuNotes')||null});
    el.innerHTML='<b>✓ Follow-up scheduled for '+date+'</b>';
    document.getElementById('fuDate').value='';
    document.getElementById('fuNotes').value='';
    loadPendingFollowUps();
  }catch(e){el.innerHTML='<b style="color:#ed4245">✗ '+e.message+'</b>';}
}

async function loadPendingFollowUps(){
  const el=document.getElementById('pendingFuList');
  try{
    const j=await api('/api/follow-ups/pending?limit=20');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No pending follow-ups</i>';return}
    el.innerHTML='<div style="max-height:300px;overflow-y:auto">'+
      j.map(f=>'<div class="recent-item"><b>'+(f.follow_up_date||'').slice(0,10)+'</b>'+
        ' <span style="color:#7c6ff0">'+(f.patient_id||'')+'</span>'+
        (f.patient_name?' - '+f.patient_name:'')+
        ' | '+(f.type||'routine')+
        ' <button class="btn btn-success btn-xs" onclick="completeFu('+f.id+')">✓</button>'+
        (f.notes?'<br><span style="color:#666;font-size:.7rem">'+f.notes+'</span>':'')+
        '</div>').join('')+'</div>';
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

async function completeFu(id){
  try{
    await api('/api/follow-ups/'+id,'PUT',{status:'completed'});
    loadPendingFollowUps();
  }catch(e){}
}

// ── Timeline ──
const TL_ICONS={visit:'📋',assessment:'🔬',ultrasound:'🫀',lab:'🧪',delivery:'👶',follow_up:'📅',admission:'🏥'};
const TL_COLORS={visit:'#3ba55c',assessment:'#7c6ff0',ultrasound:'#5865f2',lab:'#faa61a',delivery:'#ed4245',follow_up:'#3ba55c',admission:'#5865f2'};

async function loadTimeline(){
  const pid=U('tlPid');const el=document.getElementById('timelineContent');
  if(!pid){el.innerHTML='<i style="color:#ed4245">Enter Patient ID</i>';return}
  el.innerHTML='<i class="loading">Loading timeline...</i>';
  try{
    const j=await api('/api/patients/'+pid+'/timeline');
    if(!j||!j.length){el.innerHTML='<i style="color:#555">No events found for this patient</i>';return}
    el.innerHTML='<div style="position:relative;padding-left:20px">'+
      '<div style="position:absolute;left:8px;top:0;bottom:0;width:2px;background:#2a2a4a"></div>'+
      j.map(e=>{
        const icon=TL_ICONS[e.ev_type]||'📌';
        const color=TL_COLORS[e.ev_type]||'#888';
        const date=(e.ev_date||'').slice(0,10);
        return '<div style="position:relative;padding:0 0 1rem 20px">'+
          '<div style="position:absolute;left:-16px;top:2px;width:18px;height:18px;border-radius:50%;background:'+color+';display:flex;align-items:center;justify-content:center;font-size:10px;border:2px solid #0a0a16">'+icon+'</div>'+
          '<div style="background:#16162a;border-radius:8px;padding:.6rem .8rem;border:1px solid #2a2a4a">'+
          '<div style="display:flex;justify-content:space-between;align-items:center">'+
          '<b style="color:#7c6ff0;font-size:.8rem">'+(e.title||'')+'</b>'+
          '<span style="color:#555;font-size:.7rem">'+date+'</span></div>'+
          (e.description?'<div style="color:#ccc;font-size:.75rem;margin-top:.2rem">'+(e.description||'')+'</div>':'')+
          '</div></div>';
      }).join('')+'</div>';
  }catch(e){el.innerHTML='<i style="color:#ed4245">'+e.message+'</i>';}
}

// Load pending follow-ups on switch to follow-up tab
</script>
<div id="scanOverlay" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.85);z-index:9999;flex-direction:column;align-items:center;justify-content:center">
  <div style="background:#16162a;border-radius:12px;padding:1.5rem;max-width:400px;width:90%;border:1px solid #2a2a4a">
    <h3 style="color:#7c6ff0;margin-bottom:.5rem">Scan QR / Barcode</h3>
    <div id="scanReader" style="width:100%;min-height:250px"></div>
    <div id="scanStatus" style="color:#ed4245;font-size:.8rem;margin:.5rem 0"></div>
    <div class="row"><button class="btn btn-danger" onclick="closeScanner()">Cancel</button></div>
  </div>
</div>
<footer style="text-align:center;padding:1rem;font-size:.65rem;color:#333;border-top:1px solid #1e1e3a;margin-top:2rem" id="footerBranding">
  Private Clinic MS · created by Karim Abdelaziz &mdash; 00201029927276
</footer>
</body>
</html>"""




# ── Facility endpoints ──
@app.post("/api/facilities")
async def create_facility(body: dict, token: dict = Depends(verify_token)):
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    ok = add_facility(body.get("code"), body.get("name"), body.get("type","clinic"),
                      body.get("address"), body.get("phone"), body.get("governorate"))
    if not ok:
        raise HTTPException(400, "Facility code already exists")
    return {"status": "success", "facility_code": body.get("code")}

@app.get("/api/facilities")
async def list_facilities():
    return get_all_facilities()

@app.get("/api/facilities/{code}")
async def get_one_facility(code: str):
    f = get_facility(code)
    if not f:
        raise HTTPException(404, "Facility not found")
    return f

@app.get("/api/facilities/{code}/branding")
async def get_facility_branding(code: str):
    f = get_facility(code)
    if not f:
        raise HTTPException(404, "Facility not found")
    return {
        "branding_name": f.get("branding_name") or f.get("name", ""),
        "support_phone": f.get("support_phone") or f.get("phone", ""),
        "branding_logo_path": f.get("branding_logo_path", ""),
        "facility_name": f.get("name", ""),
        "facility_code": f["code"]
    }

@app.put("/api/facilities/{code}/branding")
async def update_facility_branding(code: str, body: dict, token: dict = Depends(verify_token)):
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    f = get_facility(code)
    if not f:
        raise HTTPException(404, "Facility not found")
    data = {}
    for k in ("branding_name", "support_phone", "branding_logo_path"):
        if k in body:
            data[k] = body[k]
    if data:
        update_facility(code, data)
    return {"status": "success", "message": "Branding updated"}

import os as _os_logo
LOGOS_DIR = _os_logo.path.join(_os_logo.path.dirname(__file__), "data", "logos")

@app.post("/api/upload-logo")
async def upload_logo(facility_code: str = Form(...), file: UploadFile = File(...), token: dict = Depends(verify_token)):
    if token.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    ext = _os_logo.path.splitext(file.filename)[1] or ".jpg"
    fname = f"{facility_code}{ext}"
    fpath = _os_logo.path.join(LOGOS_DIR, fname)
    with open(fpath, "wb") as f:
        content = await file.read()
        f.write(content)
    logo_url = f"/data/logos/{fname}"
    update_facility(facility_code, {"branding_logo_path": logo_url})
    return {"status": "success", "logo_url": logo_url}


# ── Referral endpoints ──
@app.post("/api/referrals")
async def create_referral(body: dict):
    if not body.get("patient_id") or not get_patient(body.get("patient_id")):
        raise HTTPException(404, "Patient not found")
    add_referral(body["patient_id"], body["from_facility"], body["to_facility"],
                 body.get("reason"), body.get("notes"), body.get("urgency","routine"))
    return {"status": "success", "message": "Referral created"}

@app.get("/api/referrals")
async def list_referrals(patient_id: str = None, facility_code: str = None):
    return get_referrals(patient_id, facility_code)

@app.put("/api/referrals/{ref_id}")
async def update_referral_endpoint(ref_id: int, body: dict):
    data = {k: v for k, v in body.items() if v is not None}
    if data:
        update_referral(ref_id, data)
    return {"status": "success"}


# ── ICD-10 endpoints ──
@app.get("/api/icd10/search")
async def search_icd10_codes(query: str = "", category: str = None):
    return search_icd10(query, category)

@app.post("/api/icd10/seed")
async def seed_icd10():
    seed_icd10_codes()
    return {"status": "success", "message": "ICD-10 codes seeded"}


# ── Shift Handover endpoints ──
@app.post("/api/handovers")
async def create_handover_endpoint(body: dict):
    create_handover(body["facility_code"], body["shift_date"], body["shift_type"],
                    body["handed_over_by"], int(body.get("active_patients",0)),
                    int(body.get("high_risk_patients",0)), int(body.get("deliveries_count",0)),
                    body.get("notes"))
    return {"status": "success", "message": "Handover created"}

@app.get("/api/handovers/{facility_code}")
async def list_handovers(facility_code: str, limit: int = 20):
    return get_handovers(facility_code, limit)

@app.get("/api/handovers/{facility_code}/report")
async def handover_report(facility_code: str):
    conn = get_conn()
    active = list(conn.execute(
        "SELECT a.*, p.name, p.age FROM admissions a JOIN patients p ON a.patient_id = p.patient_id WHERE p.facility_code = ? AND a.status = 'active' ORDER BY a.admission_date",
        (facility_code,)))
    deliveries = _val(conn.execute(
        "SELECT COUNT(*) FROM deliveries d JOIN patients p ON d.patient_id = p.patient_id WHERE p.facility_code = ? AND date(d.delivery_date) = date('now')",
        (facility_code,)))
    conn.close()
    return {"facility_code": facility_code, "active_patients": [dict(r) for r in active], "deliveries_today": deliveries}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    import json as _json
    try:
        f = get_facility("DEFAULT")
    except Exception:
        f = None
    fd = {"code":"DEFAULT","name":"Default"}
    if f:
        fd["branding_name"] = f.get("branding_name") or ""
        fd["support_phone"] = f.get("support_phone") or ""
        fd["name"] = f["name"]
    return DASHBOARD.replace('__FACILITY_DATA__', _json.dumps(fd))


if __name__ == "__main__":
    import re as _re
    _sopens = len(_re.findall(r'<script[^>]*>', DASHBOARD))
    _scloses = len(_re.findall(r'</script>', DASHBOARD))
    if _sopens != _scloses:
        print(f"⚠ WARNING: HTML template has {_sopens} <script> openings but {_scloses} </script> closings.")
        print("  The dashboard page will fail to load. Fix before deploying.")
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
