"""Reference data: EV model specs and city climate bands.

Figures are approximate public specs used for the demo. Verify before production use.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleSpec:
    model_id: str
    make: str
    model: str
    pack_kwh: float
    chemistry: str  # "LFP" or "NMC"
    new_price_lakh: float
    wmi: str  # first 3 VIN characters used by the demo decoder
    warranty_years: int = 8
    warranty_km: int = 160_000


SPECS: dict[str, VehicleSpec] = {
    s.model_id: s
    for s in [
        VehicleSpec("tata-nexon-ev-40", "Tata", "Nexon EV (40.5 kWh)", 40.5, "LFP", 16.0, "MAT"),
        VehicleSpec("tata-nexon-ev-30", "Tata", "Nexon EV (30 kWh)", 30.2, "LFP", 13.5, "MAT"),
        VehicleSpec("tata-tiago-ev-24", "Tata", "Tiago EV (24 kWh)", 24.0, "LFP", 10.5, "MAT"),
        VehicleSpec("tata-punch-ev-35", "Tata", "Punch EV (35 kWh)", 35.0, "LFP", 14.0, "MAT"),
        VehicleSpec("mg-zs-ev-50", "MG", "ZS EV (50.3 kWh)", 50.3, "LFP", 22.0, "MZ7"),
        VehicleSpec("mg-comet-17", "MG", "Comet EV (17.3 kWh)", 17.3, "LFP", 8.0, "MZ7"),
        VehicleSpec("mahindra-xuv400-39", "Mahindra", "XUV400 (39.4 kWh)", 39.4, "NMC", 17.5, "MA1"),
        VehicleSpec("hyundai-kona-39", "Hyundai", "Kona Electric (39.2 kWh)", 39.2, "NMC", 23.8, "MAL"),
        VehicleSpec("hyundai-ioniq5-72", "Hyundai", "Ioniq 5 (72.6 kWh)", 72.6, "NMC", 46.0, "MAL"),
        VehicleSpec("byd-atto3-60", "BYD", "Atto 3 (60.5 kWh)", 60.5, "LFP", 34.0, "LGX"),
    ]
}

# Approximate annual mean temperature (°C) for battery calendar-aging stress.
CITY_TEMP_C: dict[str, float] = {
    "Bengaluru": 24.0,
    "Pune": 25.0,
    "Chandigarh": 23.5,
    "Delhi": 25.5,
    "Jaipur": 26.0,
    "Mumbai": 27.5,
    "Hyderabad": 27.0,
    "Kolkata": 27.0,
    "Ahmedabad": 27.5,
    "Chennai": 29.0,
}

REFERENCE_CITY = "Pune"


def climate_band(temp_c: float) -> str:
    if temp_c >= 27.0:
        return "hot"
    if temp_c <= 24.0:
        return "mild"
    return "moderate"


def decode_vin(vin: str) -> list[VehicleSpec]:
    """Demo VIN decoder: matches the manufacturer code (WMI) to candidate models."""
    wmi = (vin or "").strip().upper()[:3]
    return [s for s in SPECS.values() if s.wmi == wmi]
