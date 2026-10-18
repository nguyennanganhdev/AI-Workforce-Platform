"""Backfill canonical Builder contracts from previously published proposals.

The command is dry-run by default. It only mutates an agent when a published
Builder proposal reproduces the agent's current objective, bindings, prompt,
skill and execution mode exactly.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from agentscope.app._router._workforce_console import (
    _BUILDER_ARTIFACT_SNAPSHOT_KEY,
    _BUILDER_BACKFILL_KEY,
    GeneratedAgent,
    PlannedAgent,
    ProposalView,
    ProposedAgentView,
    _artifact_snapshot,
    _existing_agent_covers,
    _record_contract_artifacts_match,
    _text_digest,
)
from agentscope.app.storage import AgentRecord, RedisStorage
from agentscope.app.workforce.builder import AgentBehaviorContract

sys.stdout.reconfigure(encoding="utf-8")

_BUILDER_AGENT_ID = "workforce-builder"
_USER_INDEX_PREFIX = "agentscope:user:"
_USER_INDEX_SUFFIX = ":agents"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist verified contracts. Without this flag, only report matches.",
    )
    parser.add_argument(
        "--user-id",
        action="append",
        default=[],
        help="Limit the operation to one user ID; may be passed more than once.",
    )
    parser.add_argument(
        "--synthesize-legacy",
        action="store_true",
        help=(
            "Create a conservative contract plus immutable artifact hashes when "
            "old proposals contain no contract."
        ),
    )
    return parser.parse_args()


def _tool_ids(record: AgentRecord) -> set[str]:
    return {
        str(binding.get("id") or "")
        or f"{binding.get('mcp_id', '')}:{binding.get('tool_name', '')}"
        for binding in record.data.tool_bindings
    }


def _contract_key(item: ProposedAgentView) -> str:
    assert item.behavior_contract is not None
    return item.behavior_contract.model_dump_json()


def _capability_key(value: str) -> str:
    if len(value) <= 190:
        return value
    return value[:120] + ":" + _text_digest(value)[:32]


def _canonical_contract(record: AgentRecord) -> AgentBehaviorContract | None:
    if not record.data.builder_contract:
        return None
    try:
        return AgentBehaviorContract.model_validate(record.data.builder_contract)
    except ValidationError:
        return None


def _synthesised_contract(record: AgentRecord) -> AgentBehaviorContract:
    tool_ids = sorted(_tool_ids(record))
    capabilities = [_capability_key(f"tool:{tool_id}") for tool_id in tool_ids] or [
        _capability_key(f"legacy-agent:{record.id}")
    ]
    objective = record.data.build_description.strip() or record.data.name
    action_terms = ("đặt", "booking", "hủy", "mua", "thanh toán")
    supports_action = bool(tool_ids) and any(
        term in objective.casefold() for term in action_terms
    )
    request_modes = ["advice"]
    if tool_ids:
        request_modes.append("lookup")
    if supports_action:
        request_modes.append("action")
    coordinator = "lập kế hoạch" in f"{record.data.name} {objective}".casefold()
    return AgentBehaviorContract.model_validate(
        {
            "requirement": {
                "agent_key": f"legacy-{record.id}",
                "business_profile": {
                    "profile_schema_version": "1",
                    "objective": objective,
                    "responsibilities": [
                        "Thực hiện đúng nghiệp vụ và phạm vi của agent đã phát hành",
                    ],
                    "capabilities": capabilities,
                    "input_contract": {"request": "string"},
                    "output_contract": {"result": "object"},
                    "business_scope": objective,
                    "required_constraints": [
                        "Giữ nguyên tool, prompt và skill đã được phát hành",
                    ],
                    "execution_policy": (
                        "require_approval" if supports_action else "read_only"
                    ),
                    "knowledge_requirements": [],
                },
                "capabilities": [
                    {
                        "capability": capability,
                        "required": True,
                        "reason": "Năng lực được backfill từ binding đã phát hành",
                    }
                    for capability in capabilities
                ],
                "effect": "external_operation" if supports_action else "read",
                "tracking_intent": "create_only",
            },
            "role": "coordinator" if coordinator else "specialist",
            "request_modes": request_modes,
            "deliverables": ["Kết quả nghiệp vụ theo objective đã phát hành"],
            "completion_criteria": [
                "Đã trả kết quả hợp lệ hoặc blocker cuối cùng cụ thể",
            ],
            "exclusions": ["Không mở rộng ngoài objective đã phát hành"],
            "operational_facts": [
                "Mọi dữ kiện vận hành phải có bằng chứng từ nguồn hợp lệ",
            ],
            "no_data_behavior": (
                "Nêu rõ không có dữ liệu và không tự suy diễn kết quả còn thiếu"
            ),
            "tool_error_behavior": (
                "Giữ kết quả hợp lệ, nêu lỗi tool và không lặp truy vấn không đổi"
            ),
            "partial_result_behavior": (
                "Trả phần đã xác minh và ghi rõ phần chưa thể hoàn thành"
            ),
            "customer_input_policy": (
                "Chỉ hỏi khách hàng về dữ kiện bắt buộc do khách hàng sở hữu"
            ),
            "peer_coordination_policy": (
                "Chỉ bàn giao dependency cho peer có năng lực phù hợp đã xác minh"
            ),
            "internal_reporting_policy": (
                "Báo cáo kết quả hoàn chỉnh cho reply owner hoặc người gọi trực tiếp"
            ),
            "synthesis_policy": (
                "Chỉ tổng hợp dữ liệu hợp lệ và công khai blocker còn tồn tại"
            ),
            "output_sections": ["Kết quả", "Bằng chứng", "Giới hạn"],
        },
    )


def _verify_backfill(record: AgentRecord) -> bool:
    if not record.data.builder_contract or record.data.execution_mode is None:
        return False
    contract = AgentBehaviorContract.model_validate(record.data.builder_contract)
    generated = GeneratedAgent(
        name=record.data.name,
        execution_mode=record.data.execution_mode,
        behavior_contract=contract,
        selected_tool_ids=sorted(_tool_ids(record)),
        selected_knowledge_base_ids=record.data.knowledge_base_ids,
    )
    if not _record_contract_artifacts_match(record, generated):
        return False
    selected_tools = sorted(_tool_ids(record))[::2]
    required_capabilities = [
        item.capability for item in contract.requirement.capabilities if item.required
    ]
    planned = PlannedAgent(
        name=record.data.name,
        objective=contract.requirement.business_profile.objective,
        required_capabilities=required_capabilities,
        request_modes=list(contract.request_modes),
        effect=contract.requirement.effect.value,
        suggested_tool_ids=selected_tools,
        suggested_knowledge_base_ids=record.data.knowledge_base_ids,
        reuse_agent_id=record.id,
    )
    return _existing_agent_covers(
        planned,
        record,
        _tool_ids(record),
        set(record.data.knowledge_base_ids),
    )


def _matches(record: AgentRecord, item: ProposedAgentView) -> bool:
    contract = item.behavior_contract
    if contract is None or item.reuse_agent_id is not None:
        return False
    return bool(
        record.source == "user"
        and record.data.system_role == "business"
        and record.data.lifecycle_state == "published"
        and record.data.name == item.name
        and record.data.build_description == item.objective
        and record.data.execution_mode == item.execution_mode
        and _tool_ids(record) == {tool.id for tool in item.selected_tools}
        and set(record.data.knowledge_base_ids)
        == {knowledge.id for knowledge in item.selected_knowledge_bases}
        and record.data.system_prompt == item.system_prompt
        and item.skill_markdown == record.data.generated_skill
        and item.evaluation.get("passed") is True
        and item.evaluation.get("contract_compiled") is True
        and (
            not record.data.builder_contract
            or record.data.builder_contract == contract.model_dump(mode="json")
        )
    )


def _mismatch_reasons(record: AgentRecord, item: ProposedAgentView) -> list[str]:
    contract = item.behavior_contract
    if contract is None:
        return ["missing_contract"]
    checks = {
        "reused_proposal": item.reuse_agent_id is None,
        "name": record.data.name == item.name,
        "objective": record.data.build_description == item.objective,
        "execution_mode": record.data.execution_mode == item.execution_mode,
        "tools": _tool_ids(record) == {tool.id for tool in item.selected_tools},
        "knowledge": set(record.data.knowledge_base_ids)
        == {knowledge.id for knowledge in item.selected_knowledge_bases},
        "record_prompt": record.data.system_prompt == item.system_prompt,
        "record_skill": item.skill_markdown == record.data.generated_skill,
        "evaluation": item.evaluation.get("passed") is True
        and item.evaluation.get("contract_compiled") is True,
        "contract": not record.data.builder_contract
        or record.data.builder_contract == contract.model_dump(mode="json"),
    }
    return [name for name, passed in checks.items() if not passed]


async def _user_ids(storage: RedisStorage, selected: list[str]) -> list[str]:
    if selected:
        return sorted(set(selected))
    client = storage.get_client()
    keys = client.scan_iter(match=f"{_USER_INDEX_PREFIX}*{_USER_INDEX_SUFFIX}")
    return sorted(
        {key[len(_USER_INDEX_PREFIX) : -len(_USER_INDEX_SUFFIX)] async for key in keys},
    )


async def _published_items(
    storage: RedisStorage,
    user_id: str,
) -> list[ProposedAgentView]:
    items: list[ProposedAgentView] = []
    sessions = await storage.list_sessions(user_id, _BUILDER_AGENT_ID)
    proposal_count = invalid_count = 0
    statuses: dict[str, int] = defaultdict(int)
    for session in sessions:
        messages, _has_more = await storage.list_messages(
            user_id,
            session.id,
            limit=10_000,
        )
        for message in messages:
            raw = (message.structured_output or {}).get(
                "workforce_builder_proposal",
            )
            if not raw:
                continue
            try:
                proposal = ProposalView.model_validate(raw)
            except ValueError:
                invalid_count += 1
                continue
            proposal_count += 1
            statuses[proposal.status] += 1
            if proposal.status in {"published", "ready"}:
                items.extend(proposal.agents)
    print(
        f"CATALOG user={user_id} sessions={len(sessions)} "
        f"proposals={proposal_count} invalid={invalid_count} "
        f"statuses={dict(statuses)} candidate_agents={len(items)}",
    )
    return items


async def _run(
    apply: bool,
    selected_users: list[str],
    synthesize_legacy: bool,
) -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    storage = RedisStorage(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
    )
    scanned = matched = updated = ambiguous = verified = 0
    async with storage:
        for user_id in await _user_ids(storage, selected_users):
            proposals = await _published_items(storage, user_id)
            by_name: dict[str, list[ProposedAgentView]] = defaultdict(list)
            for item in proposals:
                by_name[item.name].append(item)
            for record in await storage.list_agents(user_id):
                canonical = _canonical_contract(record)
                if canonical is not None and (
                    _BUILDER_ARTIFACT_SNAPSHOT_KEY in record.data.evaluation
                    or _BUILDER_BACKFILL_KEY in record.data.evaluation
                ):
                    if not _verify_backfill(record):
                        raise RuntimeError(
                            f"Backfill verification failed for agent {record.id}",
                        )
                    verified += 1
                    continue
                if record.data.execution_mode is None:
                    continue
                scanned += 1
                candidates = [
                    item for item in by_name[record.data.name] if _matches(record, item)
                ]
                unique = {_contract_key(item): item for item in candidates}
                if len(unique) > 1:
                    ambiguous += 1
                    print(
                        f"AMBIGUOUS user={user_id} agent={record.id} "
                        f"name={record.data.name!r}",
                    )
                    continue
                synthetic = False
                if len(unique) == 1:
                    item = next(iter(unique.values()))
                    assert item.behavior_contract is not None
                    contract = item.behavior_contract
                elif (
                    synthesize_legacy
                    and record.source == "user"
                    and record.data.system_role == "business"
                    and record.data.lifecycle_state == "published"
                ):
                    contract = _synthesised_contract(record)
                    synthetic = True
                else:
                    if not apply:
                        details = [
                            ",".join(_mismatch_reasons(record, item)) or "none"
                            for item in by_name[record.data.name]
                        ]
                        print(
                            f"SKIP user={user_id} agent={record.id} "
                            f"name={record.data.name!r} "
                            f"same_name_proposals={len(by_name[record.data.name])} "
                            f"reasons={details}",
                        )
                    continue
                matched += 1
                action = (
                    "BACKFILL-SYNTHETIC"
                    if apply and synthetic
                    else "SYNTHETIC-MATCH"
                    if synthetic
                    else "BACKFILL"
                    if apply
                    else "MATCH"
                )
                print(
                    f"{action} user={user_id} agent={record.id} "
                    f"name={record.data.name!r}",
                )
                if apply:
                    updated_record = record.model_copy(deep=True)
                    updated_record.data.builder_contract = contract.model_dump(
                        mode="json",
                    )
                    snapshot_key = (
                        _BUILDER_BACKFILL_KEY
                        if synthetic
                        else _BUILDER_ARTIFACT_SNAPSHOT_KEY
                    )
                    updated_record.data.evaluation = {
                        **updated_record.data.evaluation,
                        snapshot_key: _artifact_snapshot(
                            contract,
                            updated_record.data.system_prompt,
                            updated_record.data.generated_skill,
                        ),
                    }
                    if not _verify_backfill(updated_record):
                        raise RuntimeError(
                            f"Backfill verification failed for agent {record.id}",
                        )
                    await storage.upsert_agent(user_id, updated_record)
                    saved = await storage.get_agent(user_id, record.id)
                    if saved is None or not _verify_backfill(saved):
                        raise RuntimeError(
                            f"Backfill verification failed for agent {record.id}",
                        )
                    verified += 1
                    updated += 1
    mode = "apply" if apply else "dry-run"
    print(
        f"SUMMARY mode={mode} scanned={scanned} matched={matched} "
        f"updated={updated} verified={verified} ambiguous={ambiguous}",
    )
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(
        _run(args.apply, args.user_id, args.synthesize_legacy),
    )


if __name__ == "__main__":
    raise SystemExit(main())
