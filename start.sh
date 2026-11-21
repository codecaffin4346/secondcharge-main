#!/usr/bin/env bash
# Start the SecondCharge prototype: API on :8000, web app on :3000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "Setting up the Python environment (first run)..."
  (cd "$ROOT/backend" && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt)
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Installing web app dependencies (first run)..."
  (cd "$ROOT/frontend" && npm install)
fi
if [ ! -f "$ROOT/backend/models/soh_models.joblib" ]; then
  echo "Training models on the synthetic fleet..."
  (cd "$ROOT/backend" && .venv/bin/python -m app.ml.train)
fi
(cd "$ROOT/frontend" && npm run build >/dev/null)

(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
echo "SecondCharge running at http://localhost:3000  (API docs: http://localhost:8000/docs)"
cd "$ROOT/frontend" && npx next start -p 3000
