import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", BACKEND_DIR / "data")))
    public_web_url: str = os.getenv("PUBLIC_WEB_URL") or "http://localhost:3000"
    n8n_webhook_url: str = os.getenv("N8N_WEBHOOK_URL", "")
    cors_origins: tuple[str, ...] = tuple((os.getenv("CORS_ORIGINS") or "http://localhost:3000").split(","))
    claude_model: str = os.getenv("CLAUDE_MODEL") or "claude-opus-5-5"
    use_llm: bool = os.getenv("USE_LLM", "auto") != "off"
    pack_cost_inr_per_kwh: float = float(os.getenv("PACK_COST_INR_PER_KWH", "12000"))
    seed_demo: bool = os.getenv("SEED_DEMO", "0") == "1"
    co2_kg_per_kwh: float = float(os.getenv("CO2_KG_PER_KWH", "75"))


settings = Settings()
