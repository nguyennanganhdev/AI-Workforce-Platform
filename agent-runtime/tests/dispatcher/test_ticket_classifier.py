"""Comprehensive tests and benchmarks for TicketClassifier, Latency, and Cost estimation."""

from __future__ import annotations

import json
import time
import pytest
from pathlib import Path

from dispatcher.contracts import ReportContext
from dispatcher.ml.predictor import MLPredictor
from dispatcher.ticket_classifier import TicketClassifier, _build_classification_prompt


class MockLLMCompleter:
    """Simulated LLM completer with configurable latency and responses."""

    def __init__(self, response_text: str | None = None, should_fail: bool = False, simulated_delay_s: float = 0.0):
        self.response_text = response_text or json.dumps({
            "category": "PLUMBING",
            "severity": "HIGH",
            "urgency": "HIGH",
            "complexity": "MODERATE",
            "confidence": 0.95,
            "evidence": ["Water leakage reported on ceiling", "Risk of electrical short"],
        })
        self.should_fail = should_fail
        self.simulated_delay_s = simulated_delay_s
        self.prompt_calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.prompt_calls.append(prompt)
        if self.simulated_delay_s > 0:
            time.sleep(self.simulated_delay_s)
        if self.should_fail:
            raise RuntimeError("Connection error to LLM Provider")
        return self.response_text


@pytest.fixture
def sample_report() -> ReportContext:
    return {
        "text": "Căn hộ S2.01-1204 bị rò rỉ nước từ trần nhà vệ sinh, chảy lênh láng ra sàn gỗ.",
        "attachments": [
            {"name": "leak1.jpg", "media_type": "image/jpeg", "size_bytes": 102400},
            {"name": "leak2.jpg", "media_type": "image/jpeg", "size_bytes": 204800},
        ],
        "facts": ["Resident reported at 10:30 AM", "Tower S2.01"],
        "resident_mentioned_agent": None,
    }


@pytest.mark.asyncio
async def test_ticket_classifier_happy_path(sample_report):
    completer = MockLLMCompleter()
    classifier = TicketClassifier(llm=completer)

    classification, signals, evidence = await classifier.classify(sample_report)

    assert classification["category"] == "PLUMBING"
    assert classification["severity"] == "HIGH"
    assert classification["urgency"] == "HIGH"
    assert classification["complexity"] == "MODERATE"
    assert classification["confidence"] == 0.95
    assert classification["method"] == "LLM"
    assert "LLM confidence: 0.95" in evidence


@pytest.mark.asyncio
async def test_ticket_classifier_markdown_json_tolerance(sample_report):
    # LLM returns markdown fenced JSON block
    fenced_output = """```json
    {
        "category": "ELECTRICAL",
        "severity": "CRITICAL",
        "urgency": "CRITICAL",
        "complexity": "COMPLEX",
        "confidence": 0.92,
        "evidence": ["Mùi khét tại tủ điện tầng 5"]
    }
    ```"""
    completer = MockLLMCompleter(response_text=fenced_output)
    classifier = TicketClassifier(llm=completer)

    classification, signals, evidence = await classifier.classify(sample_report)
    assert classification["category"] == "ELECTRICAL"
    assert classification["severity"] == "CRITICAL"
    assert classification["method"] == "LLM"


@pytest.mark.asyncio
async def test_ticket_classifier_llm_failure_graceful_fallback(sample_report):
    completer = MockLLMCompleter(should_fail=True)
    classifier = TicketClassifier(llm=completer)

    classification, signals, evidence = await classifier.classify(sample_report)

    assert classification["category"] == "OTHER"
    assert classification["severity"] == "MEDIUM"
    assert classification["urgency"] == "MEDIUM"
    assert classification["method"] == "RULE"
    assert any("fallback" in e.lower() for e in evidence)


@pytest.mark.asyncio
async def test_ticket_classifier_with_ml_predictor(sample_report, tmp_path):
    # Test integration with MLPredictor (even if models directory is mock/empty)
    predictor = MLPredictor(model_dir=str(tmp_path))
    predictor.load()

    completer = MockLLMCompleter()
    classifier = TicketClassifier(llm=completer, ml_predictor=predictor)

    classification, signals, evidence = await classifier.classify(sample_report)
    assert classification["category"] == "PLUMBING"
    assert signals is not None
    assert signals["model_version"] == "none"
    assert signals["sla_breach_risk"] == 0.0


@pytest.mark.asyncio
async def test_benchmark_latency_and_cost_estimation(sample_report):
    """Benchmark inference latency and token cost estimation for Ticket Classification."""
    prompt = _build_classification_prompt(sample_report)
    
    # 1. Cost Estimation (Rule of thumb: ~4 chars per token for EN/code, ~2-3 chars for VN)
    # Estimate prompt input tokens and expected JSON output tokens
    est_prompt_tokens = len(prompt) // 3
    est_output_tokens = 150  # Fixed schema JSON output
    total_tokens = est_prompt_tokens + est_output_tokens
    
    # Pricing benchmarks (e.g. Gemini 1.5 Flash / GPT-4o-mini rates: ~$0.15 per 1M input, $0.60 per 1M output)
    cost_per_million_input = 0.15
    cost_per_million_output = 0.60
    est_cost_usd = (est_prompt_tokens * cost_per_million_input + est_output_tokens * cost_per_million_output) / 1_000_000

    # 2. Latency Benchmark: Overhead of Dispatcher classification parsing & feature extraction
    completer = MockLLMCompleter()
    classifier = TicketClassifier(llm=completer)

    start_time = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        await classifier.classify(sample_report)
    elapsed = time.perf_counter() - start_time
    avg_latency_ms = (elapsed / iterations) * 1000

    # Dispatcher overhead must be sub-millisecond (excluding network roundtrip to LLM)
    assert avg_latency_ms < 2.0, f"Dispatcher overhead {avg_latency_ms:.3f}ms exceeds 2ms threshold"
    assert est_cost_usd < 0.0005, "Classification prompt exceeds acceptable cost limit per ticket"
