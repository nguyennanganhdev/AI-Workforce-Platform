"""Tests for ML features, predictor fallback, and Vietnamese text normalizer."""

from __future__ import annotations

import pytest

from dispatcher.ml.features import encode_categorical, extract_features
from dispatcher.ml.predictor import MLPredictor
from dispatcher.ml.text_normalizer import normalize_vietnamese_text


def test_vietnamese_text_normalizer():
    # Test abbreviations & resident teencode
    raw = "Bql ơi tm s201 k chạy, bấm k đk, mùi khét vl"
    clean = normalize_vietnamese_text(raw)
    
    assert "ban quản lý" in clean.lower()
    assert "thang máy" in clean.lower()
    assert "tòa S2.01" in clean
    assert "không chạy" in clean.lower()
    assert "không được" in clean.lower()

    # Test real estate domain abbreviations & chat slang
    raw2 = "Ad ơi ch p1204 s102 bị chập cb dh, nc tràn ngập sàn toang rồi help gấp"
    clean2 = normalize_vietnamese_text(raw2)
    assert "quản trị viên" in clean2.lower()
    assert "căn hộ" in clean2.lower()
    assert "tòa S1.02" in clean2
    assert "cầu dao điện" in clean2.lower()
    assert "điều hòa" in clean2.lower()
    assert "hỏng nặng rồi" in clean2.lower()
    assert "cứu giúp" in clean2.lower()


def test_extract_features_safe_at_intake():
    feats = extract_features(
        text="Báo cáo rò rỉ nước tại căn hộ P1204 tòa S102",
        category="PLUMBING",
        location_type="APARTMENT",
        has_image=True,
        num_attachments=2,
        created_at="2026-09-29T10:30:00Z",
        staff_availability=0.8,
        current_workload=5,
    )
    
    assert feats["category"] == "PLUMBING"
    assert feats["has_image"] == 1
    assert feats["num_attachments"] == 2
    assert feats["staff_availability"] == 0.8
    assert "actual_resolution_hours" not in feats  # No leakage


def test_encode_categorical():
    raw_feats = {
        "category": "PLUMBING",
        "location_type": "APARTMENT",
        "word_count": 10,
    }
    encoded = encode_categorical(raw_feats)
    assert encoded["cat_PLUMBING"] == 1
    assert encoded["cat_ELECTRICAL"] == 0
    assert encoded["loc_APARTMENT"] == 1
    assert encoded["loc_LOBBY"] == 0
    assert "category" not in encoded


def test_ml_predictor_graceful_fallback(tmp_path):
    predictor = MLPredictor(model_dir=str(tmp_path))
    predictor.load()
    
    # When model files are absent, should return safe fallback without crashing
    feats = extract_features(
        text="Thử nghiệm",
        category="OTHER",
        location_type="OTHER",
        has_image=False,
        num_attachments=0,
    )
    prob = predictor.predict_breach_risk(feats)
    assert prob == 0.0
