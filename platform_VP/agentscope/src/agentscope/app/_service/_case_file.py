# -*- coding: utf-8 -*-
"""The case file of one customer turn: its evidence and what it cost.

A team chat keeps a copy of every member reply in the Leader session (with
its tool calls, results and token usage), so one session read is enough to
show which lookups backed an answer and how many tokens each agent spent.
"""
import json
import os
from typing import Any

from ..._logging import logger
from ...message import Msg, ToolCallBlock, ToolResultBlock
from ..storage import StorageBase

# Coordination tools are how agents talk, not evidence for an answer.
_INTERNAL_TOOLS = frozenset(
    {
        "TeamSay",
        "TeamCreate",
        "TeamDelete",
        "AgentInvite",
        "AgentCreate",
        "Skill",
        "SharedContextRead",
        "MemoryPropose",
    },
)
_RESULT_CHARS = 1500
_PAGE_SIZE = 200
_MAX_PAGES = 25


def model_prices() -> dict[str, dict[str, float]]:
    """Prices per 1M tokens from ``WORKFORCE_MODEL_PRICES``.

    Format: ``{"gpt-6-luna": {"input": 1.25, "cached_input": 0.125,
    "output": 10}}`` in USD. Models without a price get no cost; prices are
    never guessed.
    """
    raw = os.getenv("WORKFORCE_MODEL_PRICES", "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        logger.warning("WORKFORCE_MODEL_PRICES is not valid JSON; costs are not shown.")
        return {}
    prices: dict[str, dict[str, float]] = {}
    if isinstance(value, dict):
        for model, entry in value.items():
            if isinstance(entry, dict) and {"input", "output"} <= entry.keys():
                try:
                    prices[str(model)] = {k: float(v) for k, v in entry.items()}
                except (TypeError, ValueError):
                    continue
    return prices


def _result_text(result: ToolResultBlock) -> str:
    if isinstance(result.output, str):
        text = result.output
    else:
        text = "\n".join(
            getattr(block, "text", "") for block in result.output if getattr(block, "text", "")
        )
    return text if len(text) <= _RESULT_CHARS else text[:_RESULT_CHARS] + "…"


def _arguments(call: ToolCallBlock) -> Any:
    try:
        return json.loads(call.input) if call.input else {}
    except ValueError:
        return call.input


def _cost(usage: dict[str, int], price: dict[str, float] | None) -> float | None:
    if price is None:
        return None
    cached = usage["cache_input_tokens"]
    uncached = max(usage["input_tokens"] - cached, 0)
    return (
        uncached * price["input"]
        + cached * price.get("cached_input", price["input"])
        + usage["output_tokens"] * price["output"]
    ) / 1_000_000


def _latest_copies(messages: list[Msg]) -> list[Msg]:
    """One entry per id, at its first position, with its latest copy."""
    latest = {message.id: message for message in messages}
    seen: set[str] = set()
    unique = []
    for message in messages:
        if message.id not in seen:
            seen.add(message.id)
            unique.append(latest[message.id])
    return unique


def turn_messages(messages: list[Msg], message_id: str) -> list[Msg] | None:
    """The customer turn containing ``message_id``: from its customer message
    to the next one. ``None`` when the message is not in ``messages``."""
    messages = _latest_copies(messages)
    index = next((i for i, m in enumerate(messages) if m.id == message_id), None)
    if index is None:
        return None
    start = next((i for i in range(index, -1, -1) if messages[i].role == "user"), 0)
    end = next(
        (i for i in range(start + 1, len(messages)) if messages[i].role == "user"),
        len(messages),
    )
    return messages[start:end]


def customer_text(message: Msg) -> str:
    """The text a customer typed."""
    return "\n".join(
        getattr(block, "text", "") for block in message.content if getattr(block, "type", "") == "text"
    )


def build_case_file(
    messages: list[Msg],
    message_id: str,
    *,
    leader_agent_id: str,
    models: dict[str, str | None],
    prices: dict[str, dict[str, float]],
) -> dict | None:
    """Evidence and cost of the customer turn that contains ``message_id``.

    Args:
        messages: The Leader session's messages, oldest first.
        message_id: Any message of the turn (usually the answer).
        leader_agent_id: Author of replies without ``team_agent_id``.
        models: Model name used by each agent id, for pricing.
        prices: Prices per 1M tokens, see :func:`model_prices`.

    Returns:
        ``None`` when ``message_id`` is not in ``messages``.
    """
    turn = turn_messages(messages, message_id)
    if turn is None:
        return None
    customer = turn[0] if turn and turn[0].role == "user" else None

    agents: dict[str, dict] = {}
    evidence: list[dict] = []
    for message in turn:
        if message.role != "assistant":
            continue
        agent_id = str(message.metadata.get("team_agent_id") or leader_agent_id)
        row = agents.setdefault(
            agent_id,
            {
                "agent_id": agent_id,
                "name": message.name,
                "model": models.get(agent_id),
                "replies": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_input_tokens": 0,
            },
        )
        row["replies"] += 1
        if message.usage is not None:
            row["input_tokens"] += message.usage.input_tokens
            row["output_tokens"] += message.usage.output_tokens
            row["cache_input_tokens"] += message.usage.cache_input_tokens
        blocks = message.get_content_blocks()
        results = {b.id: b for b in blocks if isinstance(b, ToolResultBlock)}
        for call in blocks:
            if not isinstance(call, ToolCallBlock) or call.name in _INTERNAL_TOOLS:
                continue
            result = results.get(call.id)
            evidence.append(
                {
                    "agent_id": agent_id,
                    "agent_name": message.name,
                    "tool": call.name,
                    "arguments": _arguments(call),
                    "state": str(result.state) if result is not None else "running",
                    "result": _result_text(result) if result is not None else "",
                    "at": (result.finished_at or result.created_at) if result is not None else call.created_at,
                },
            )

    totals = {"input_tokens": 0, "output_tokens": 0, "cache_input_tokens": 0}
    priced = bool(agents)
    total_cost = 0.0
    for row in agents.values():
        for key in totals:
            totals[key] += row[key]
        row["cost_usd"] = _cost(row, prices.get(row["model"] or ""))
        if row["cost_usd"] is None:
            priced = False
        else:
            total_cost += row["cost_usd"]
    last = turn[-1] if turn else None
    return {
        "turn": {
            "customer_message_id": customer.id if customer else None,
            "customer_text": customer_text(customer) if customer else "",
            "started_at": turn[0].created_at if turn else None,
            "ended_at": (last.finished_at or last.created_at) if last else None,
        },
        "agents": list(agents.values()),
        "totals": {**totals, "cost_usd": total_cost if priced else None, "priced": priced},
        "evidence": evidence,
    }


async def load_turn_messages(
    storage: StorageBase,
    user_id: str,
    session_id: str,
    message_id: str,
) -> list[Msg]:
    """Recent messages, paging back until the turn's customer message.

    The turn ends at the next customer message, so newer pages are always
    complete; older pages are read only until the start is reached.
    """
    pages: list[list[Msg]] = []
    before: str | None = None
    found = False
    for _ in range(_MAX_PAGES):
        page, has_more = await storage.list_messages(
            user_id, session_id, limit=_PAGE_SIZE, before=before,
        )
        if not page:
            break
        pages.append(page)
        if not found:
            found = any(message.id == message_id for message in page)
        if found:
            position = next(
                (i for i, m in enumerate(page) if m.id == message_id),
                len(page),
            )
            if any(m.role == "user" for m in page[: position + 1]) or not has_more:
                break
        if not has_more:
            break
        before = page[0].id
    return [message for page in reversed(pages) for message in page]
