"""How much of each model call could come from the prompt cache.

Reads the requests fake_openai_room.py wrote (FAKE_MODEL_DUMP) and, per agent
(prompt_cache_key), measures the longest prefix each call shares with an
earlier call of that agent: the most the provider's prefix cache can serve.
A call that diverges before the previous call's last message (the volatile
tail: Shared Context packet, recall) is a cache break and is listed, unless it
diverges inside the system prompt's session notification (a new ticket).

    python prefix_report.py model-requests.jsonl

The prompt is rendered as tools then messages, an approximation of the
provider's layout. Cache steps: 2,048 tokens for gpt-5.5, else 1,024 then 128.
"""

import json
import sys
from collections import defaultdict

import tiktoken

sys.stdout.reconfigure(encoding="utf-8")
ENC = tiktoken.get_encoding("o200k_base")


def segments(request: dict) -> list[str]:
    parts = [json.dumps(request["tools"], ensure_ascii=False, sort_keys=True)]
    for message in request["messages"]:
        body = {k: message.get(k) for k in ("role", "name", "content", "tool_calls", "tool_call_id") if message.get(k)}
        parts.append(json.dumps(body, ensure_ascii=False, sort_keys=True))
    return parts


def common(a: list[str], b: list[str]) -> tuple[int, int]:
    """(whole segments in common, extra characters of the next segment)."""
    count = 0
    while count < min(len(a), len(b)) and a[count] == b[count]:
        count += 1
    if count < min(len(a), len(b)):
        x, y, chars = a[count], b[count], 0
        while chars < min(len(x), len(y)) and x[chars] == y[chars]:
            chars += 1
        return count, chars
    return count, 0


def tokens(parts: list[str], count: int, chars: int) -> int:
    text = "".join(parts[:count]) + (parts[count][:chars] if count < len(parts) else "")
    return len(ENC.encode(text))


def cacheable(prefix: int, model: str) -> int:
    if prefix < 1024:
        return 0
    step = 2048 if model.startswith("gpt-5.5") else 128
    return 1024 + (prefix - 1024) // step * step if step == 128 else prefix // step * step


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as dump:
        requests = [json.loads(line) for line in dump if line.strip()]
    seen: dict[str, list[list[str]]] = defaultdict(list)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # calls, input, shared prefix, cacheable
    breaks, new_sessions = [], 0
    for number, request in enumerate(requests, 1):
        key = request["key"] or request["role"]
        parts, earlier = segments(request), seen[key]
        total = tokens(parts, len(parts), 0)
        best, at = (0, 0), None
        for previous in earlier:
            match = common(previous, parts)
            if match > best:
                best, at = match, previous
        prefix = tokens(parts, *best)
        row = totals[f"{request['role']} {key}"]
        row[0] += 1
        row[1] += total
        row[2] += prefix
        row[3] += cacheable(prefix, request.get("model") or "")
        # Diverging before the earlier call's last message means something
        # already in the history (or the system prompt, or the tools) changed.
        if at is not None and best[0] < min(len(at) - 1, len(parts)):
            index, start = best[0], max(0, best[1] - 40)
            if index == 1 and "<system-notification>" in at[1][:best[1]]:
                new_sessions += 1  # a new ticket: its session id is the first difference
                earlier.append(parts)
                continue
            breaks.append(f"#{number} {request['role']} {key}: diverges at segment {index} of {len(at)} (0 = tools)\n"
                          f"    was: {at[index][start:best[1] + 120]!r}\n    now: {parts[index][start:best[1] + 120]!r}")
        earlier.append(parts)

    print(f"{'agent':<52} {'calls':>5} {'input':>8} {'shared':>8} {'cacheable':>9}")
    sums = [0, 0, 0, 0]
    for name, (calls, total, prefix, cached) in sorted(totals.items()):
        sums = [s + v for s, v in zip(sums, (calls, total, prefix, cached))]
        print(f"{name[:52]:<52} {calls:>5} {total:>8} {prefix / total:>7.0%} {cached / total:>8.0%}")
    print(f"{'all':<52} {sums[0]:>5} {sums[1]:>8} {sums[2] / sums[1]:>7.0%} {sums[3] / sums[1]:>8.0%}")
    print(f"\nnew sessions (diverged at the session notification, expected): {new_sessions}")
    print(f"cache breaks (diverged before the earlier call's volatile tail): {len(breaks)}")
    for line in breaks:
        print(line)


if __name__ == "__main__":
    main()
