"""Multi-Algorithm ML Benchmark & Model Trainer for AI Dispatcher.

Compares candidate algorithms for:
1. Classification Task: SLA Breach Risk Prediction (Binary Classification)
2. Regression Task: Incident Resolution Time Prediction (Hours)

Candidate Algorithms compared:
- LightGBM (LGBMClassifier / LGBMRegressor)
- XGBoost (XGBClassifier / XGBRegressor)
- CatBoost (CatBoostClassifier / CatBoostRegressor)
- Random Forest (RandomForestClassifier / RandomForestRegressor)
- Linear Baseline (LogisticRegression / Ridge)

Evaluates on test holdout set with full metrics (ROC-AUC, F1, Precision, Recall, MAE, RMSE)
and exports the top-performing models to .joblib artifacts for agent-runtime.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic dataset generator for benchmarking & demonstration
# ---------------------------------------------------------------------------
def generate_synthetic_data(n_samples: int = 5000, random_state: int = 42) -> pd.DataFrame:
    """Generate realistic synthetic ticket records mirroring Vinhomes operations."""
    np.random.seed(random_state)
    
    categories = [
        "PLUMBING", "ELECTRICAL", "ELEVATOR", "FIRE_SAFETY",
        "SANITATION", "SECURITY", "STRUCTURAL", "HVAC",
        "LANDSCAPE", "PEST_CONTROL", "PARKING", "ACCESS_CONTROL",
        "WATER_SUPPLY", "DRAINAGE", "OTHER",
    ]
    locations = [
        "APARTMENT", "LOBBY", "PARKING", "POOL",
        "GYM", "GARDEN", "ROOFTOP", "BASEMENT",
        "CORRIDOR", "STAIRWELL", "UTILITY_ROOM", "OTHER",
    ]
    
    cat_col = np.random.choice(categories, size=n_samples)
    loc_col = np.random.choice(locations, size=n_samples)
    desc_len = np.random.randint(10, 400, size=n_samples)
    num_attachments = np.random.poisson(lam=1.2, size=n_samples)
    hour_of_day = np.random.randint(0, 24, size=n_samples)
    is_weekend = np.random.binomial(n=1, p=0.28, size=n_samples)
    is_night = ((hour_of_day < 6) | (hour_of_day >= 22)).astype(int)
    staff_avail = np.random.uniform(0.1, 1.0, size=n_samples)
    current_workload = np.random.randint(0, 50, size=n_samples)
    
    # SLA risk logic (higher during night, low staff, elevators/fire safety, high workload)
    risk_score = (
        0.3 * is_night
        + 0.25 * (1.0 - staff_avail)
        + 0.2 * (current_workload / 50.0)
        + 0.15 * np.isin(cat_col, ["ELEVATOR", "FIRE_SAFETY", "ELECTRICAL"]).astype(int)
        + np.random.normal(0, 0.1, size=n_samples)
    )
    is_sla_breached = (risk_score > 0.45).astype(int)
    
    # Resolution hours logic
    base_hours = {
        "FIRE_SAFETY": 1.0, "ELEVATOR": 2.5, "ELECTRICAL": 3.0, "PLUMBING": 4.0,
        "HVAC": 5.0, "STRUCTURAL": 12.0, "SANITATION": 2.0, "SECURITY": 1.5,
    }
    cat_base = np.array([base_hours.get(c, 3.5) for c in cat_col])
    resolution_hours = np.maximum(
        0.5,
        cat_base * (1.5 - staff_avail) + (current_workload * 0.1) + np.random.exponential(scale=1.5, size=n_samples)
    )

    df = pd.DataFrame({
        "category": cat_col,
        "location_type": loc_col,
        "description_length": desc_len,
        "num_attachments": num_attachments,
        "has_image": (num_attachments > 0).astype(int),
        "hour_of_day": hour_of_day,
        "is_weekend": is_weekend,
        "is_night": is_night,
        "staff_availability": staff_avail,
        "current_workload": current_workload,
        "is_sla_breached": is_sla_breached,
        "actual_resolution_hours": resolution_hours,
    })
    return df


# ---------------------------------------------------------------------------
# Benchmark Suite
# ---------------------------------------------------------------------------
def run_benchmark(data_path: str | None = None, output_dir: str = "models") -> None:
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import (
        roc_auc_score, f1_score, precision_score, recall_score,
        mean_absolute_error, mean_squared_error, r2_score
    )
    import joblib

    # 1. Load or Generate Dataset
    if data_path and os.path.exists(data_path):
        logger.info("Loading real training data from: %s", data_path)
        df = pd.read_parquet(data_path) if data_path.endswith(".parquet") else pd.read_csv(data_path)
    else:
        logger.info("Generating synthetic benchmark dataset (5,000 samples)...")
        df = generate_synthetic_data()

    X = df.drop(columns=["is_sla_breached", "actual_resolution_hours"])
    y_cls = df["is_sla_breached"]
    y_reg = df["actual_resolution_hours"]

    # Preprocessor for tabular features
    categorical_cols = ["category", "location_type"]
    numeric_cols = [c for c in X.columns if c not in categorical_cols]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", "passthrough", numeric_cols),
        ]
    )

    # Train / Test split
    X_train, X_test, y_cls_train, y_cls_test = train_test_split(X, y_cls, test_size=0.2, random_state=42, stratify=y_cls)
    _, _, y_reg_train, y_reg_test = train_test_split(X, y_reg, test_size=0.2, random_state=42)

    logger.info("=== BENCHMARKING CLASSIFICATION (SLA Breach Risk) ===")
    
    # Candidate Classifiers
    cls_candidates: dict[str, Any] = {}
    
    # 1. Scikit-learn Logistic Regression
    from sklearn.linear_model import LogisticRegression
    cls_candidates["LogisticRegression"] = LogisticRegression(max_iter=1000)
    
    # 2. Random Forest
    from sklearn.ensemble import RandomForestClassifier
    cls_candidates["RandomForest"] = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    
    # 3. LightGBM
    try:
        import lightgbm as lgb
        cls_candidates["LightGBM"] = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.05, max_depth=6, random_state=42, verbose=-1)
    except ImportError:
        logger.warning("lightgbm not installed, skipping.")

    # 4. XGBoost
    try:
        import xgboost as xgb
        cls_candidates["XGBoost"] = xgb.XGBClassifier(n_estimators=150, learning_rate=0.05, max_depth=5, random_state=42, eval_metric="logloss")
    except ImportError:
        logger.warning("xgboost not installed, skipping.")

    # 5. CatBoost
    try:
        from catboost import CatBoostClassifier
        cls_candidates["CatBoost"] = CatBoostClassifier(iterations=200, learning_rate=0.05, depth=6, verbose=0, random_seed=42)
    except ImportError:
        logger.warning("catboost not installed, skipping.")

    best_cls_name = ""
    best_cls_score = -1.0
    best_cls_pipeline = None

    for name, clf in cls_candidates.items():
        pipeline = Pipeline(steps=[("prep", preprocessor), ("model", clf)])
        pipeline.fit(X_train, y_cls_train)
        
        y_prob = pipeline.predict_proba(X_test)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        
        auc = roc_auc_score(y_cls_test, y_prob)
        f1 = f1_score(y_cls_test, y_pred)
        prec = precision_score(y_cls_test, y_pred, zero_division=0)
        rec = recall_score(y_cls_test, y_pred)
        
        logger.info(f"[{name:18s}] ROC-AUC: {auc:.4f} | F1: {f1:.4f} | Precision: {prec:.4f} | Recall: {rec:.4f}")
        
        if auc > best_cls_score:
            best_cls_score = auc
            best_cls_name = name
            best_cls_pipeline = pipeline

    logger.info(f"==> BEST CLASSIFIER: {best_cls_name} (ROC-AUC: {best_cls_score:.4f})")

    # -----------------------------------------------------------------------
    logger.info("\n=== BENCHMARKING REGRESSION (Resolution Hours Prediction) ===")
    reg_candidates: dict[str, Any] = {}
    
    from sklearn.linear_model import Ridge
    reg_candidates["RidgeRegression"] = Ridge()
    
    from sklearn.ensemble import RandomForestRegressor
    reg_candidates["RandomForest"] = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)

    try:
        import lightgbm as lgb
        reg_candidates["LightGBM"] = lgb.LGBMRegressor(n_estimators=150, learning_rate=0.05, max_depth=6, random_state=42, verbose=-1)
    except ImportError:
        pass

    try:
        import xgboost as xgb
        reg_candidates["XGBoost"] = xgb.XGBRegressor(n_estimators=150, learning_rate=0.05, max_depth=5, random_state=42)
    except ImportError:
        pass

    best_reg_name = ""
    best_reg_mae = float("inf")
    best_reg_pipeline = None

    for name, reg in reg_candidates.items():
        pipeline = Pipeline(steps=[("prep", preprocessor), ("model", reg)])
        pipeline.fit(X_train, y_reg_train)
        
        y_pred = pipeline.predict(X_test)
        mae = mean_absolute_error(y_reg_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_reg_test, y_pred))
        r2 = r2_score(y_reg_test, y_pred)
        
        logger.info(f"[{name:18s}] MAE: {mae:.3f} hrs | RMSE: {rmse:.3f} hrs | R²: {r2:.4f}")
        
        if mae < best_reg_mae:
            best_reg_mae = mae
            best_reg_name = name
            best_reg_pipeline = pipeline

    logger.info(f"==> BEST REGRESSOR: {best_reg_name} (MAE: {best_reg_mae:.3f} hrs)")

    # -----------------------------------------------------------------------
    # Export best model pipelines to artifacts
    # -----------------------------------------------------------------------
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    cls_path = out_dir / "breach_risk_v1.joblib"
    reg_path = out_dir / "resolution_v1.joblib"
    
    joblib.dump(best_cls_pipeline, cls_path)
    joblib.dump(best_reg_pipeline, reg_path)
    logger.info(f"Saved best models to:\n - {cls_path}\n - {reg_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark ML Models for AI Workforce Dispatcher")
    parser.add_argument("--data", type=str, default=None, help="Path to CSV/Parquet dataset")
    parser.add_argument("--output", type=str, default="models", help="Output directory for .joblib models")
    args = parser.parse_args()
    
    run_benchmark(data_path=args.data, output_dir=args.output)
