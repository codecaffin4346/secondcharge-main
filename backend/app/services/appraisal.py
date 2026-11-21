"""End-to-end appraisal: inputs -> features -> models -> decisions -> stored result."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.ml import predict
from app.ml.features import build_row, derive_from_dongle
from app.services import decisions, llm
from app.services.certificate import verify_url
from app.specs import CITY_TEMP_C, REFERENCE_CITY, SPECS, climate_band

log = logging.getLogger("secondcharge.appraisal")
MODEL_VERSION = "v0.1-synthetic"
TYPICAL_OWNER = {"dc_fast_share": 0.25, "avg_temp_c": CITY_TEMP_C[REFERENCE_CITY]}
TYPICAL_KM_PER_YEAR = 11000


class AppraisalError(ValueError):
    pass


def run(*, vin: str, model_id: str, age_years: float, odometer_km: int, city: str,
        market_price_lakh: float | None, dongle: dict | None,
        invoice_text: str | None, seller_contact: str | None = None) -> dict:
    spec = SPECS.get(model_id)
    if spec is None:
        raise AppraisalError(f"Unknown model '{model_id}'. Pick one from /api/vehicle-models.")
    if city not in CITY_TEMP_C:
        raise AppraisalError(f"Unknown city '{city}'. Supported: {', '.join(CITY_TEMP_C)}.")
    if age_years <= 0 or odometer_km < 0:
        raise AppraisalError("Vehicle age must be above zero and the odometer cannot be negative.")

    # Service history
    service = {"provided": bool(invoice_text and invoice_text.strip()), "method": None,
               "battery_repairs": 0, "module_replaced": False, "notes": []}
    if service["provided"]:
        fields, method = llm.extract_invoice(invoice_text)
        service.update(method=method, battery_repairs=fields.battery_repairs, module_replaced=fields.module_replaced,
                       notes=fields.battery_notes, invoice_vin=fields.vin, invoice_odometer_km=fields.odometer_km,
                       service_date=fields.service_date)

    dongle_feats = derive_from_dongle(dongle, spec.pack_kwh)
    temp = CITY_TEMP_C[city]
    row = build_row(age_years=age_years, odometer_km=float(odometer_km), pack_kwh=spec.pack_kwh,
                    chemistry=spec.chemistry, avg_temp_c=temp, dongle_features=dongle_feats,
                    battery_repairs=service["battery_repairs"], module_replaced=service["module_replaced"])

    health = predict.predict_soh(row)
    km_per_year = odometer_km / age_years
    life = predict.project(row, health["soh"], km_per_year)
    factors = predict.explain(row)
    anomaly = predict.anomaly(row)
    expected = predict.expected_soh(row, {**TYPICAL_OWNER, "odometer_km": TYPICAL_KM_PER_YEAR * age_years})
    benchmark_curve = predict.project(
        {**row, **{k: float("nan") for k in predict.SNAPSHOT_FEATURES}, **TYPICAL_OWNER,
         "high_soc_share": float("nan"), "avg_depth_of_discharge": float("nan"),
         "battery_repairs": 0.0, "module_replaced": 0.0,
         "odometer_km": TYPICAL_KM_PER_YEAR * age_years,
         "efc": TYPICAL_KM_PER_YEAR * age_years * 0.14 / spec.pack_kwh},
        expected, TYPICAL_KM_PER_YEAR)["curve"]

    g = decisions.grade(health["soh"])
    price_lakh = market_price_lakh or decisions.estimate_market_price_lakh(spec, age_years)
    val = decisions.valuation(spec, health["soh"], expected, price_lakh)
    val["market_price_source"] = "appraiser" if market_price_lakh else "depreciation estimate"
    rt = decisions.route(health["soh"], g["grade"], anomaly["flagged"])
    sources = {
        "diagnostics": dongle is not None and any(dongle.get(k) is not None for k in ("cell_voltages_mv", "bms_soh_pct")),
        "charge_sessions": bool(dongle and dongle.get("charge_sessions")),
        "service_history": service["provided"],
        "vin_decode": True,
    }
    warnings = []
    if service.get("invoice_vin") and service["invoice_vin"] != vin.upper():
        warnings.append(f"Invoice VIN {service['invoice_vin']} does not match the appraised VIN.")
    if service.get("invoice_odometer_km") and service["invoice_odometer_km"] > odometer_km:
        warnings.append("Invoice shows a higher odometer reading than entered. Check for odometer rollback.")
    if not decisions.warranty(spec, age_years, odometer_km)["active"]:
        warnings.append("Battery warranty has expired.")

    result = {
        "id": uuid.uuid4().hex[:10].upper(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": MODEL_VERSION,
        "vehicle": {"vin": vin.upper(), "model_id": spec.model_id, "make": spec.make, "model": spec.model,
                    "pack_kwh": spec.pack_kwh, "chemistry": spec.chemistry, "age_years": age_years,
                    "odometer_km": odometer_km, "city": city, "climate": climate_band(temp)},
        "inputs": {"sources": sources, "derived": {k: (None if v != v else round(v, 3)) for k, v in dongle_feats.items()},
                   "service_history": service},
        "health": health,
        "confidence": decisions.confidence(sources, health["high"] - health["low"]),
        "grade": g,
        "remaining_life": life,
        "benchmark_curve": benchmark_curve,
        "factors": factors,
        "anomaly": anomaly,
        "valuation": val,
        "warranty": decisions.warranty(spec, age_years, odometer_km),
        "route": rt,
        "co2": decisions.co2(spec, rt["code"]),
        "warnings": warnings,
        "seller_contact": seller_contact,
        "links": {"verify": verify_url("")},
    }
    result["links"]["verify"] = verify_url(result["id"])
    result["summary"], result["summary_method"] = llm.summarize(result)
    return result


def notify_automation(result: dict) -> None:
    """Fire the n8n webhook (certificate email, partner routing). Runs as a background task."""
    if not settings.n8n_webhook_url:
        return
    payload = {
        "event": "appraisal.completed",
        "id": result["id"],
        "vin": result["vehicle"]["vin"],
        "vehicle": f"{result['vehicle']['make']} {result['vehicle']['model']}",
        "soh": result["health"]["soh"],
        "grade": result["grade"]["grade"],
        "route": result["route"],
        "fair_price_inr": result["valuation"]["fair_price_inr"],
        "co2_avoided_kg": result["co2"]["avoided_kg"],
        "seller_contact": result.get("seller_contact"),
        "certificate_url": result["links"]["verify"],
        "summary": result["summary"],
    }
    try:
        httpx.post(settings.n8n_webhook_url, json=payload, timeout=10)
    except httpx.HTTPError as e:
        log.warning("n8n webhook failed: %s", e)
