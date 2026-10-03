"""Propose safety guidance for emergency replies from the knowledge folder, for management to approve.

    python scripts/propose_emergency_guidance.py <data-dir>     (DATABASE_URL = owner connection)

Reception answers an emergency with a fixed sentence. What the resident should do meanwhile is
safety advice, so no model writes it: it is the answer, word for word, that each area's own
`huong-dan-xu-ly-tinh-huong.md` gives to the matching question. It waits as a pending candidate
until management approves it in Operations ("Tri thức chờ duyệt"); only then does the request
policy hand it to Reception (v3_learning.approved_guidance).

Re-running is safe. An unchanged text is proposed once, whatever was decided about it. A changed
text is a new candidate, and the approved one stays in use until the new one is approved.
"""

import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import asyncpg

FILE = "huong-dan-xu-ly-tinh-huong.md"
# Emergency kind (v3_reception_runtime.EMERGENCY_KINDS) -> the question that answers it, and how
# management sees the kind. Kinds the documents do not cover get no guidance at all.
KINDS = {
    "fire": (re.compile(r"cháy", re.IGNORECASE), "cháy hoặc khói"),
    "gas": (re.compile(r"mùi gas", re.IGNORECASE), "mùi gas"),
    "elevator": (re.compile(r"thang.*kẹt|kẹt.*thang", re.IGNORECASE), "kẹt thang máy"),
}
SECTION = re.compile(r"^## \d+\.\s*(.+?)\s*\n+(.+?)(?=\n\s*\n|\n## |\Z)", re.MULTILINE | re.DOTALL)


def drafts(markdown: str) -> dict[str, tuple[str, str]]:
    """kind -> (question, answer) for the first question of each kind with a one-paragraph answer."""
    found: dict[str, tuple[str, str]] = {}
    for question, answer in SECTION.findall(markdown):
        answer = " ".join(answer.split())
        # A list or a lead-in to one is not a sentence to send in a chat reply.
        if answer.startswith(("-", "*", "|")) or answer.endswith(":"):
            continue
        # "Không. Anh chị đi thang bộ..." answers a yes/no question; the instruction is what follows.
        answer = re.sub(r"^(Không|Có)\.\s+", "", answer)
        for kind, (pattern, _) in KINDS.items():
            if kind not in found and pattern.search(question):
                found[kind] = (question, answer)
    return found


async def main(root: Path) -> None:
    db = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        for path in sorted(root.rglob(FILE)):
            if ".git" in path.parts:
                continue
            zone, source = path.parent.name, path.relative_to(root).as_posix()
            # The zone's scope, and the memory of the one management unit that covers the zone or
            # its buildings. Two units in one zone would each need their own text: nothing is proposed.
            targets = await db.fetch("""
                select a.tenant_id,a.id as scope_id,n.id as namespace_id from zones z
                join access_scopes a on a.tenant_id=z.tenant_id and a.kind='zone' and a.zone_id=z.id
                join access_scopes s on s.tenant_id=z.tenant_id and (s.kind='tenant'
                  or (s.kind='site' and s.site_id=z.site_id) or (s.kind='zone' and s.zone_id=z.id)
                  or (s.kind='building' and s.building_id in (select id from buildings where zone_id=z.id)))
                join management_coverage mc on mc.scope_id=s.id and mc.tenant_id=s.tenant_id
                  and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
                join workspaces w on w.management_unit_id=mc.management_unit_id and w.tenant_id=mc.tenant_id
                  and w.status='active'
                join memory_namespaces n on n.workspace_id=w.id and n.tenant_id=w.tenant_id
                  and n.kind='workspace' and n.status='active'
                where z.code=$1 group by a.tenant_id,a.id,n.id
            """, zone)
            if len(targets) != 1:
                print(f"skipped {source}: zone '{zone}' needs exactly one management workspace with memory, found {len(targets)}")
                continue
            target = targets[0]
            for kind, (question, answer) in drafts(path.read_text(encoding="utf-8")).items():
                digest = hashlib.sha256(answer.encode()).hexdigest()
                evidence = {"emergencyKind": kind, "answer": answer, "source": source, "sourceQuestion": question,
                            "question": f"Câu Lễ tân gửi kèm khi cư dân báo {KINDS[kind][1]}"}
                created = await db.fetchval("""
                    insert into memory_candidates(id,tenant_id,scope_id,namespace_id,proposed_text,evidence,
                      pii_redacted,status,reason,proposal_hash)
                    values ($1,$2,$3,$4,$5,$6::jsonb,false,'pending',$7,$8) on conflict (id) do nothing returning id
                """, uuid5(NAMESPACE_URL, f"emergency-guidance:{target['tenant_id']}:{target['scope_id']}:{kind}:{digest}"),
                    target["tenant_id"], target["scope_id"], target["namespace_id"], answer,
                    json.dumps(evidence, ensure_ascii=False),
                    f"Trích nguyên văn từ {source}, mục \"{question}\". Hướng dẫn an toàn: cần Ban quản lý duyệt.", digest)
                print(f"{'proposed' if created else 'unchanged'} {zone} {kind}")
    finally:
        await db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    asyncio.run(main(Path(sys.argv[1]).resolve()))
