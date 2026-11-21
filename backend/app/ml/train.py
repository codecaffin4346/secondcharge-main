"""Train the SoH quantile models and the anomaly detector on the synthetic fleet.

Run:  python -m app.ml.train
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split

from app.ml.features import FEATURES, MONOTONE
from app.ml.simulator import generate_fleet

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
QUANTILES = {"low": 0.1, "median": 0.5, "high": 0.9}
ANOMALY_FEATURES = ["cell_delta_mv", "pack_temp_max_c", "age_years"]


def train(n: int = 12000, seed: int = 7) -> dict:
    df = generate_fleet(n=n, seed=seed)
    X, y = df[FEATURES], df["soh"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=seed)
    X_tr, X_cal, y_tr, y_cal = train_test_split(X_tr, y_tr, test_size=0.2, random_state=seed)

    constraints = tuple(MONOTONE.get(f, 0) for f in FEATURES)
    models = {}
    preds = {}
    for name, q in QUANTILES.items():
        m = xgb.XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=q,
            n_estimators=600, learning_rate=0.05, max_depth=5,
            subsample=0.9, colsample_bytree=0.9, monotone_constraints=constraints,
            random_state=seed,
        )
        m.fit(X_tr, y_tr)
        models[name] = m
        preds[name] = m.predict(X_te)

    # Conformal calibration: widen the band until it covers 80% of a held-out calibration set.
    cal_low, cal_high = models["low"].predict(X_cal), models["high"].predict(X_cal)
    scores = np.maximum(cal_low - y_cal.to_numpy(), y_cal.to_numpy() - cal_high)
    level = min(1.0, 0.8 * (1 + 1 / len(scores)))
    margin = float(np.quantile(scores, level))
    preds["low"] = preds["low"] - margin
    preds["high"] = preds["high"] + margin

    err = np.abs(preds["median"] - y_te.to_numpy())
    mae = float(err.mean())
    with_data = X_te["capacity_soh"].notna().to_numpy() | X_te["bms_soh"].notna().to_numpy()
    mae_with = float(err[with_data].mean())
    mae_history = float(err[~with_data].mean())
    coverage = float(np.mean((y_te >= preds["low"]) & (y_te <= preds["high"])))
    width = float(np.mean(preds["high"] - preds["low"]))

    # Anomaly detector trained on vehicles with dongle data.
    dongle_rows = df.dropna(subset=["cell_delta_mv", "pack_temp_max_c"])
    iso = IsolationForest(n_estimators=300, contamination=0.05, random_state=seed)
    iso.fit(dongle_rows[ANOMALY_FEATURES])
    flagged = iso.predict(dongle_rows[ANOMALY_FEATURES]) == -1
    true_anom = dongle_rows["anomaly"].to_numpy() == 1
    recall = float(flagged[true_anom].mean()) if true_anom.any() else 0.0
    precision = float(true_anom[flagged].mean()) if flagged.any() else 0.0

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models": models, "iso": iso, "band_margin": margin, "features": FEATURES, "anomaly_features": ANOMALY_FEATURES},
                MODEL_DIR / "soh_models.joblib")
    metrics = {
        "training_vehicles": len(X_tr),
        "test_vehicles": len(X_te),
        "soh_mae_points": round(mae, 2),
        "soh_mae_with_diagnostics": round(mae_with, 2),
        "soh_mae_history_only": round(mae_history, 2),
        "band_80pct_coverage": round(coverage, 3),
        "avg_band_width_points": round(width, 2),
        "anomaly_recall": round(recall, 3),
        "anomaly_precision": round(precision, 3),
    }
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
