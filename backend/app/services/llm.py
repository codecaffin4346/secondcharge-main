"""Claude-powered helpers: invoice field extraction and a plain-language summary.

Both have deterministic fallbacks, so the prototype works offline or without an API key.
"""

from __future__ import annotations

import io
import logging
import re

import anthropic
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.config import settings
from app.fmt import inr

log = logging.getLogger("secondcharge.llm")
_disabled_reason: str | None = None if settings.use_llm else "USE_LLM=off"


class InvoiceFields(BaseModel):
    vin: str | None = Field(None, description="17-character VIN if present")
    service_date: str | None = Field(None, description="Date of the latest service, ISO format if possible")
    odometer_km: int | None = Field(None, description="Odometer reading on the latest invoice, in km")
    battery_repairs: int = Field(0, description="Number of distinct high-voltage battery repairs or battery warranty claims")
    module_replaced: bool = Field(False, description="True if a battery module or cells were replaced")
    battery_notes: list[str] = Field(default_factory=list, description="Short notes for each battery-related line item")


def _client() -> anthropic.Anthropic | None:
    global _disabled_reason
    if _disabled_reason:
        return None
    try:
        return anthropic.Anthropic(timeout=45.0, max_retries=1)
    except anthropic.AnthropicError as e:  # e.g. no credentials configured
        _disabled_reason = str(e)
        return None


def _call_failed(e: Exception) -> None:
    global _disabled_reason
    if isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        _disabled_reason = f"Claude API unavailable: {e.__class__.__name__}"
    log.warning("Claude call failed, using fallback: %s", e)


def _no_credentials(e: Exception) -> None:
    global _disabled_reason
    _disabled_reason = "No Claude API credentials configured (set ANTHROPIC_API_KEY)"
    log.info("%s; using fallbacks. (%s)", _disabled_reason, e)


def file_to_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


BATTERY_WORDS = re.compile(r"\b(battery|hv|high[- ]voltage|bms|cell|module|pack|thermal)\b", re.I)


def _regex_extract(text: str) -> InvoiceFields:
    vin = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text.upper())
    kms = [int(m.replace(",", "")) for m in re.findall(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*km", text, re.I)]
    lines = [l.strip() for l in text.splitlines() if BATTERY_WORDS.search(l)]
    repair_lines = [l for l in lines if re.search(r"replac|repair|warranty|fault|claim", l, re.I)]
    module = any(re.search(r"(module|cell)s?\b.*replac|replac.*\b(module|cell)", l, re.I) for l in lines)
    date = re.search(r"\b(20\d{2}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]20\d{2})\b", text)
    return InvoiceFields(
        vin=vin.group(1) if vin else None,
        service_date=date.group(1) if date else None,
        odometer_km=max(kms) if kms else None,
        battery_repairs=len(repair_lines),
        module_replaced=module,
        battery_notes=lines[:6],
    )


def extract_invoice(text: str) -> tuple[InvoiceFields, str]:
    """Returns the extracted fields and the method used ("claude" or "rules")."""
    client = _client()
    if client and text.strip():
        try:
            resp = client.messages.parse(
                model=settings.claude_model,
                max_tokens=4000,
                system="You extract structured data from Indian EV service invoices for a battery-health appraisal. "
                       "Count only high-voltage traction battery work as battery repairs; ignore the 12V battery, tyres and bodywork.",
                messages=[{"role": "user", "content": f"Invoice text:\n\n{text[:20000]}"}],
                output_format=InvoiceFields,
            )
            if resp.stop_reason != "refusal" and resp.parsed_output is not None:
                return resp.parsed_output, "claude"
        except anthropic.AnthropicError as e:  # API errors and timeouts
            _call_failed(e)
        except TypeError as e:  # raised by the SDK when no credentials are configured
            _no_credentials(e)
    return _regex_extract(text), "rules"


def _template_summary(r: dict) -> str:
    v = r["vehicle"]
    soh = r["health"]
    pos = [f for f in r["factors"] if f["impact"] > 0][:1]
    neg = [f for f in r["factors"] if f["impact"] < 0][:2]
    parts = [f"This {v['make']} {v['model']} battery is estimated at {soh['soh']:.0f}% health "
             f"(likely between {soh['low']:.0f}% and {soh['high']:.0f}%), grade {r['grade']['grade']}."]
    if neg:
        parts.append("The biggest drags are " + " and ".join(f"{f['label'].lower()} ({f['value']})" for f in neg) + ".")
    if pos:
        parts.append(f"{pos[0]['label']} ({pos[0]['value']}) works in its favour.")
    adj = r["valuation"]["battery_adjustment_inr"]
    parts.append(f"Compared with a typical car of the same model and age, the battery {'adds' if adj >= 0 else 'takes off'} "
                 f"about {inr(abs(adj))} on the trade-in price.")
    return " ".join(parts)


def summarize(result: dict) -> tuple[str, str]:
    """Plain-language note for the seller. Returns (text, method)."""
    client = _client()
    if client:
        facts = {
            "vehicle": result["vehicle"], "health": result["health"], "grade": result["grade"],
            "remaining_life": {k: result["remaining_life"][k] for k in ("rul_years", "rul_km", "beyond_horizon")},
            "top_factors": result["factors"], "valuation": result["valuation"], "route": result["route"]["title"],
            "anomaly": result["anomaly"], "confidence": result["confidence"],
        }
        try:
            resp = client.messages.create(
                model=settings.claude_model,
                max_tokens=1000,
                output_config={"effort": "low"},
                system="You write short, plain-language battery health notes for people trading in an electric car in India. "
                       "Use 3 to 4 sentences, no headings or lists, rupees with Indian digit grouping. "
                       "Explain the health estimate and its range, the main reasons, and what it means for the price. "
                       "Use only the numbers given; do not invent figures.",
                messages=[{"role": "user", "content": f"Appraisal data (JSON): {facts}"}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if resp.stop_reason != "refusal" and text:
                return text, "claude"
        except anthropic.AnthropicError as e:  # API errors and timeouts
            _call_failed(e)
        except TypeError as e:  # raised by the SDK when no credentials are configured
            _no_credentials(e)
    return _template_summary(result), "template"


def status() -> dict:
    return {"model": settings.claude_model, "enabled": _disabled_reason is None, "reason": _disabled_reason}
