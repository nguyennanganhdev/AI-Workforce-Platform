"""Offline, held-out recall and paired task ablation; never uses a live DB.

The task solver is deterministic and requires a retrieved source. These are
retrieval/grounding outcomes, not proof of improvement in resident tickets.
"""
import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile

from agentscope.app._agent_memory import AgentMemoryService
from agentscope.app.storage import AgentMemoryRecord, AsyncSQLAlchemyStorage


async def evaluate(cases):
    with tempfile.TemporaryDirectory(prefix="awp-memory-eval-") as directory:
        storage = AsyncSQLAlchemyStorage(f"sqlite+aiosqlite:///{Path(directory)/'recall.db'}", create_tables=True)
        await storage.__aenter__()
        try:
            memory = AgentMemoryService(storage)
            for row in cases["memories"]:
                content = row["content"]
                item = AgentMemoryRecord(id=row["id"], user_id=row["owner"], agent_id=row["agent"],
                    content=content, kind="lesson", source_ticket=row["source_ticket"], source_event_ids=["fixture-verified-source"],
                    expires_at=datetime.now(UTC)+timedelta(days=row.get("ttl_days", 14)),
                    provenance={"policy":"agent-memory-evidence-v2","supported":True,"safe_to_transfer":True,
                                "content_sha256":hashlib.sha256(content.encode()).hexdigest()} if row.get("verified", True) else {})
                await storage.upsert_agent_memory(row["owner"], item)
            results = []
            for case in cases["cases"]:
                selected = await memory.recall(case["owner"], case["agent"], case["query"], ticket=case["ticket"], limit=3)
                ids = {item.id for item in selected}
                gold = set(case["expected_memory_ids"])
                # Same solver in both arms: answer only when a cited procedure
                # contains the held-out task's required action; otherwise abstain.
                treatment = bool(gold & ids) if gold else not ids
                baseline = not gold
                contaminated = bool(ids - set(case.get("allowed_memory_ids", case["expected_memory_ids"])))
                results.append({"case_id":case["id"],"retrieved_ids":sorted(ids),"expected_ids":sorted(gold),
                                "without_memory_outcome":baseline,"with_memory_outcome":treatment and not contaminated,
                                "contamination":contaminated})
            n = len(results)
            baseline = sum(r["without_memory_outcome"] for r in results)/n
            treatment = sum(r["with_memory_outcome"] for r in results)/n
            return {"environment":"offline_disposable_sqlite","benchmark":"recall_grounding_regression_ablation_v1",
                    "solver":"deterministic_evidence_required","business_outcome_verified":False,
                    "cases":n,"without_memory_success_rate":baseline,"with_memory_success_rate":treatment,
                    "paired_delta":treatment-baseline,"contaminated_cases":sum(r["contamination"] for r in results),
                    "results":results,"dataset_sha256":hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest()}
        finally:
            await storage.__aexit__(None,None,None)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=asyncio.run(evaluate(json.loads(args.cases.read_text(encoding="utf-8"))))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))
    raise SystemExit(result['contaminated_cases']>0 or result['with_memory_success_rate']<1)
