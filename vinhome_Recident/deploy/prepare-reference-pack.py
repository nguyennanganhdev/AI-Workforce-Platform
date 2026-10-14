"""Compile the sourced public reference JSON to the Domain knowledge loader format. Does not publish or call a model."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5


def compile_records(rows):
    documents = []
    codes = set()
    for row in rows:
        if (
            row["site_code"] not in {"ocean-park-1", "ocean-park-2", "ocean-park-3"}
            or row["authority"] != "reference"
        ):
            raise SystemExit(
                "Only explicitly scoped public reference records are accepted."
            )
        if not row["sources"] or any(
            urlsplit(u).scheme != "https"
            or not (
                (urlsplit(u).hostname or "") == "vinhomes.vn"
                or (urlsplit(u).hostname or "").endswith(".vinhomes.vn")
            )
            for u in row["sources"]
        ):
            raise SystemExit(
                "Each record requires an official HTTPS Vinhomes source URL."
            )
        # Old packs keep the same document IDs. New catalog entries need their own stable key.
        record_code = row.get("record_code", "amenities")
        if not record_code or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-/" for c in record_code
        ):
            raise ValueError("Invalid public record code.")
        code = "public/" + row["site_code"] + "/" + record_code
        if code in codes:
            raise ValueError("Duplicate public record code.")
        codes.add(code)
        document = uuid5(NAMESPACE_URL, "vinhomes-public-reference:" + code)
        version = uuid5(
            document,
            hashlib.sha256(
                json.dumps(row, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
        )
        documents.append(
            {
                "id": str(document),
                "version_id": str(version),
                "code": code,
                "site": row["site_code"],
                "title": row["title"],
                "category": row.get("category", "public-amenity-reference"),
                "audience": "resident",
                "zone": None,
                "buildings": [],
                "unverified": True,
                "metadata": {
                    "sources": row["sources"],
                    "source_published_at": row["source_published_at"],
                    "retrieved_at": row["retrieved_at"],
                    "source_kind": "official_public_reference",
                    "operational_approval": "pending",
                    "catalog_kind": row.get("kind", "amenity"),
                    "official_code": row.get("official_code"),
                    "fee_policy": None,
                    "operating_hours": None,
                    "operator": None,
                    "booking_policy": None,
                    "cancellation_policy": None,
                },
                "chunks": [
                    {
                        "id": str(uuid5(document, "intro")),
                        "ordinal": 0,
                        "heading_path": row["title"],
                        "text": row["body"],
                        "token_count": len(row["body"].split()),
                    }
                ],
            }
        )
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    documents = compile_records(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        gzip.compress(
            (
                "\n".join(
                    json.dumps(d, ensure_ascii=False, sort_keys=True) for d in documents
                )
                + "\n"
            ).encode(),
            mtime=0,
        )
    )
    print(
        json.dumps(
            {
                "documents": len(documents),
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "status": "reference",
            }
        )
    )


if __name__ == "__main__":
    main()
