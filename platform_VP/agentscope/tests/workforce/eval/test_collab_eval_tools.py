"""Offline tests for the collaboration evaluation tooling and DEMO MCP data."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "scripts/workforce/eval"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scoring = _load("collab_eval_scoring", EVAL_DIR / "scoring.py")
demo = _load("workforce_demo_mcp", ROOT / "scripts/workforce/demo_mcp_server.py")


def test_amounts_understand_vietnamese_formats() -> None:
    text = "Tổng 2.650.000 VND, còn 1,35 triệu; xe 250k và phí 150 000 đ"
    found = scoring.amounts(text)
    assert {2_650_000, 1_350_000, 250_000, 150_000} <= found


def test_answer_checks_fold_accents_and_flag_incomplete_reply() -> None:
    answer = "Nên chọn DEMO Song Han Riverside, tổng 2,65 triệu. Bạn muốn đặt không?"
    results = scoring.check_answer(
        answer,
        {
            "must_include_any": ["DEMO Sông Hàn Riverside"],
            "amounts_any": [2_650_000],
            "must_not_include": ["Furama"],
            "expect_question": True,
        },
    )
    assert all(result.passed for result in results)

    incomplete = scoring.check_answer(
        "Nhóm chưa hoàn tất yêu cầu trong giới hạn xử lý hiện tại.",
        {},
    )
    assert not incomplete[-1].passed


def test_metric_checks_and_summary() -> None:
    metrics = {
        "total": {"input_tokens": 9000, "cached_input_tokens": 4500, "output_tokens": 1000, "cache_hit_ratio": 0.5, "calls": 6},
        "branches": [
            {"agent_name": "Hotel", "status": "completed", "model_calls": 2, "exchanges": 2},
            {"agent_name": "Car", "status": "stopped", "reason": "exchange limit exceeded", "model_calls": 3, "exchanges": 25},
        ],
        "event_counts": {"question": 1, "answer": 1},
    }
    results = scoring.check_metrics(metrics, {"min_agents": 2, "max_total_tokens": 5000})
    by_name = {r.name: r.passed for r in results}
    assert by_name["≥ 2 agent tham gia"] is True
    assert by_name["tổng token ≤ 5,000"] is False
    assert by_name["không nhánh nào bị runtime dừng"] is False
    summary = scoring.summarize(metrics)
    assert summary["exchanges"] == 27
    assert summary["stopped_branches"] == 1
    assert summary["peer_questions"] == 1


def test_scenarios_file_is_valid_and_ids_unique() -> None:
    data = json.loads((EVAL_DIR / "scenarios.json").read_text(encoding="utf-8"))
    ids = [scenario["id"] for scenario in data["scenarios"]]
    assert len(ids) == len(set(ids))
    for scenario in data["scenarios"]:
        assert scenario["turns"]
        assert scenario["judge_rubric"]


def test_demo_data_matches_scenario_expectations() -> None:
    hotels = demo.search_hotels("Da Nang", guests=2, nights=2)["hotels"]
    totals = {hotel["hotel_id"]: hotel["total_price_vnd"] for hotel in hotels}
    assert totals == {"DN-01": 2_400_000, "DN-02": 1_500_000, "DN-03": 5_200_000}
    car = demo.search_cars("sân bay Đà Nẵng", "Đà Nẵng", 2)["cars"][0]
    assert car["price_vnd"] == 250_000
    cost = demo.calculate_trip_cost(
        [{"label": "DN-01", "amount_vnd": 2_400_000}, {"label": "xe", "amount_vnd": 250_000}],
        budget_vnd=5_000_000,
        reserve_vnd=1_000_000,
    )
    assert cost["total_vnd"] == 2_650_000 and cost["within_ceiling"]

    four = {h["hotel_id"]: h["total_price_vnd"] for h in demo.search_hotels("Đà Nẵng", 4, 2)["hotels"]}
    assert four == {"DN-01": 4_800_000, "DN-02": 3_000_000}
    assert demo.search_hotels("Đà Lạt", 4, 2)["hotels"] == []
    assert demo.lookup_incident_type("vỡ ống nước dưới bồn rửa")["code"] == "PLB-LEAK"
    assert demo.lookup_incident_type("nhà mất điện từ sáng")["code"] == "ELC-OUT"
    assert demo.get_service_fee("PLB-LEAK")["labour_per_hour_vnd"] == 150_000
