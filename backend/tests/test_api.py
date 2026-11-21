import json
import os

os.environ["USE_LLM"] = "off"
os.environ["DATA_DIR"] = os.path.join(os.path.dirname(__file__), ".data")

import pytest
from fastapi.testclient import TestClient

from app.demo_samples import SAMPLES
from app.fmt import inr
from app.main import app
from app.ml.features import derive_from_dongle


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _appraise(client, sample):
    form = {k: str(v) for k, v in sample["form"].items()}
    form["dongle_json"] = json.dumps(sample["dongle"])
    files = {"invoice_file": (sample["invoice"]["filename"], sample["invoice"]["text"].encode(), "text/plain")}
    r = client.post("/api/appraisals", data=form, files=files)
    assert r.status_code == 200, r.text
    return r.json()


def test_samples_land_in_expected_grades(client):
    results = {s["key"]: _appraise(client, s) for s in SAMPLES}
    assert results["careful-owner"]["grade"]["grade"] == "A"
    assert results["fast-charged-heat"]["grade"]["grade"] == "C"
    assert results["fleet-weak-module"]["grade"]["grade"] == "D"
    # careful owner beats the benchmark, so the seller gets paid more
    assert results["careful-owner"]["valuation"]["battery_adjustment_inr"] > 0
    assert results["fast-charged-heat"]["valuation"]["battery_adjustment_inr"] < 0
    assert results["fleet-weak-module"]["anomaly"]["flagged"] is True
    assert results["fleet-weak-module"]["inputs"]["service_history"]["battery_repairs"] >= 1


def test_band_contains_estimate(client):
    r = _appraise(client, SAMPLES[1])
    h = r["health"]
    assert h["low"] <= h["soh"] <= h["high"]
    assert r["remaining_life"]["rul_years"] > 0


def test_history_only_appraisal_has_wider_band(client):
    s = SAMPLES[0]
    form = {k: str(v) for k, v in s["form"].items()}
    r = client.post("/api/appraisals", data=form)
    assert r.status_code == 200
    j = r.json()
    assert j["confidence"] in {"medium", "low"}
    assert j["inputs"]["sources"]["diagnostics"] is False


def test_certificate_and_passport(client):
    r = _appraise(client, SAMPLES[0])
    pdf = client.get(f"/api/appraisals/{r['id']}/certificate.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    pp = client.get(f"/api/appraisals/{r['id']}/passport.json").json()
    assert pp["state_of_health"]["value_pct"] == r["health"]["soh"]


def test_rejects_bad_input(client):
    form = {k: str(v) for k, v in SAMPLES[0]["form"].items()}
    assert client.post("/api/appraisals", data={**form, "model_id": "unknown"}).status_code == 422
    assert client.post("/api/appraisals", data={**form, "dongle_json": "{not json"}).status_code == 422
    assert client.get("/api/appraisals/NOPE").status_code == 404


def test_capacity_from_charge_sessions():
    sessions = [{"soc_start": 20, "soc_end": 80, "kwh": 0.6 * 36 / 0.92, "dc": i % 2 == 0} for i in range(5)]
    f = derive_from_dongle({"charge_sessions": sessions, "cell_voltages_mv": [3600, 3640]}, pack_kwh=40)
    assert abs(f["capacity_soh"] - 90) < 0.01
    assert f["dc_fast_share"] == pytest.approx(0.6)
    assert f["cell_delta_mv"] == 40


def test_indian_rupee_grouping():
    assert inr(1234567) == "₹12,34,567"
    assert inr(-207000) == "-₹2,07,000"
    assert inr(950) == "₹950"
