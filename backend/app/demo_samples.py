"""Three demo vehicles with realistic diagnostic dumps and service invoices.

The data is generated from the same aging physics as the synthetic fleet, so each car
lands in a different grade: A (careful owner), C (fast-charged in heat), D (high-mileage
fleet car with a weak module).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from app.ml.features import CHARGE_EFFICIENCY
from app.ml.simulator import true_soh
from app.specs import CITY_TEMP_C, SPECS


def _sessions(rng, n, capacity_kwh, dc_share, high_soc_share, dod, start: date):
    out = []
    for i in range(n):
        dc = rng.random() < dc_share
        soc_start = int(np.clip(rng.normal(100 - dod, 8), 5, 70))
        soc_end = 100 if rng.random() < high_soc_share else int(np.clip(rng.normal(85 if dc else 90, 4), soc_start + 15, 94))
        kwh = capacity_kwh * (soc_end - soc_start) / 100 / CHARGE_EFFICIENCY * rng.normal(1, 0.015)
        out.append({"date": (start + timedelta(days=3 * i)).isoformat(), "dc": bool(dc),
                    "soc_start": soc_start, "soc_end": soc_end, "kwh": round(float(kwh), 2)})
    return out


def _car(key, title, story, vin, model_id, city, age, km, dc, high_soc, dod, cells_extra, temp_extra, invoice, seed, price):
    rng = np.random.default_rng(seed)
    spec = SPECS[model_id]
    temp = CITY_TEMP_C[city]
    efc = km * 0.14 / spec.pack_kwh
    soh = float(true_soh(np.array([age]), np.array([efc]), np.array([1.0 if spec.chemistry == "LFP" else 0.0]),
                         np.array([temp]), np.array([dc]), np.array([high_soc]), np.array([dod]))[0])
    if cells_extra:
        soh -= 5
    capacity = spec.pack_kwh * soh / 100
    cells = list(np.round(rng.normal(3650, 3, 96)).astype(int))
    spread = 8 + 0.9 * (100 - soh)
    cells[10] = int(3650 - spread / 2 - cells_extra)
    cells[50] = int(3650 + spread / 2)
    dongle = {
        "vin": vin,
        "reader": "ELM327 BLE (mock)",
        "read_at": "2026-11-20T10:30:00+05:30",
        "odometer_km": km,
        "bms_soh_pct": round(min(soh + 1.8, 100), 1),
        "cumulative_charged_kwh": round(km * 0.14 / CHARGE_EFFICIENCY),
        "pack_temp_max_c": round(35 + (temp - 25) * 1.2 + 6 * dc + temp_extra, 1),
        "cell_voltages_mv": [int(c) for c in cells],
        "charge_sessions": _sessions(rng, 40, capacity, dc, high_soc, dod, date(2026, 7, 1)),
    }
    return {
        "key": key, "title": title, "story": story,
        "form": {"vin": vin, "model_id": model_id, "age_years": age, "odometer_km": km, "city": city,
                 "market_price_lakh": price},
        "dongle": dongle,
        "invoice": {"filename": f"service-invoice-{key}.txt", "text": invoice},
    }


SAMPLES = [
    _car("careful-owner", "Careful owner", "Charged at home, mild Bengaluru weather, rarely fast-charged.",
         "MAT612345NEX40001", "tata-nexon-ev-40", "Bengaluru", 2.5, 28000, 0.08, 0.10, 45, 0, 0,
         """AUTHORISED SERVICE INVOICE  No. BLR-2026-08841
Date: 2026-09-14   VIN: MAT612345NEX40001   Odometer: 27,400 km
Periodic maintenance - 25,000 km service ........ Rs 3,200
HV battery health check (BMS scan) - no faults ... Rs 0
Cabin air filter replacement ..................... Rs 650
Tyre rotation and alignment ...................... Rs 1,100
12V auxiliary battery test - OK .................. Rs 0
""", 1, 11.8),
    _car("fast-charged-heat", "Fast-charged in the heat", "Chennai car, mostly DC fast charging, often charged to 100%.",
         "MAL0KONA39CHN7712", "hyundai-kona-39", "Chennai", 6.0, 98000, 0.72, 0.6, 62, 0, 2,
         """SERVICE INVOICE  No. CHN/WS/2026/1193
Date: 2026-10-02   VIN: MAL0KONA39CHN7712   Odometer: 97,200 km
Periodic maintenance - 95,000 km service ......... Rs 4,800
HV battery coolant replacement ................... Rs 2,950
Software update - BMS firmware v3.1 .............. Rs 0
Brake pad replacement (front) .................... Rs 3,400
Previous visit 2024-05-11: HV battery thermal sensor fault - repaired under warranty
""", 2, 9.5),
    _car("fleet-weak-module", "High-mileage fleet car", "Ahmedabad ride-hailing car, 150,000 km, one weak module.",
         "MA1XUV400AHD5521", "mahindra-xuv400-39", "Ahmedabad", 7.0, 150000, 0.8, 0.55, 70, 45, 8,
         """FLEET SERVICE INVOICE  No. AHD-FL-55217
Date: 2026-10-28   VIN: MA1XUV400AHD5521   Odometer: 149,600 km
Periodic maintenance - 150,000 km ................ Rs 5,600
HV battery diagnostic - cell imbalance warning, module 3 below threshold ... Rs 1,500
Customer declined module replacement (quoted Rs 68,000)
Suspension bush replacement ...................... Rs 4,200
""", 3, 7.2),
]
