# SecondCharge: EV trade-in battery health estimator

Prototype by Team Aura++ for the Tek Qubit hackathon (Theme 4: Sustainability – Green Tech for Automotive Retail).

An appraiser enters a used EV's VIN, odometer and city, attaches the OBD-II/BMS read and a service invoice, and gets:

- **State of health** with a calibrated 80% range and a confidence level
- **Remaining life** until the pack reaches 70% (end of first life), using the owner's own usage
- **Why this score**: SHAP factors in health points, plus a plain-language summary for the seller
- **Fair trade-in price**: measured vs expected health, priced against pack replacement cost
- **Next life for the battery**: certified resale, second-life storage or recycling, with CO2e avoided
- **Weak-module check** from cell imbalance and pack temperature
- **Battery Health Certificate** PDF with a QR code to a verification page, and a battery-passport-style JSON record
- **Automation**: an n8n webhook emails the seller and alerts second-life/recycling partners
- **Dealer dashboard** with grades, routes and total CO2e avoided

## Run it

Requirements: Python via [uv](https://docs.astral.sh/uv/), Node.js 20+. On macOS, XGBoost also needs OpenMP: `brew install libomp`.

```bash
./start.sh
```

Then open http://localhost:3000 and pick one of the three demo cars. API docs are at http://localhost:8000/docs.

Manual setup:

```bash
cd backend
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m app.ml.train          # trains models, writes models/metrics.json
.venv/bin/uvicorn app.main:app --port 8000

cd ../frontend
npm install && npm run build && npx next start -p 3000
```

Tests: `cd backend && .venv/bin/python -m pytest`

## Configuration

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | backend | unset | Enables Claude for invoice reading and seller summaries. Without it, a rule-based reader and a template are used. |
| `CLAUDE_MODEL` | backend | `claude-opus-5-5` | Claude model ID |
| `USE_LLM` | backend | `auto` | `off` disables Claude calls |
| `N8N_WEBHOOK_URL` | backend | unset | n8n webhook called after each appraisal |
| `PUBLIC_WEB_URL` | backend | `http://localhost:3000` | Base URL printed in certificate QR codes |
| `PACK_COST_INR_PER_KWH` | backend | `12000` | Pack replacement cost used for pricing (assumption) |
| `CO2_KG_PER_KWH` | backend | `75` | CO2e per kWh of avoided pack manufacturing (assumption) |
| `BACKEND_URL` | frontend | `http://127.0.0.1:8000` | Where Next.js forwards `/api/*` |

## Deploy (free tiers)

**Backend on Render**
1. Render dashboard → **New → Blueprint** → choose this repo. It reads `render.yaml` and builds `backend/Dockerfile`.
2. Leave `PUBLIC_WEB_URL` blank for now; optionally add `ANTHROPIC_API_KEY`.
3. After the deploy, open `https://<your-service>.onrender.com/api/health` to check it.

**Web app on Vercel**
1. Vercel → **Add New → Project** → import this repo.
2. Set **Root Directory** to `frontend`.
3. Add the environment variable `BACKEND_URL` = your Render URL (no trailing slash), then deploy.

Finally, set `PUBLIC_WEB_URL` on Render to the Vercel URL so certificate QR codes point to the live site.

The free Render tier sleeps after about 15 minutes idle; the first request after that takes up to a minute. Open the site a few minutes before a demo. Its disk is also temporary, so stored appraisals reset on restart and the three demo cars are re-added automatically (`SEED_DEMO=1`).

## Automation (n8n)

1. Run n8n (`npx n8n` or Docker) and import `n8n/secondcharge-appraisal-workflow.json`.
2. Add SMTP credentials to the two email nodes and activate the workflow.
3. Start the backend with `N8N_WEBHOOK_URL=http://localhost:5678/webhook/secondcharge-appraisal`.

Each completed appraisal then emails the seller their certificate link, and Grade C/D batteries are offered to second-life and recycling partners automatically.

## How the model works

Pack-level trade-in data is not public, so `app/ml/simulator.py` generates a synthetic fleet of 12,000 Indian EVs whose aging follows the behaviour reported in public lab datasets (NASA PCoE, CALCE, Severson et al. 2019): an early drop, calendar fade sped up by heat and high charge levels, cycle fade sped up by DC fast charging and deep discharges, a late "knee", weak-module anomalies and realistic missing data.

- **SoH**: three XGBoost quantile models (10th/50th/90th percentile) with monotone constraints, plus conformal calibration so the 80% range really covers 80%.
- **Remaining life**: the median model is re-run at future ages and odometer readings with the owner's habits, up to age 10 (the edge of the training data).
- **Anomaly**: Isolation Forest on cell voltage spread, peak pack temperature and age.
- **Benchmark**: the same model scores a typical owner's car of the same model and age; the price adjustment is the difference.

Held-out results on the synthetic fleet are in `backend/models/metrics.json` (about 1 point mean absolute error, 0.9 with diagnostics and 1.35 from history only). These numbers show the pipeline works; real-world accuracy needs real pack data.

## Layout

```
backend/   FastAPI app, ML (app/ml), business rules and services (app/services), tests
frontend/  Next.js + Tailwind + Recharts web app
n8n/       Importable automation workflow
```
