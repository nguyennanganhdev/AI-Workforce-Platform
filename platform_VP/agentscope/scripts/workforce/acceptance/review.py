"""Attach an independent judge's verdicts to an existing immutable run."""

import argparse
import hashlib
import json
from pathlib import Path

from .judge import digest, judge_evidence, read_json, score


def review(folder: Path, judge_report: dict) -> dict:
    report = read_json(folder / "report.json")
    index = []
    for scenario in report["scenarios"]:
        for run in scenario["runs"]:
            path = (folder / run["evidence_file"]).resolve()
            if folder.resolve() not in path.parents or digest(path) != run["evidence_sha256"]:
                raise ValueError("Run evidence is missing, changed or outside this run")
            problems = judge_evidence(read_json(path), scenario.get("expect", {}))
            if run["passed"] != (not problems) or run["problems"] != problems:
                raise ValueError("Saved verdict does not match the persisted evidence")
            index.append({"scenario": scenario["id"], "repeat": run["repeat"], "sha256": run["evidence_sha256"]})
    expected = hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest()
    if expected != report["evidence_index_sha256"]:
        raise ValueError("Run evidence index changed")
    return score(report, judge_report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--judge-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary = review(args.run, read_json(args.judge_report))
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
