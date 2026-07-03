# Maternal-Fetal Health Monitoring System - Data Collection Layer

import os
import json
import glob
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class MaternalHealthData:
    patient_id: str
    age: int
    bmi_pre_pregnancy: float
    gestational_age: int
    blood_pressure_sys: int
    blood_pressure_dia: int
    glucose_level: float
    heart_rate: int
    temperature: float
    fetal_heart_rate: int
    fetal_movement_count: int
    uterine_contractions: int
    hemoglobin: float
    protein_urine: float
    glucose_urine: float
    previous_cesarean: bool = False
    history_diabetes: bool = False
    history_hypertension: bool = False
    history_depression: bool = False
    recorded_at: Optional[str] = None

    def __post_init__(self):
        if self.recorded_at is None:
            self.recorded_at = datetime.now().isoformat()


@dataclass
class FetalUltrasoundData:
    patient_id: str
    gestational_age: int
    image_path: str = ""
    head_circumference: float = 0.0
    abdominal_circumference: float = 0.0
    femur_length: float = 0.0
    estimated_weight: float = 0.0
    amniotic_fluid_index: float = 0.0
    placental_location: str = ""
    anomalies_detected: List[str] = None

    def __post_init__(self):
        if self.anomalies_detected is None:
            self.anomalies_detected = []


class DataCollector:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        os.makedirs(f"{base_dir}/raw", exist_ok=True)
        os.makedirs(f"{base_dir}/processed", exist_ok=True)
        os.makedirs(f"{base_dir}/ultrasound", exist_ok=True)

    def save_clinical(self, data: MaternalHealthData) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{self.base_dir}/raw/clinical_{data.patient_id}_{ts}.json"
        with open(path, 'w') as f:
            json.dump(asdict(data), f, default=str, indent=2)
        return path

    def save_ultrasound(self, data: FetalUltrasoundData) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{self.base_dir}/ultrasound/us_{data.patient_id}_{ts}.json"
        with open(path, 'w') as f:
            json.dump(asdict(data), f, default=str, indent=2)
        return path

    def get_patient_history(self, patient_id: str) -> pd.DataFrame:
        records = []
        for f in glob.glob(f"{self.base_dir}/raw/clinical_{patient_id}_*.json"):
            with open(f) as fp:
                records.append(json.load(fp))
        return pd.DataFrame(records) if records else pd.DataFrame()
