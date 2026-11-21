"""Feature definitions shared by training and inference."""

from __future__ import annotations

import math
from statistics import median
from typing import Any

FEATURES = [
    "age_years",
    "odometer_km",
    "efc",
    "pack_kwh",
    "is_lfp",
    "avg_temp_c",
    "dc_fast_share",
    "high_soc_share",
    "avg_depth_of_discharge",
    "cell_delta_mv",
    "pack_temp_max_c",
    "battery_repairs",
    "module_replaced",
    "bms_soh",
    "capacity_soh",
]

# Monotone constraints keep projections physically sensible:
# more age, km, cycles, heat or fast charging never raises predicted health.
MONOTONE = {
    "age_years": -1,
    "odometer_km": -1,
    "efc": -1,
    "avg_temp_c": -1,
    "dc_fast_share": -1,
    "high_soc_share": -1,
    "bms_soh": 1,
    "capacity_soh": 1,
}

FEATURE_LABELS = {
    "age_years": "Vehicle age",
    "odometer_km": "Odometer",
    "efc": "Charge cycles",
    "pack_kwh": "Pack size",
    "is_lfp": "Chemistry",
    "avg_temp_c": "Climate",
    "dc_fast_share": "DC fast charging",
    "high_soc_share": "Charging to 95%+",
    "avg_depth_of_discharge": "Depth of discharge",
    "cell_delta_mv": "Cell imbalance",
    "pack_temp_max_c": "Peak pack temperature",
    "battery_repairs": "Battery repairs",
    "module_replaced": "Module replaced",
    "bms_soh": "BMS-reported health",
    "capacity_soh": "Measured capacity",
}

CHARGE_EFFICIENCY = 0.92  # share of wall energy that reaches the pack
CONSUMPTION_KWH_PER_KM = 0.14


def nan() -> float:
    return float("nan")


def derive_from_dongle(dongle: dict[str, Any] | None, pack_kwh: float) -> dict[str, float]:
    """Turn a raw OBD/BMS + charge-session dump into model features.

    Missing inputs come back as NaN so the model treats them as unknown.
    """
    out = {k: nan() for k in ("dc_fast_share", "high_soc_share", "avg_depth_of_discharge",
                              "cell_delta_mv", "pack_temp_max_c", "bms_soh", "capacity_soh", "efc")}
    if not dongle:
        return out

    cells = dongle.get("cell_voltages_mv") or []
    if len(cells) >= 2:
        out["cell_delta_mv"] = float(max(cells) - min(cells))
    if dongle.get("pack_temp_max_c") is not None:
        out["pack_temp_max_c"] = float(dongle["pack_temp_max_c"])
    if dongle.get("bms_soh_pct") is not None:
        out["bms_soh"] = float(dongle["bms_soh_pct"])
    if dongle.get("cumulative_charged_kwh"):
        out["efc"] = float(dongle["cumulative_charged_kwh"]) * CHARGE_EFFICIENCY / pack_kwh

    sessions = dongle.get("charge_sessions") or []
    if sessions:
        n = len(sessions)
        out["dc_fast_share"] = sum(1 for s in sessions if s.get("dc")) / n
        out["high_soc_share"] = sum(1 for s in sessions if s.get("soc_end", 0) >= 95) / n
        out["avg_depth_of_discharge"] = sum(100 - s.get("soc_start", 50) for s in sessions) / n
        # Capacity from clean sessions: energy into pack / fraction of SoC added.
        caps = []
        for s in sessions:
            dsoc = s.get("soc_end", 0) - s.get("soc_start", 0)
            if dsoc >= 30 and s.get("kwh"):
                caps.append(s["kwh"] * CHARGE_EFFICIENCY / (dsoc / 100))
        if len(caps) >= 3:
            out["capacity_soh"] = min(105.0, median(caps) / pack_kwh * 100)
    return out


def build_row(*, age_years: float, odometer_km: float, pack_kwh: float, chemistry: str,
              avg_temp_c: float, dongle_features: dict[str, float],
              battery_repairs: int = 0, module_replaced: bool = False) -> dict[str, float]:
    row = {k: nan() for k in FEATURES}
    row.update(dongle_features)
    row["age_years"] = age_years
    row["odometer_km"] = odometer_km
    row["pack_kwh"] = pack_kwh
    row["is_lfp"] = 1.0 if chemistry.upper() == "LFP" else 0.0
    row["avg_temp_c"] = avg_temp_c
    row["battery_repairs"] = float(battery_repairs)
    row["module_replaced"] = 1.0 if module_replaced else 0.0
    if math.isnan(row["efc"]):
        row["efc"] = odometer_km * CONSUMPTION_KWH_PER_KM / pack_kwh
    return row
