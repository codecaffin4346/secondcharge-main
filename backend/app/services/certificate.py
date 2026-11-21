"""Battery Health Certificate (PDF with a verification QR code) and battery passport record."""

from __future__ import annotations

import io

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import settings
from app.fmt import inr as _inr


def inr(v: float) -> str:
    return _inr(v, symbol="Rs ")  # built-in PDF fonts have no rupee glyph

TEAL = colors.HexColor("#0D7A6B")
INK = colors.HexColor("#13211F")
MUTED = colors.HexColor("#5B6965")
TINT = colors.HexColor("#EAF3F1")
GRADE_COLORS = {"A": "#0D7A6B", "B": "#2C5D9E", "C": "#E39B2E", "D": "#C0443A"}


def verify_url(appraisal_id: str) -> str:
    base = settings.public_web_url.rstrip("/")
    if base and "://" not in base:
        base = f"https://{base}"
    return f"{base}/verify/{appraisal_id}"


def render_pdf(r: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    m = 18 * mm

    c.setFillColor(TEAL)
    c.rect(0, H - 42 * mm, W, 42 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(m, H - 20 * mm, "Battery Health Certificate")
    c.setFont("Helvetica", 11)
    c.drawString(m, H - 28 * mm, "SecondCharge  |  EV trade-in battery appraisal")
    c.drawString(m, H - 34 * mm, f"Certificate {r['id']}  |  Issued {r['created_at'][:10]}")

    v = r["vehicle"]
    y = H - 56 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(m, y, f"{v['make']} {v['model']}")
    c.setFont("Helvetica", 10)
    c.setFillColor(MUTED)
    c.drawString(m, y - 6 * mm, f"VIN {v['vin']}  |  {v['age_years']:.1f} years  |  {v['odometer_km']:,} km  |  {v['chemistry']} {v['pack_kwh']} kWh  |  {v['city']}")

    # health block
    y -= 20 * mm
    h, g = r["health"], r["grade"]
    c.setFillColor(TINT)
    c.roundRect(m, y - 34 * mm, W - 2 * m, 34 * mm, 4 * mm, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawString(m + 6 * mm, y - 8 * mm, "STATE OF HEALTH")
    c.setFont("Helvetica-Bold", 34)
    c.drawString(m + 6 * mm, y - 22 * mm, f"{h['soh']:.1f}%")
    c.setFont("Helvetica", 10)
    c.drawString(m + 6 * mm, y - 29 * mm, f"80% range {h['low']:.1f}-{h['high']:.1f}%  |  confidence {r['confidence']}")
    c.setFillColor(colors.HexColor(GRADE_COLORS[g["grade"]]))
    c.roundRect(m + 78 * mm, y - 27 * mm, 22 * mm, 20 * mm, 3 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(m + 89 * mm, y - 21 * mm, g["grade"])
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(m + 106 * mm, y - 12 * mm, g["label"])
    rl = r["remaining_life"]
    c.setFont("Helvetica", 10)
    life = ("beyond " + str(int(rl["horizon_years"])) + " years") if rl["beyond_horizon"] else f"about {rl['rul_years']} years / {rl['rul_km']:,} km"
    c.drawString(m + 106 * mm, y - 19 * mm, f"Remaining life to 70%: {life}")
    c.drawString(m + 106 * mm, y - 25 * mm, f"Next life: {r['route']['title']}")

    # valuation
    y -= 46 * mm
    val = r["valuation"]
    c.setFont("Helvetica-Bold", 12)
    c.drawString(m, y, "Fair trade-in valuation")
    rows = [
        ("Market price before battery check", inr(val["market_price_inr"])),
        (f"Expected health for this model and age", f"{val['expected_soh']:.1f}%"),
        ("Difference from expected", f"{val['delta_points']:+.1f} points"),
        ("Value per health point", inr(val["value_per_point_inr"])),
        ("Battery adjustment", ("+" if val["battery_adjustment_inr"] >= 0 else "") + inr(val["battery_adjustment_inr"])),
        ("Fair trade-in price", inr(val["fair_price_inr"])),
    ]
    c.setFont("Helvetica", 10)
    for i, (k, vv) in enumerate(rows):
        yy = y - (7 + i * 6) * mm
        if i == len(rows) - 1:
            c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(m, yy, k)
        c.drawRightString(W - m, yy, vv)

    # factors
    y -= 50 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(m, y, "What drives this score")
    c.setFont("Helvetica", 10)
    for i, f in enumerate(r["factors"][:5]):
        yy = y - (7 + i * 6) * mm
        c.setFillColor(INK)
        c.drawString(m, yy, f"{f['label']} ({f['value']})")
        c.setFillColor(TEAL if f["impact"] >= 0 else colors.HexColor("#C0443A"))
        c.drawRightString(W - m, yy, f"{f['impact']:+.1f} pts")

    # summary
    y -= 42 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(m, y, "Summary")
    text = c.beginText(m, y - 7 * mm)
    text.setFont("Helvetica", 10)
    text.setLeading(14)
    for line in _wrap(r["summary"].replace("₹", "Rs "), 100):
        text.textLine(line)
    c.drawText(text)

    # QR + footer
    qr = qrcode.make(verify_url(r["id"]))
    qbuf = io.BytesIO()
    qr.save(qbuf, format="PNG")
    qbuf.seek(0)
    c.drawImage(ImageReader(qbuf), W - m - 32 * mm, 14 * mm, 32 * mm, 32 * mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(m, 30 * mm, f"Verify this certificate: {verify_url(r['id'])}")
    c.drawString(m, 25 * mm, f"Model: SoH estimator {r['model_version']}. CO2 avoided if kept in use: {r['co2']['avoided_kg']:,} kg CO2e (assumption-based).")
    c.drawString(m, 20 * mm, "Prototype output for the Tek Qubit hackathon. Estimates are trained on a synthetic fleet.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _wrap(s: str, width: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:8]


def passport(r: dict) -> dict:
    """Battery record with fields modelled on the EU battery passport's performance and durability data."""
    v = r["vehicle"]
    return {
        "schema": "secondcharge.battery-record/0.1",
        "battery": {"chemistry": v["chemistry"], "rated_capacity_kwh": v["pack_kwh"], "vehicle_make": v["make"], "vehicle_model": v["model"], "vin": v["vin"]},
        "state_of_health": {"value_pct": r["health"]["soh"], "range_pct": [r["health"]["low"], r["health"]["high"]], "assessed_at": r["created_at"], "method": f"SecondCharge {r['model_version']}"},
        "usage": {"age_years": v["age_years"], "odometer_km": v["odometer_km"], "climate_band": v["climate"]},
        "repairs": r["inputs"]["service_history"],
        "expected_remaining_life": {k: r["remaining_life"][k] for k in ("rul_years", "rul_km", "beyond_horizon")},
        "next_life": r["route"]["code"],
        "certificate_url": verify_url(r["id"]),
    }
