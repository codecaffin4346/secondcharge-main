"""SecondCharge API."""

from __future__ import annotations

import json
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import settings
from app.ml import predict
from app.services import appraisal, certificate, llm, store
from app.specs import CITY_TEMP_C, SPECS, decode_vin

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    predict._bundle()  # load (or train on first run) before the first request
    if settings.seed_demo and not store.list_all(1):
        threading.Thread(target=_seed_demo, daemon=True).start()
    yield


def _seed_demo() -> None:
    """Hosted demos start with an empty disk; add the three demo cars so the dashboard isn't blank."""
    from app.demo_samples import SAMPLES
    for s in SAMPLES:
        try:
            r = appraisal.run(**s["form"], dongle=s["dongle"], invoice_text=s["invoice"]["text"], seller_contact=None)
            store.save(r)
        except Exception:  # seeding is best-effort and must never stop the API
            logging.exception("Demo seeding failed for %s", s["key"])


app = FastAPI(title="SecondCharge API", version="0.1.0", lifespan=lifespan,
              description="EV trade-in battery health estimator: SoH, remaining life, fair price, next-life routing.")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])

MAX_UPLOAD = 5 * 1024 * 1024


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model_metrics": predict.metrics(), "llm": llm.status(),
            "automation": {"n8n_webhook": bool(settings.n8n_webhook_url)}}


@app.get("/api/vehicle-models")
def vehicle_models() -> dict:
    return {
        "models": [{"model_id": s.model_id, "make": s.make, "model": s.model, "pack_kwh": s.pack_kwh,
                    "chemistry": s.chemistry, "wmi": s.wmi} for s in SPECS.values()],
        "cities": list(CITY_TEMP_C),
    }


@app.get("/api/vin/{vin}")
def vin_lookup(vin: str) -> dict:
    return {"vin": vin.upper(), "candidates": [s.model_id for s in decode_vin(vin)]}


@app.post("/api/appraisals")
async def create_appraisal(
    background: BackgroundTasks,
    vin: str = Form(..., min_length=11, max_length=17),
    model_id: str = Form(...),
    age_years: float = Form(..., gt=0, le=20),
    odometer_km: int = Form(..., ge=0, le=1_000_000),
    city: str = Form(...),
    market_price_lakh: float | None = Form(None, gt=0, le=200),
    seller_contact: str | None = Form(None, max_length=200),
    dongle_json: str | None = Form(None),
    dongle_file: UploadFile | None = File(None),
    invoice_file: UploadFile | None = File(None),
) -> dict:
    dongle = None
    raw = dongle_json
    if dongle_file is not None and dongle_file.filename:
        raw = (await dongle_file.read(MAX_UPLOAD)).decode("utf-8", errors="replace")
    if raw and raw.strip():
        try:
            dongle = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(422, f"Diagnostic data is not valid JSON: {e.msg} (line {e.lineno}).")
        if not isinstance(dongle, dict):
            raise HTTPException(422, "Diagnostic data must be a JSON object.")

    invoice_text = None
    if invoice_file is not None and invoice_file.filename:
        data = await invoice_file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "Invoice file is larger than 5 MB.")
        try:
            invoice_text = llm.file_to_text(invoice_file.filename, data)
        except Exception as e:  # pypdf raises several error types for damaged files
            raise HTTPException(422, f"Could not read the invoice file: {e}")

    try:
        result = appraisal.run(vin=vin, model_id=model_id, age_years=age_years, odometer_km=odometer_km, city=city,
                               market_price_lakh=market_price_lakh, dongle=dongle, invoice_text=invoice_text,
                               seller_contact=seller_contact)
    except appraisal.AppraisalError as e:
        raise HTTPException(422, str(e))
    store.save(result)
    background.add_task(appraisal.notify_automation, result)
    return result


@app.get("/api/appraisals")
def list_appraisals() -> dict:
    items = store.list_all()
    return {"items": [_brief(r) for r in items]}


@app.get("/api/appraisals/{appraisal_id}")
def get_appraisal(appraisal_id: str) -> dict:
    r = store.get(appraisal_id)
    if not r:
        raise HTTPException(404, "Appraisal not found.")
    return r


@app.get("/api/appraisals/{appraisal_id}/certificate.pdf")
def get_certificate(appraisal_id: str) -> Response:
    r = store.get(appraisal_id)
    if not r:
        raise HTTPException(404, "Appraisal not found.")
    return Response(certificate.render_pdf(r), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="SecondCharge-{appraisal_id}.pdf"'})


@app.get("/api/appraisals/{appraisal_id}/passport.json")
def get_passport(appraisal_id: str) -> dict:
    r = store.get(appraisal_id)
    if not r:
        raise HTTPException(404, "Appraisal not found.")
    return certificate.passport(r)


@app.get("/api/dashboard")
def dashboard() -> dict:
    items = store.list_all(1000)
    grades = {g: 0 for g in "ABCD"}
    routes: dict[str, int] = {}
    for r in items:
        grades[r["grade"]["grade"]] += 1
        routes[r["route"]["title"]] = routes.get(r["route"]["title"], 0) + 1
    n = len(items)
    return {
        "appraisals": n,
        "co2_avoided_kg": sum(r["co2"]["avoided_kg"] for r in items),
        "avg_soh": round(sum(r["health"]["soh"] for r in items) / n, 1) if n else None,
        "seller_uplift_inr": sum(max(r["valuation"]["battery_adjustment_inr"], 0) for r in items),
        "flagged": sum(1 for r in items if r["anomaly"]["flagged"]),
        "grades": grades,
        "routes": routes,
        "recent": [_brief(r) for r in items[:20]],
    }


def _brief(r: dict) -> dict:
    return {
        "id": r["id"], "created_at": r["created_at"], "vin": r["vehicle"]["vin"],
        "vehicle": f"{r['vehicle']['make']} {r['vehicle']['model']}", "soh": r["health"]["soh"],
        "grade": r["grade"]["grade"], "route": r["route"]["title"],
        "fair_price_inr": r["valuation"]["fair_price_inr"], "adjustment_inr": r["valuation"]["battery_adjustment_inr"],
        "co2_avoided_kg": r["co2"]["avoided_kg"], "flagged": r["anomaly"]["flagged"],
    }


@app.get("/api/samples")
def samples() -> dict:
    from app.demo_samples import SAMPLES
    return {"samples": SAMPLES}
