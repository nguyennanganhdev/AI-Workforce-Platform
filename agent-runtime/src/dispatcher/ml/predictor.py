"""ML model loader and predictor for advisory signals.

Loads trained model artifacts (.joblib) from a configurable directory
and exposes the MLPredictor protocol expected by TicketClassifier.

Model training happens in research/platform/ml/ — NOT here.
Models are serialized to .joblib and deployed alongside the runtime.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dispatcher.contracts import Complexity, Urgency
from dispatcher.ml.features import encode_categorical, extract_features

logger = logging.getLogger(__name__)

# Default path for model artifacts — overridden by MODEL_ARTIFACTS_DIR env var
_DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "..", "models",
)


class MLPredictor:
    """Loads and runs traditional ML models for advisory predictions.

    Implements the MLPredictor protocol from ticket_classifier.py.
    All predictions are advisory — they never override business rules.
    """

    def __init__(self, model_dir: str | None = None) -> None:
        self._model_dir = Path(model_dir or os.environ.get("MODEL_ARTIFACTS_DIR", _DEFAULT_MODEL_DIR))
        self._urgency_model: Any | None = None
        self._resolution_model: Any | None = None
        self._complexity_model: Any | None = None
        self._breach_model: Any | None = None
        self._model_version: str = "none"
        self._loaded = False

    def load(self) -> None:
        """Load model artifacts from disk.

        Called once at startup.  If any model file is missing, that
        prediction is disabled but others still work.
        """
        try:
            import joblib  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("joblib not installed; ML predictions disabled")
            return

        for name, attr in [
            ("urgency", "_urgency_model"),
            ("resolution", "_resolution_model"),
            ("complexity", "_complexity_model"),
            ("breach_risk", "_breach_model"),
        ]:
            path = self._model_dir / f"{name}_v1.joblib"
            if path.exists():
                setattr(self, attr, joblib.load(path))
                logger.info("Loaded ML model: %s", path)
            else:
                logger.info("ML model not found (optional): %s", path)

        # Version is derived from whichever models were loaded
        loaded = [
            name for name, attr in [
                ("urgency", "_urgency_model"),
                ("resolution", "_resolution_model"),
                ("complexity", "_complexity_model"),
                ("breach_risk", "_breach_model"),
            ]
            if getattr(self, attr) is not None
        ]
        self._model_version = f"v1:{'+'.join(loaded)}" if loaded else "none"
        self._loaded = True

    @property
    def model_version(self) -> str:
        return self._model_version

    def predict_urgency(self, features: dict) -> tuple[Urgency, float]:
        """Predict urgency level and confidence."""
        if self._urgency_model is None:
            return "MEDIUM", 0.0

        encoded = encode_categorical(features)
        try:
            prediction = self._urgency_model.predict([list(encoded.values())])[0]
            proba = self._urgency_model.predict_proba([list(encoded.values())])[0]
            confidence = float(max(proba))
            urgency_map: dict[int, Urgency] = {0: "LOW", 1: "MEDIUM", 2: "HIGH", 3: "CRITICAL"}
            return urgency_map.get(int(prediction), "MEDIUM"), confidence
        except Exception:
            logger.warning("Urgency prediction failed", exc_info=True)
            return "MEDIUM", 0.0

    def predict_resolution_hours(self, features: dict) -> tuple[float, float]:
        """Predict resolution hours and confidence."""
        if self._resolution_model is None:
            return 0.0, 0.0

        encoded = encode_categorical(features)
        try:
            prediction = float(self._resolution_model.predict([list(encoded.values())])[0])
            # For regression, use R² score as rough confidence proxy
            confidence = 0.5  # Placeholder until we have calibration data
            return max(0.0, prediction), confidence
        except Exception:
            logger.warning("Resolution prediction failed", exc_info=True)
            return 0.0, 0.0

    def predict_complexity(self, features: dict) -> Complexity:
        """Predict ticket complexity."""
        if self._complexity_model is None:
            return "MODERATE"

        encoded = encode_categorical(features)
        try:
            prediction = self._complexity_model.predict([list(encoded.values())])[0]
            complexity_map: dict[int, Complexity] = {0: "SIMPLE", 1: "MODERATE", 2: "COMPLEX"}
            return complexity_map.get(int(prediction), "MODERATE")
        except Exception:
            logger.warning("Complexity prediction failed", exc_info=True)
            return "MODERATE"

    def predict_breach_risk(self, features: dict) -> float:
        """Predict SLA breach probability (0.0–1.0)."""
        if self._breach_model is None:
            return 0.0

        encoded = encode_categorical(features)
        try:
            proba = self._breach_model.predict_proba([list(encoded.values())])[0]
            return float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception:
            logger.warning("Breach risk prediction failed", exc_info=True)
            return 0.0
