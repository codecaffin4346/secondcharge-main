"""Synthetic EV fleet generator.

Pack-level trade-in data is not public, so we simulate a fleet whose degradation follows
the behaviour seen in public lab datasets (NASA PCoE, CALCE, Severson et al. 2019):
an early drop, calendar fade accelerated by heat and high state of charge, cycle fade
accelerated by fast charging and deep discharges, and a late "knee".
The ground truth here is synthetic; the pipeline is what the prototype demonstrates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.features import FEATURES
from app.specs import CITY_TEMP_C, SPECS

K_CAL = {"LFP": 1.05, "NMC": 1.55}   # % per year^0.8 at 25 °C
K_CYC = {"LFP": 0.011, "NMC": 0.018}  # % per equivalent full cycle


def true_soh(age, efc, chemistry_is_lfp, temp_c, dc_share, high_soc, dod, variation=1.0):
    """Ground-truth state of health (%) for arrays of vehicles."""
    k_cal = np.where(chemistry_is_lfp == 1, K_CAL["LFP"], K_CAL["NMC"])
    k_cyc = np.where(chemistry_is_lfp == 1, K_CYC["LFP"], K_CYC["NMC"])
    early = 2.0 * (1 - np.exp(-age / 0.5))
    temp_factor = np.exp(0.045 * (temp_c - 25.0))
    calendar = k_cal * temp_factor * (1 + 0.5 * high_soc) * np.power(age, 0.8)
    cycle = k_cyc * efc * (1 + 0.7 * dc_share) * (1 + 0.3 * (dod - 50) / 50) * np.where(temp_c > 27, 1.1, 1.0)
    fade = (calendar + cycle) * variation
    knee = np.where(fade > 22, 0.4 * np.power(np.clip(fade - 22, 0, None), 1.2), 0.0)
    return 100 - early - fade - knee


def generate_fleet(n: int = 12000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    specs = list(SPECS.values())
    cities = list(CITY_TEMP_C.items())

    spec_idx = rng.integers(0, len(specs), n)
    city_idx = rng.integers(0, len(cities), n)
    pack_kwh = np.array([specs[i].pack_kwh for i in spec_idx])
    is_lfp = np.array([1.0 if specs[i].chemistry == "LFP" else 0.0 for i in spec_idx])
    temp_c = np.array([cities[i][1] for i in city_idx]) + rng.normal(0, 0.5, n)

    age = rng.uniform(0.3, 9.5, n)
    km_per_year = np.clip(rng.lognormal(np.log(11000), 0.45, n), 3000, 40000)
    odometer = age * km_per_year
    consumption = rng.normal(0.14, 0.015, n)
    efc = odometer * consumption / pack_kwh

    dc_share = np.clip(rng.beta(1.6, 3.2, n), 0, 1)
    high_soc = np.clip(rng.beta(1.5, 3.5, n), 0, 1)
    dod = np.clip(rng.normal(55, 12, n), 20, 90)
    variation = rng.lognormal(0, 0.10, n)

    soh = true_soh(age, efc, is_lfp, temp_c, dc_share, high_soc, dod, variation)

    # Weak-module anomalies (~4%): extra fade, visible as cell imbalance and heat.
    anomaly = rng.random(n) < 0.04
    soh = soh - anomaly * rng.uniform(3, 7, n)

    # Battery repairs; module replacement restores some capacity.
    repairs = rng.poisson(0.08 + 0.02 * age)
    module_replaced = (repairs > 0) & (rng.random(n) < 0.35)
    soh = soh + module_replaced * rng.uniform(2, 5, n)
    soh = np.clip(soh + rng.normal(0, 0.8, n), 35, 100)

    cell_delta = np.clip(8 + 0.9 * (100 - soh) + rng.normal(0, 3, n) + anomaly * rng.uniform(30, 60, n), 2, None)
    pack_temp_max = 35 + (temp_c - 25) * 1.2 + 6 * dc_share + rng.normal(0, 2.5, n) + anomaly * 7

    bms_soh = np.clip(soh + rng.normal(1.5, 1.5, n), 0, 100)  # BMS readings tend to be optimistic
    capacity_soh = soh + rng.normal(0, 1.5, n)

    df = pd.DataFrame({
        "age_years": age,
        "odometer_km": odometer,
        "efc": efc,
        "pack_kwh": pack_kwh,
        "is_lfp": is_lfp,
        "avg_temp_c": temp_c,
        "dc_fast_share": dc_share,
        "high_soc_share": high_soc,
        "avg_depth_of_discharge": dod,
        "cell_delta_mv": cell_delta,
        "pack_temp_max_c": pack_temp_max,
        "battery_repairs": repairs.astype(float),
        "module_replaced": module_replaced.astype(float),
        "bms_soh": bms_soh,
        "capacity_soh": capacity_soh,
    })

    # Real appraisals have sparse data: hide inputs the way they go missing in practice.
    has_sessions = rng.random(n) < 0.6
    for col in ("dc_fast_share", "high_soc_share", "avg_depth_of_discharge", "capacity_soh"):
        df.loc[~has_sessions, col] = np.nan
    has_dongle = rng.random(n) < 0.7
    for col in ("cell_delta_mv", "pack_temp_max_c"):
        df.loc[~has_dongle, col] = np.nan
    df.loc[~(has_dongle & (rng.random(n) < 0.55)), "bms_soh"] = np.nan
    # Without a throughput counter, cycles are estimated from the odometer.
    no_counter = rng.random(n) < 0.5
    df.loc[no_counter, "efc"] = df.loc[no_counter, "odometer_km"] * 0.14 / df.loc[no_counter, "pack_kwh"]

    df["soh"] = soh
    df["anomaly"] = anomaly.astype(int)
    return df[FEATURES + ["soh", "anomaly"]]
