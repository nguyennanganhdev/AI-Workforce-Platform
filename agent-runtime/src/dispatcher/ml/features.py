"""Feature extraction from TicketReport for ML models.

Only features that are SAFE at prediction time are included.
Post-outcome variables (actual_resolution_hours, number_of_reassignments,
number_of_rejections) are excluded to prevent data leakage.

See the analysis § IX for the full feature safety classification.
"""

from __future__ import annotations

import re
from datetime import datetime

from dispatcher.ml.text_normalizer import normalize_vietnamese_text


def extract_features(
    text: str,
    category: str,
    location_type: str,
    has_image: bool,
    num_attachments: int,
    created_at: str | None = None,
    staff_availability: float | None = None,
    current_workload: int | None = None,
    similar_case_count: int | None = None,
) -> dict:
    """Extract a feature dict for ML models.

    All parameters are available at intake time — no post-outcome leakage.

    Returns a flat dict ready for model input (after encoding).
    """
    features: dict = {}

    # Normalize Vietnamese text (resolves resident slang, teencode, domain abbreviations)
    clean_text = normalize_vietnamese_text(text)

    # Text features (safe at intake)
    features["description_length"] = len(clean_text)
    features["word_count"] = len(clean_text.split())
    features["has_question_mark"] = int("?" in text)
    features["has_exclamation"] = int("!" in text)
    features["mention_count"] = len(re.findall(r"@\w+", text))

    # Category features (safe — determined at intake)
    features["category"] = category

    # Location features (safe — from property context)
    features["location_type"] = location_type

    # Attachment features (safe — known at submission)
    features["has_image"] = int(has_image)
    features["num_attachments"] = num_attachments

    # Temporal features (safe — from timestamp)
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at)
            features["created_hour"] = dt.hour
            features["created_day"] = dt.weekday()
            features["is_weekend"] = int(dt.weekday() >= 5)
            # Night shift (22:00 – 06:00) — typically less staff
            features["is_night"] = int(dt.hour >= 22 or dt.hour < 6)
        except (ValueError, TypeError):
            features["created_hour"] = 12
            features["created_day"] = 2
            features["is_weekend"] = 0
            features["is_night"] = 0
    else:
        features["created_hour"] = 12
        features["created_day"] = 2
        features["is_weekend"] = 0
        features["is_night"] = 0

    # Operational context (safe — current state, not outcome)
    features["staff_availability"] = staff_availability if staff_availability is not None else 0.5
    features["current_workload"] = current_workload if current_workload is not None else 0
    features["similar_case_count"] = similar_case_count if similar_case_count is not None else 0

    return features


# ---------------------------------------------------------------------------
# Known categories for one-hot encoding
# ---------------------------------------------------------------------------

KNOWN_CATEGORIES: list[str] = [
    "PLUMBING", "ELECTRICAL", "ELEVATOR", "FIRE_SAFETY",
    "SANITATION", "SECURITY", "STRUCTURAL", "HVAC",
    "LANDSCAPE", "PEST_CONTROL", "PARKING", "ACCESS_CONTROL",
    "WATER_SUPPLY", "DRAINAGE", "OTHER",
]

KNOWN_LOCATIONS: list[str] = [
    "APARTMENT", "LOBBY", "PARKING", "POOL",
    "GYM", "GARDEN", "ROOFTOP", "BASEMENT",
    "CORRIDOR", "STAIRWELL", "UTILITY_ROOM", "OTHER",
]


def encode_categorical(features: dict) -> dict:
    """One-hot encode categorical features for sklearn/xgboost models.

    Returns a new dict with categorical fields replaced by binary columns.
    """
    encoded = {k: v for k, v in features.items() if k not in ("category", "location_type")}

    cat = features.get("category", "OTHER")
    for c in KNOWN_CATEGORIES:
        encoded[f"cat_{c}"] = int(cat == c)

    loc = features.get("location_type", "OTHER")
    for loc_type in KNOWN_LOCATIONS:
        encoded[f"loc_{loc_type}"] = int(loc == loc_type)

    return encoded
