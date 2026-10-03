"""End-to-End Interactive & Automated Demo for AI Workforce Platform Dispatcher Pipeline.

Demonstrates:
  1. Vietnamese Slang / Abbreviation Text Normalization
  2. Hybrid Incident Classification (LLM + ML Predictor)
  3. ML Signals: SLA Breach Risk & Estimated Resolution Hours
  4. SLA Policy Matching & Safety Approval Rules
  5. Multi-Agent Roster Selection (Coordinator, Specialist, Reviewer)
  6. Turn Policy & Token/Time Budgeting
  7. Complete DispatcherDecision Assembly
  8. GroupChat Adapter: Conversion to OpenRoom Payload (DEV-4 Integration)

Usage:
    .venv\\Scripts\\python agent-runtime/demo_dispatcher.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add src to sys.path so dispatcher package is discoverable
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dispatcher.adapters.groupchat_adapter import to_open_room_payload
from dispatcher.agent_selector import AgentSelector
from dispatcher.contracts import (
    EligibleAgentRef,
    IncidentContext,
    ReportContext,
    SlaPolicyRef,
    TicketReport,
)
from dispatcher.decision import build_decision
from dispatcher.ml.predictor import MLPredictor
from dispatcher.ml.text_normalizer import normalize_vietnamese_text
from dispatcher.ticket_classifier import TicketClassifier
from dispatcher.turn_policy import TurnPolicyEngine


import os
import urllib.error
import urllib.request


class GeminiCompleter:
    """Real Google Gemini API Completer via native REST API (zero extra package required)."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        loop = asyncio.get_running_loop()

        def _fetch() -> str:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]

        return await loop.run_in_executor(None, _fetch)


class OpenAICompleter:
    """Real OpenAI API Completer via native REST API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        loop = asyncio.get_running_loop()

        def _fetch() -> str:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]

        return await loop.run_in_executor(None, _fetch)


class SimulatedLLMCompleter:
    """Mock LLM response for demonstration without requiring cloud API keys."""

    async def complete(self, prompt: str) -> str:
        # Simulate structured JSON returned by Gemini / Claude
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


def get_llm_completer():
    """Auto-detect LLM provider from environment variables, or fallback to simulated mock."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if gemini_key:
        print("  🔑 LLM Provider: Google Gemini API (gemini-1.5-flash) [Real]")
        return GeminiCompleter(gemini_key)
    elif openai_key:
        print("  🔑 LLM Provider: OpenAI API (gpt-4o-mini) [Real]")
        return OpenAICompleter(openai_key)
    else:
        print("  ⚡ LLM Provider: Simulated LLM Mock (Offline Mode - No API Key needed)")
        return SimulatedLLMCompleter()


async def run_pipeline():
    print("=" * 76)
    print("      🚀 AI WORKFORCE PLATFORM - DISPATCHER & ML PIPELINE DEMO 🚀      ")
    print("=" * 76)

    # 1. Resident input with slang & abbreviations
    raw_text = "Ad ơi ch p1204 s102 bị chập cb dh, khét lẹt toang rồi help gấp!!"
    report: ReportContext = {
        "text": raw_text,
        "attachments": [
            {"name": "cb_chay.jpg", "media_type": "image/jpeg", "size_bytes": 150000},
        ],
        "facts": ["Báo cáo lúc 23:15 đêm", "Tòa S1.02 Vinhomes Ocean Park"],
        "resident_mentioned_agent": None,
    }

    print("\n[BƯỚC 1] 📩 TIẾP NHẬN BÁO CÁO CƯ DÂN & TIỀN XỬ LÝ:")
    print(f"  • Tin nhắn thô:   \"{raw_text}\"")
    clean_text = normalize_vietnamese_text(raw_text)
    print(f"  • Sau chuẩn hóa:  \"{clean_text}\"")
    print(f"  • Tệp đính kèm:   1 ảnh ({report['attachments'][0]['name']})")

    # 2. Init Predictor & Classifier
    models_dir = str(Path(__file__).parent / "src" / "dispatcher" / "ml" / "models")
    predictor = MLPredictor(model_dir=models_dir)
    predictor.load()
    llm = get_llm_completer()
    classifier = TicketClassifier(llm=llm, ml_predictor=predictor)

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

    # 4. Define Incident & Policies
    incident: IncidentContext = {
        "incident_id": "inc-2026-0930",
        "human_reported_severity": None,
        "is_safety_hazard": True,
        "is_recurring": False,
        "property_tier": "PREMIUM",
    }
    sla_policies: list[SlaPolicyRef] = [
        {
            "policy_id": "sla-elec-high",
            "sla_policy_id": "sla-elec-high",
            "category": "ELECTRICAL",
            "severity": "HIGH",
            "response_minutes": 15,
            "resolution_minutes": 120,
            "first_response_time_minutes": 15,
            "resolution_time_minutes": 120,
            "escalation_time_minutes": 30,
            "warning_threshold_percent": 75.0,
            "created_at": "2026-09-01T00:00:00Z",
        },
    ]
    eligible_agents: list[EligibleAgentRef] = [
        {
            "agent_id": "agent-coord-01",
            "agent_version_id": "agent-coord-01",
            "role": "COORDINATOR",
            "capabilities": ["GENERAL", "ORCHESTRATION"],
            "category_affinity": ["GENERAL"],
            "deployment_status": "ACTIVE",
            "status": "PUBLISHED",
            "max_concurrent_sessions": 10,
        },
        {
            "agent_id": "agent-elec-spec",
            "agent_version_id": "agent-elec-spec",
            "role": "SPECIALIST",
            "capabilities": ["ELECTRICAL", "MAINTENANCE"],
            "category_affinity": ["ELECTRICAL"],
            "deployment_status": "ACTIVE",
            "status": "PUBLISHED",
            "max_concurrent_sessions": 5,
        },
        {
            "agent_id": "agent-reviewer",
            "agent_version_id": "agent-reviewer",
            "role": "REVIEWER",
            "capabilities": ["GENERAL", "QUALITY_ASSURANCE"],
            "category_affinity": ["GENERAL"],
            "deployment_status": "ACTIVE",
            "status": "PUBLISHED",
            "max_concurrent_sessions": 5,
        },
    ]

    ticket: TicketReport = {
        "ticket_id": "TK-2026-VHM-8899",
        "tenant_id": "tenant-vinhomes-oceanpark",
        "correlation_id": "corr-session-001",
        "subject": {
            "namespace": "vinhomes-p1204",
            "subject_id": "sub-apartment-s102",
        },
        "report": report,
        "incident": incident,
        "sla_policies": sla_policies,
        "eligible_agents": eligible_agents,
        "created_at": "2026-09-30T04:15:00Z",
    }

    # 5. Build Complete Decision
    print("\n[BƯỚC 3] ⚙️ ASSEMBLE DISPATCHER DECISION (ENGINE ORCHESTRATION):")
    selector = AgentSelector()
    policy_engine = TurnPolicyEngine()
    decision = await build_decision(
        ticket=ticket,
        classifier=classifier,
        selector=selector,
        policy_engine=policy_engine,
    )

    print(f"  • Decision ID:          {decision['decision_id']}")
    print(f"  • SLA Phản hồi:         <= {decision['sla']['response_minutes']} phút")
    print(f"  • SLA Giải quyết:       <= {decision['sla']['resolution_minutes']} phút (2.0 giờ)")
    approval_str = f"CÓ ⚠️ ({decision['approval_reason']})" if decision['requires_approval'] else "KHÔNG"
    print(f"  • Cần duyệt BQL:        {approval_str}")
    print(f"  • Turn Policy purpose:  {decision['turn_policy']['purpose']}")
    print(f"  • Max Turns:            {decision['turn_policy']['max_turns']}")
    print(f"  • Max Consecutive:      {decision['turn_policy']['max_consecutive_turns']}")
    print(f"  • Session Timeout:      {decision['turn_policy']['timeout_seconds']}s")

    print("\n[BƯỚC 4] 👥 ĐỘI AGENT ĐƯỢC CHỌN (ROSTER):")
    for agent in decision["selected_agents"]:
        print(f"  • [{agent['role']:11s}] ID: {agent['agent_version_id']:18s} (Lý do: {agent['selection_reason']})")

    # 6. Adapter to GroupChat (DEV-4 integration)
    print("\n[BƯỚC 5] 🔌 ADAPTER MAPPING → GROUPCHAT OPENROOM (DEV-4 COMPATIBILITY):")
    open_room = to_open_room_payload(ticket=ticket, decision=decision)
    gc_context = open_room["context"]
    gc_payload = open_room["payload"]
    print(f"  • GroupChat Room Version: {gc_payload['groupchat_version_id']}")
    print(f"  • Context Tenant ID:      {gc_context['tenant_id']}")
    print(f"  • Context Ticket ID:      {gc_context['ticket_id']}")
    print(f"  • Initial Participants:   {len(gc_payload['participants'])} agents")
    for p in gc_payload['participants']:
        print(f"      - {p['role']:12s}: {p['agent_version_id']}")
    print(f"  • Max Turns in Room:      {gc_payload['turn_policy']['max_turns']}")
    print(f"  • Max Consecutive:        {gc_payload['turn_policy']['max_consecutive_turns']}")
    print(f"  • Room Timeout:           {gc_payload['turn_policy']['timeout_seconds']}s")

    print("\n" + "=" * 76)
    print("            ✅ TOÀN BỘ PIPELINE ĐÃ CHẠY THÀNH CÔNG 100%!            ")
    print("=" * 76)


if __name__ == "__main__":
    asyncio.run(run_pipeline())
