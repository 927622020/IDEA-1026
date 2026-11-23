"""Train and evaluate the synthetic stockout prediction model."""

import json
from pathlib import Path

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

from app.ml.feature_contract import (
    FEATURE_COLUMNS,
    FEATURE_CONTRACT_VERSION,
    PREDICTION_HORIZON_DAYS,
)
from app.ml.synthetic_data import generate_synthetic_dataset


def train_stockout_model() -> dict[str, float]:
    """Train LightGBM using a chronological, leakage-aware split."""

    df = generate_synthetic_dataset(
        days=365,
        seed=42,
        location_count=3,
        product_count=5,
    )

    dates = sorted(df["prediction_date"].unique())

    if len(dates) < 30:
        raise ValueError("Insufficient dates for model training")

    split_index = int(len(dates) * 0.8)
    test_start = dates[split_index]

    # Purge the seven days before testing because their target
    # windows could overlap the test period.
    train_cutoff = (
        pd.Timestamp(test_start)
        - pd.Timedelta(days=PREDICTION_HORIZON_DAYS)
    ).date()

    train_df = df[df["prediction_date"] < train_cutoff].copy()
    test_df = df[df["prediction_date"] >= test_start].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Training or testing dataset is empty")

    X_train = train_df[list(FEATURE_COLUMNS)]
    y_train = train_df["stockout_next_7d"]

    X_test = test_df[list(FEATURE_COLUMNS)]
    y_test = test_df["stockout_next_7d"]

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError("Both datasets must contain both target classes")

    positive_count = int(y_train.sum())
    negative_count = len(y_train) - positive_count

    model = LGBMClassifier(
        objective="binary",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=15,
        max_depth=-1,
        scale_pos_weight=negative_count / positive_count,
        random_state=42,
        verbosity=-1,
    )

    model.fit(X_train, y_train)

    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "train_rows": float(len(train_df)),
        "test_rows": float(len(test_df)),
        "train_positive_rate": float(y_train.mean()),
        "test_positive_rate": float(y_test.mean()),
    }

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    joblib.dump(
        model,
        artifacts_dir / "stockout_lightgbm.joblib",
    )
    metadata = {
        "model_name": "stockout_lightgbm",
        "model_type": "LightGBM binary classifier",
        "model_version": FEATURE_CONTRACT_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "prediction_horizon_days": PREDICTION_HORIZON_DAYS,
        "training_data_source": "synthetic",
        "is_production_ready": False,
        "warning": (
            "Trained on synthetic data only. "
            "Metrics do not represent real-world performance."
        ),
        "dataset": {
            "seed": 42,
            "locations": 3,
            "products": 5,
            "training_rows": len(train_df),
            "testing_rows": len(test_df),
            "training_start": str(train_df["prediction_date"].min()),
            "training_end": str(train_df["prediction_date"].max()),
            "testing_start": str(test_df["prediction_date"].min()),
            "testing_end": str(test_df["prediction_date"].max()),
        },
        "metrics": metrics,
        "features": list(FEATURE_COLUMNS),
    }

    metadata_path = artifacts_dir / "stockout_model_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
 )
    print("\nSYNTHETIC STOCKOUT MODEL EVALUATION")
    print("----------------------------------")
    print(f"Training rows: {len(train_df)}")
    print(f"Testing rows: {len(test_df)}")
    print(f"Training period ends: {train_df['prediction_date'].max()}")
    print(f"Testing period starts: {test_df['prediction_date'].min()}")
    print(f"ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"PR-AUC: {metrics['pr_auc']:.4f}")

    print("\nClassification report:")
    print(classification_report(y_test, predictions, zero_division=0))

    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions))

    print("\nFeature importance:")
    importance = pd.Series(
        model.feature_importances_,
        index=FEATURE_COLUMNS,
    ).sort_values(ascending=False)

    print(importance.to_string())

    print("\nModel saved to artifacts/stockout_lightgbm.joblib")
    print("WARNING: This model was trained on synthetic data only.")

    return metrics


if __name__ == "__main__":
    train_stockout_model()
