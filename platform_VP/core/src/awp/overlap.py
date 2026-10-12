"""How much two agent profiles do the same work: a number that depends on nothing but their text.

This is the hard gate of the builder (a model's opinion that two agents overlap is only advice): the words of
`handles` and `mission`, lower-cased, without Vietnamese marks, without the words every profile uses, compared as
sets (Jaccard). Two scores are taken and the higher one counts: all the words, and the words of `handles` alone.
`handles` is the list of work an agent takes, so two agents with the same handles do the same work however their
missions are worded; in one score over everything the mission's words would dilute that. The same two profiles
always get the same score, so the gate can be tested and explained: the result names the words they share.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Words that say nothing about what an agent handles: articles and glue (English, Vietnamese without marks), and
# the words every mission is written with.
STOP = frozenset("""
a an the and or of to for in on at by with from as is are be this that it its who which what when all any each every
agent assistant specialist leader team handles handle handling help helps about into their them you your our we i
la va cua cho cac nhung mot trong khi voi duoc de tu tai ve theo co khong nay do thi ma se da dang hay hoac nhu
chuyen vien tro ly xu viec yeu cau nguoi
""".split())
_WORD = re.compile(r"[a-z0-9]+")


def normalise(text: str) -> str:
    """Lower case, no marks: "Sửa Ống Nước" and "sua ong nuoc" are the same words."""
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokens(*texts: str | Iterable[str]) -> frozenset[str]:
    """The words that tell one agent's work from another's."""
    flat = [t for x in texts for t in ([x] if isinstance(x, str) else x)]
    words = _WORD.findall(normalise(" ".join(flat)))
    return frozenset(w for w in words if len(w) > 1 and w not in STOP)


def _get(profile, name: str):
    return profile.get(name) if isinstance(profile, dict) else getattr(profile, name, None)


def profile_tokens(profile) -> frozenset[str]:
    """`profile`: an AgentProfile, or a dict with `mission` and `handles`."""
    return tokens(_get(profile, "mission") or "", _get(profile, "handles") or [])


def score(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard: shared words over all words. Two empty sets share nothing."""
    return len(a & b) / len(a | b) if a and b else 0.0


def compare(a, b) -> tuple[float, frozenset[str]]:
    """(score, shared words) of two profiles: the higher of all their words and their handles alone."""
    whole = (profile_tokens(a), profile_tokens(b))
    handles = (tokens(_get(a, "handles") or []), tokens(_get(b, "handles") or []))
    best = max(whole, handles, key=lambda pair: score(*pair))
    return score(*best), best[0] & best[1]


def overlaps(candidate, existing: dict[str, object]) -> list[dict]:
    """`candidate` against each existing agent (key -> its profile, or its profiles when a published version and a
    newer draft both count: the highest score is the key's), highest score first; zero scores are left out. Each
    entry says with whom, how much and through which words."""
    out = []
    for key, others in existing.items():
        s, shared = max((compare(candidate, o) for o in (others if isinstance(others, (list, tuple)) else [others])),
                        key=lambda found: found[0], default=(0.0, frozenset()))
        if s > 0:
            out.append({"key": key, "score": round(s, 3), "shared": sorted(shared)})
    return sorted(out, key=lambda o: (-o["score"], o["key"]))
