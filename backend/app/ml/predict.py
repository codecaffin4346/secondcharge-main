"""Inference: SoH with a calibrated band, SHAP factors, remaining-life projection, anomaly check."""

from __future__ import annotations

import json
import math
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import shap

from app.ml.features import CONSUMPTION_KWH_PER_KM, FEATURE_LABELS, FEATURES
from app.ml.train import MODEL_DIR

END_OF_FIRST_LIFE = 70.0
MAX_TRAINED_AGE = 10.0  # the synthetic fleet covers cars up to ~9.5 years; don't extrapolate further
# Inputs that only describe the pack today; they are unknown for future projections.
SNAPSHOT_FEATURES = ["bms_soh", "capacity_soh", "cell_delta_mv", "pack_temp_max_c"]


@lru_cache(maxsize=1)
def _bundle():
    path = MODEL_DIR / "soh_models.joblib"
    if not path.exists():
        from app.ml.train import train
        train()
    b = joblib.load(path)
    b["explainer"] = shap.TreeExplainer(b["models"]["median"])
    return b


def metrics() -> dict:
    p = MODEL_DIR / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=FEATURES).astype(float)


def predict_soh(row: dict) -> dict:
    b = _bundle()
    X = _frame([row])
    med = float(b["models"]["median"].predict(X)[0])
    low = float(b["models"]["low"].predict(X)[0]) - b["band_margin"]
    high = float(b["models"]["high"].predict(X)[0]) + b["band_margin"]
    low, high = min(low, med), max(high, med)
    return {"soh": round(min(med, 100.0), 1), "low": round(max(low, 0.0), 1), "high": round(min(high, 100.0), 1)}


def explain(row: dict, top: int = 6) -> list[dict]:
    """SHAP contributions in SoH points, largest first. Unknown inputs are skipped."""
    b = _bundle()
    X = _frame([row])
    values = b["explainer"].shap_values(X)[0]
    factors = []
    for name, v in zip(FEATURES, values):
        raw = row.get(name)
        if raw is None or (isinstance(raw, float) and math.isnan(raw)) or abs(v) < 0.05:
            continue
        factors.append({"feature": name, "label": FEATURE_LABELS[name], "value": _fmt(name, raw), "impact": round(float(v), 2)})
    factors.sort(key=lambda f: abs(f["impact"]), reverse=True)
    return factors[:top]


def _fmt(name: str, v: float) -> str:
    if name in ("dc_fast_share", "high_soc_share"):
        return f"{v * 100:.0f}% of sessions"
    if name == "age_years":
        return f"{v:.1f} years"
    if name == "odometer_km":
        return f"{v:,.0f} km"
    if name == "efc":
        return f"{v:.0f} cycles"
    if name == "avg_temp_c":
        return f"{v:.1f} °C average"
    if name in ("bms_soh", "capacity_soh"):
        return f"{v:.1f}%"
    if name == "cell_delta_mv":
        return f"{v:.0f} mV spread"
    if name == "pack_temp_max_c":
        return f"{v:.0f} °C peak"
    if name == "avg_depth_of_discharge":
        return f"{v:.0f}% average"
    if name == "is_lfp":
        return "LFP" if v >= 0.5 else "NMC"
    if name == "pack_kwh":
        return f"{v:.1f} kWh"
    if name in ("module_replaced",):
        return "yes" if v >= 0.5 else "no"
    return f"{v:g}"


def project(row: dict, current_soh: float, km_per_year: float, horizon_years: float = 12.0, step: float = 0.25) -> dict:
    """Project SoH forward with the owner's habits and find when it crosses 70%.

    The model is run on future ages and odometer readings. Snapshot measurements are unknown
    in the future, so the curve is anchored to today's estimate with a constant offset.
    """
    b = _bundle()
    horizon_years = min(horizon_years, max(MAX_TRAINED_AGE - row["age_years"], 1.0))
    base = dict(row)
    for k in SNAPSHOT_FEATURES:
        base[k] = float("nan")
    efc_per_km = (row["efc"] / row["odometer_km"]) if row["odometer_km"] > 0 else CONSUMPTION_KWH_PER_KM / row["pack_kwh"]

    steps = np.arange(0, horizon_years + 1e-9, step)
    rows = []
    for dt in steps:
        r = dict(base)
        r["age_years"] = row["age_years"] + dt
        r["odometer_km"] = row["odometer_km"] + km_per_year * dt
        r["efc"] = r["odometer_km"] * efc_per_km
        rows.append(r)
    curve = b["models"]["median"].predict(_frame(rows))
    offset = current_soh - float(curve[0])
    curve = np.minimum.accumulate(curve + offset)  # health never recovers by itself

    rul_years = None
    if current_soh <= END_OF_FIRST_LIFE:
        rul_years = 0.0
    else:
        below = np.where(curve <= END_OF_FIRST_LIFE)[0]
        if len(below):
            i = below[0]
            # linear interpolation between the two steps around the crossing
            y0, y1 = curve[i - 1], curve[i]
            t0 = steps[i - 1]
            rul_years = float(t0 + step * (y0 - END_OF_FIRST_LIFE) / max(y0 - y1, 1e-6))
    points = [
        {"age": round(row["age_years"] + float(t), 2), "soh": round(float(s), 2)}
        for t, s in zip(steps[::2], curve[::2])  # one point every half year
    ]
    return {
        "rul_years": None if rul_years is None else round(rul_years, 1),
        "rul_km": None if rul_years is None else int(round(rul_years * km_per_year, -3)),
        "beyond_horizon": rul_years is None,
        "horizon_years": horizon_years,
        "curve": points,
    }


def expected_soh(row: dict, typical: dict) -> float:
    """Benchmark: what a typical owner's car of the same model and age would score."""
    b = _bundle()
    r = {k: float("nan") for k in FEATURES}
    r.update({k: row[k] for k in ("age_years", "pack_kwh", "is_lfp")})
    r.update({"battery_repairs": 0.0, "module_replaced": 0.0})  # a typical car has no battery repairs
    r.update(typical)
    r["efc"] = r["odometer_km"] * CONSUMPTION_KWH_PER_KM / r["pack_kwh"]
    return round(float(b["models"]["median"].predict(_frame([r]))[0]), 1)


def anomaly(row: dict) -> dict:
    b = _bundle()
    feats = b["anomaly_features"]
    if any(row.get(f) is None or math.isnan(row[f]) for f in feats):
        return {"checked": False, "flagged": False, "reasons": []}
    X = pd.DataFrame([[row[f] for f in feats]], columns=feats)
    flagged = bool(b["iso"].predict(X)[0] == -1)
    reasons = []
    if flagged:
        if row["cell_delta_mv"] > 45:
            reasons.append(f"Cell voltage spread of {row['cell_delta_mv']:.0f} mV suggests a weak module")
        if row["pack_temp_max_c"] > 45:
            reasons.append(f"Peak pack temperature of {row['pack_temp_max_c']:.0f} °C is unusually high")
        if not reasons:
            reasons.append("Diagnostic pattern is unusual for a pack of this age")
    return {"checked": True, "flagged": flagged, "reasons": reasons}
