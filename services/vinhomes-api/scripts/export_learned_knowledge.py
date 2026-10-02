"""Write approved learned answers into the knowledge folder, ready for publish.ts.

    python scripts/export_learned_knowledge.py <data-dir>     (DATABASE_URL = owner connection)

Each scope's approved answers become one file, `hoi-dap-ban-quan-ly.md`, in the folder that
scope is published from (site -> 00-do-thi, zone or building -> the folder with its code).
The files are rewritten in full every time, so approving, rejecting or revoking a candidate
and exporting again is all it takes; `server/src/knowledge/publish.ts` then ingests the change.
"""

import asyncio
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import asyncpg

FILE = "hoi-dap-ban-quan-ly.md"


def folder_for(root: Path, kind: str, code: str) -> Path | None:
    if kind == "site":
        return root / "00-do-thi"
    matches = [path for path in root.rglob(code) if path.is_dir() and ".git" not in path.parts]
    return matches[0] if len(matches) == 1 else None


def render(items: list[dict]) -> str:
    lines = ["---", f"cap_nhat: {date.today().isoformat()}", "nguon: Ban quản lý trả lời cư dân", "---", "",
             "# Hỏi đáp do Ban quản lý trả lời", ""]
    for number, item in enumerate(items, 1):
        lines += [f"## {number}. {item['question']}", "", item["answer"], ""]
    return "\n".join(lines)


async def main(root: Path) -> None:
    db = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        rows = await db.fetch("""
            select c.evidence->>'question' as question,c.evidence->>'answer' as answer,s.kind,
              coalesce(b.code,z.code,si.code) as code
            from memory_candidates c join access_scopes s on s.id=c.scope_id
            left join buildings b on b.id=s.building_id left join zones z on z.id=s.zone_id left join sites si on si.id=s.site_id
            where c.status='approved' and c.evidence ? 'sessionId' order by c.created_at
        """)
    finally:
        await db.close()
    by_folder: dict[Path, list[dict]] = defaultdict(list)
    for row in rows:
        folder = folder_for(root, row["kind"], row["code"])
        if folder is None:
            print(f"no folder for {row['kind']} {row['code']}: skipped")
            continue
        by_folder[folder].append(dict(row))
    # A folder whose answers were all withdrawn loses its file, so publish.ts retires the document.
    for stale in root.rglob(FILE):
        if stale.parent not in by_folder:
            stale.unlink()
            print(f"removed {stale.relative_to(root)}")
    for folder, items in by_folder.items():
        (folder / FILE).write_text(render(items), encoding="utf-8")
        print(f"wrote {(folder / FILE).relative_to(root)}: {len(items)} answers")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    asyncio.run(main(Path(sys.argv[1]).resolve()))
