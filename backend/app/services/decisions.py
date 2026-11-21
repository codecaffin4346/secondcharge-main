"""Business rules: grade, fair price, next-life route and CO2 impact.

Kept separate from the ML so the rules are easy to audit and change.
"""

from __future__ import annotations

from app.config import settings
from app.specs import VehicleSpec

USABLE_POINTS = 30.0  # 100% -> 70%: the span of a pack's first life


def grade(soh: float) -> dict:
    if soh >= 85:
        return {"grade": "A", "label": "Like new"}
    if soh >= 75:
        return {"grade": "B", "label": "Normal wear"}
    if soh >= 65:
        return {"grade": "C", "label": "Noticeable fade"}
    return {"grade": "D", "label": "End of first life"}


def estimate_market_price_lakh(spec: VehicleSpec, age_years: float) -> float:
    """Simple depreciation curve used when the appraiser gives no market price."""
    value = spec.new_price_lakh * 0.82  # first-year drop
    value *= 0.88 ** max(age_years - 1, 0)
    return round(value, 2)


def valuation(spec: VehicleSpec, soh: float, expected: float, market_price_lakh: float) -> dict:
    replacement = spec.pack_kwh * settings.pack_cost_inr_per_kwh
    per_point = replacement / USABLE_POINTS
    delta = soh - expected
    adjustment = delta * per_point
    market = market_price_lakh * 100_000
    fair = max(market + adjustment, 0)
    return {
        "market_price_inr": round(market),
        "expected_soh": expected,
        "delta_points": round(delta, 1),
        "pack_replacement_inr": round(replacement),
        "value_per_point_inr": round(per_point),
        "battery_adjustment_inr": round(adjustment, -2),
        "fair_price_inr": round(fair, -2),
        "assumptions": f"Pack cost ₹{settings.pack_cost_inr_per_kwh:,.0f}/kWh; {USABLE_POINTS:.0f} points of usable first life (100% → 70%).",
    }


def warranty(spec: VehicleSpec, age_years: float, odometer_km: float) -> dict:
    years_left = max(spec.warranty_years - age_years, 0)
    km_left = max(spec.warranty_km - odometer_km, 0)
    active = years_left > 0 and km_left > 0
    return {
        "active": active,
        "years_left": round(years_left, 1) if active else 0,
        "km_left": int(km_left) if active else 0,
        "terms": f"{spec.warranty_years} years / {spec.warranty_km:,} km",
    }


def route(soh: float, grade_letter: str, anomaly_flagged: bool) -> dict:
    if grade_letter == "A":
        r = ("certified_resale", "Certified resale", "List as a certified used EV with the Grade A certificate.")
    elif grade_letter == "B":
        r = ("resale", "Resale at fair price", "List with the certificate attached; battery warranty transfers to the buyer.")
    elif grade_letter == "C":
        r = ("resale_or_second_life", "Discounted resale or second-life storage",
             "Offer as a discounted city car, and send the pack details to second-life storage partners in parallel.")
    elif soh >= 50:
        r = ("second_life_storage", "Second-life energy storage",
             "Send the battery passport to second-life storage partners for reuse in stationary storage.")
    else:
        r = ("recycling", "Certified recycling", "Request pickup by a registered battery recycler for material recovery.")
    out = {"code": r[0], "title": r[1], "action": r[2], "notify_partners": r[0] in {"resale_or_second_life", "second_life_storage", "recycling"}}
    if anomaly_flagged:
        out["action"] += " Inspect the flagged module before listing."
    return out


def co2(spec: VehicleSpec, route_code: str) -> dict:
    kept_in_use = route_code != "recycling"
    avoided = spec.pack_kwh * settings.co2_kg_per_kwh if kept_in_use else 0.0
    return {
        "kept_in_use": kept_in_use,
        "avoided_kg": round(avoided),
        "basis": f"{settings.co2_kg_per_kwh:.0f} kg CO2e per kWh of new pack manufacturing avoided (assumption; published estimates vary).",
    }


def confidence(sources: dict, band_width: float) -> str:
    if (sources.get("diagnostics") and sources.get("charge_sessions")) or band_width <= 3.5:
        return "high"
    if sources.get("diagnostics") or sources.get("charge_sessions") or band_width <= 5:
        return "medium"
    return "low"
