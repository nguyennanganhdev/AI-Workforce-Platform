"""End-to-End Interactive & Automated Demo for AI Workforce Platform Dispatcher Pipeline.

Usage:
    .venv\\Scripts\\python agent-runtime/demo_dispatcher.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add src to sys.path so dispatcher package is discoverable
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dispatcher.agent_selector import build_selected_agents
from dispatcher.contracts import (
    EligibleAgentRef,
    IncidentContext,
    ReportContext,
    SlaPolicyRef,
)
from dispatcher.ml.predictor import MLPredictor
from dispatcher.ml.text_normalizer import normalize_vietnamese_text
from dispatcher.rules import check_approval_required, resolve_sla
from dispatcher.ticket_classifier import TicketClassifier


class SimulatedLLMCompleter:
    """Mock LLM response for demonstration without requiring API keys."""

    async def complete(self, prompt: str) -> str:
        # Simulate structured JSON returned by LLM
        return json.dumps({
            "category": "ELECTRICAL",
            "severity": "HIGH",
            "urgency": "HIGH",
            "complexity": "MODERATE",
            "confidence": 0.96,
            "evidence": [
                "Chập cầu dao tổng tại căn hộ",
                "Mùi khét lẹt và nguy cơ cháy nổ cao trong đêm",
            ],
        })


async def run_pipeline():
    print("=" * 70)
    print("        🚀 AI WORKFORCE PLATFORM - DISPATCHER PIPELINE DEMO 🚀        ")
    print("=" * 70)

    # 1. Resident input with slang & abbreviations
    raw_text = "Ad ơi ch p1204 s102 bị chập cb dh, khét lẹt toang rồi help gấp!!"
    report: ReportContext = {
        "text": raw_text,
        "attachments": [
            {"name": "cb_chay.jpg", "media_type": "image/jpeg", "size_bytes": 150000},
        ],
        "facts": ["Báo cáo lúc 23:15 đêm", "Tòa S1.02 Vinhomes"],
        "resident_mentioned_agent": None,
    }

    print("\n[BƯỚC 1] 📩 TIẾP NHẬN BÁO CÁO CƯ DÂN:")
    print(f"  • Tin nhắn thô:   \"{raw_text}\"")
    clean_text = normalize_vietnamese_text(raw_text)
    print(f"  • Sau chuẩn hóa:  \"{clean_text}\"")
    print(f"  • Tệp đính kèm:   1 ảnh ({report['attachments'][0]['name']})")

    # 2. Init Predictor & Classifier
    models_dir = str(Path(__file__).parent / "src" / "dispatcher" / "ml" / "models")
    predictor = MLPredictor(model_dir=models_dir)
    predictor.load()
    classifier = TicketClassifier(llm=SimulatedLLMCompleter(), ml_predictor=predictor)

    # 3. Classify & ML Signals
    print("\n[BƯỚC 2] 🧠 PHÂN LOẠI & DỰ BÁO AI (HYBRID CLASSIFICATION):")
    classification, signals, evidence = await classifier.classify(report)
    print(f"  • Danh mục sự cố:       {classification['category']}")
    print(f"  • Mức độ nghiêm trọng:  {classification['severity']}")
    print(f"  • Độ khẩn cấp:          {classification['urgency']}")
    print(f"  • Độ phức tạp:          {classification['complexity']}")
    print(f"  • Độ tin cậy (LLM):     {classification['confidence']:.2%}")
    print(f"  • Căn cứ phân loại:     {evidence[0]}")

    if signals:
        print("\n  📊 TÍN HIỆU ML (ADVISORY PREDICTION SIGNALS):")
        print(f"    - Model version:       {signals['model_version']}")
        print(f"    - Rủi ro vi phạm SLA:  {signals['sla_breach_risk']:.1%}")
        print(f"    - Ước tính xử lý:      {signals['predicted_resolution_hours']:.1f} giờ")

    # 4. Rules & SLA Matching
    print("\n[BƯỚC 3] ⚖️ RULE ENGINE & ÁP ĐẶT CAM KẾT SLA (HARD CONSTRAINTS):")
    sla_policies: list[SlaPolicyRef] = [
        {
            "sla_policy_id": "sla-elec-high",
            "category": "ELECTRICAL",
            "severity": "HIGH",
            "first_response_time_minutes": 15,
            "resolution_time_minutes": 120,
            "escalation_time_minutes": 30,
            "warning_threshold_percent": 75.0,
            "created_at": "2026-09-01T00:00:00Z",
        },
    ]
    sla = resolve_sla(classification, sla_policies)
    
    incident: IncidentContext = {
        "incident_id": "inc-2026-0929",
        "human_reported_severity": None,
        "is_safety_hazard": True,
        "is_recurring": False,
        "property_tier": "PREMIUM",
    }
    require_approval, approval_reason = check_approval_required(classification, incident)
    print(f"  • Mã chính sách SLA:    {sla['policy_id']}")
    print(f"  • Phản hồi lần đầu:     <= {sla['first_response_minutes']} phút")
    print(f"  • Giải quyết dứt điểm:  <= {sla['resolution_minutes']} phút (2.0 giờ)")
    print(f"  • Yêu cầu BQL duyệt:    {'CÓ ⚠️ (' + str(approval_reason) + ')' if require_approval else 'KHÔNG'}")

    # 5. Agent Routing
    print("\n[BƯỚC 4] 👥 ĐIỀU PHỐI ĐỘI AGENT (MULTI-AGENT ROSTER):")
    available_agents: list[EligibleAgentRef] = [
        {
            "agent_version_id": "agent-coord-01",
            "role": "COORDINATOR",
            "category_affinity": ["GENERAL"],
            "deployment_status": "ACTIVE",
            "status": "PUBLISHED",
            "max_concurrent_sessions": 10,
        },
        {
            "agent_version_id": "agent-elec-spec",
            "role": "SPECIALIST",
            "category_affinity": ["ELECTRICAL"],
            "deployment_status": "ACTIVE",
            "status": "PUBLISHED",
            "max_concurrent_sessions": 5,
        },
        {
            "agent_version_id": "agent-reviewer",
            "role": "REVIEWER",
            "category_affinity": ["GENERAL"],
            "deployment_status": "ACTIVE",
            "status": "PUBLISHED",
            "max_concurrent_sessions": 5,
        },
    ]
    selected_agents, warnings = build_selected_agents(
        classification=classification,
        eligible=available_agents,
        resident_requested=None,
    )
    for agent in selected_agents:
        print(f"  • [{agent['role']:11s}] ID: {agent['agent_version_id']:18s} (Lý do chọn: {agent['selection_reason']})")

    print("\n" + "=" * 70)
    print("            ✅ TOÀN BỘ PIPELINE ĐÃ CHẠY THÀNH CÔNG!            ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_pipeline())
