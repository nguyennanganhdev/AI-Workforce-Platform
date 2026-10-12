"""What a partner's MCP server said, as one of ok | pending | failed | unknown (spec 8, P0 item 17).

The rule behind every line: anything that may have reached the partner and has no clear answer is `unknown`
(never `failed`, never repeated); only an error that provably happened before the request left is `failed`.
The partner's own words are reduced before an agent reads them.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

import httpx
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult

from . import ssrf
from .common import opaque_id


OK, PENDING, FAILED, UNKNOWN = "ok", "pending", "failed", "unknown"

# Status words a partner may answer with, and what each means to us.
DONE_WORDS = {"confirmed", "completed", "complete", "done", "success", "succeeded"}
PENDING_WORDS = {"pending", "accepted", "queued", "processing", "in_progress"}
FAILED_WORDS = {"failed", "rejected", "declined", "error", "cancelled", "canceled"}
KNOWN_WORDS = DONE_WORDS | PENDING_WORDS | FAILED_WORDS
JOB_KEYS = ("external_job_id", "operation_id", "job_id", "id")
JOB_ID = re.compile(r"[A-Za-z0-9_.:-]{1,200}")  # the ids a model is shown; any other id is kept and compared, never shown

REQUEST_TIMEOUT = 408  # mcp.types.REQUEST_TIMEOUT: what the SDK raises when read_timeout_seconds passes
MAX_TEXT = 20000


@dataclass
class PartnerResult:
    outcome: str  # ok | pending | failed | unknown
    text: str  # what the agent may be shown, already merged with structuredContent and cleaned of errors' detail
    status: str | None = None  # the partner's own status word, lower case
    external_job_id: str | None = None
    error: str | None = None  # connect | timeout | session | tool_error | protocol | transport | auth | http | ...
    sent: bool | None = None  # False: provably not delivered; True: delivered; None: may have been
    elapsed: float = 0.0
    attempts: int = 1



class TooLarge(Exception):
    """The partner's answer is larger than the cap."""



def leaves(exc: BaseException) -> list[BaseException]:
    """Flatten ExceptionGroups (anyio task groups wrap the real error)."""
    if isinstance(exc, BaseExceptionGroup):
        out: list[BaseException] = []
        for e in exc.exceptions:
            out.extend(leaves(e))
        return out
    return [exc]


# ---- what the partner said -----------------------------------------------------------------------------------------
def merge_text(res: CallToolResult) -> str:
    """content + structuredContent as one text. FastMCP also copies a plain return into
    structuredContent={"result": text}: that is not shown twice."""
    text = "\n".join(b.text for b in res.content if getattr(b, "type", "") == "text")
    sc = res.structuredContent
    if sc is None:
        return text
    if isinstance(sc, dict) and set(sc) == {"result"} and str(sc["result"]) == text:
        return text
    if not text:
        return json.dumps(sc, ensure_ascii=False, sort_keys=True)
    try:
        if json.loads(text) == sc:
            return text
    except ValueError:
        pass
    return text + "\nstructuredContent: " + json.dumps(sc, ensure_ascii=False, sort_keys=True)


def partner_json(res: CallToolResult, text: str) -> dict | None:
    """The object that carries `status` and the job id: structuredContent first, else a JSON text block."""
    if isinstance(res.structuredContent, dict) and "status" in res.structuredContent:
        return res.structuredContent
    for candidate in (text, *(b.text for b in res.content if getattr(b, "type", "") == "text")):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I)
_PATH = re.compile(r"(?:[A-Za-z]:\\|/)(?:[\w.@-]+[\\/])+[\w.@-]*")
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_TOKEN = re.compile(r"\b(?:Bearer|Basic|ApiKey)\s+\S+|\b[A-Za-z0-9_\-+/=]{24,}\b", re.I)


def redact(text: str, secrets: tuple[str, ...]) -> str:
    """Our header values out of a partner's words, whole or in part: a partner that parsed `Bearer <token>` echoes
    the token alone."""
    pieces = {p for s in secrets for p in (s, *s.split()) if len(p) >= 8 or p == s and len(p) >= 4}
    for piece in sorted(pieces, key=len, reverse=True):
        text = text.replace(piece, "[redacted]")
    return text


def safe_error(text: str, secrets: tuple[str, ...] = ()) -> str:
    """The first line of a partner's error, without anything that reveals how its system or our setup looks:
    URLs, file paths, addresses, long tokens, and the values of our own headers."""
    line = redact(next((ln.strip() for ln in text.splitlines() if ln.strip()), ""), secrets)
    for pattern in (_URL, _PATH, _IP, _TOKEN):
        line = pattern.sub("[removed]", line)
    line = "".join(c for c in line if c.isprintable())
    return line[:200]


def normalize(res: CallToolResult, kind: str, tracking: str, secrets: tuple[str, ...] = ()) -> PartnerResult:
    """The partner answered. Pending is only `pending` when someone follows it (`tracking` events or status_query);
    an untracked action that answers pending is `unknown`, never done."""
    if res.isError:
        text = safe_error(merge_text(res), secrets)
        return PartnerResult(FAILED, text or "the partner reported an error", error="tool_error", sent=True)
    text = merge_text(res)[:MAX_TEXT]
    obj = partner_json(res, text)
    status = str(obj.get("status", "")).strip().lower() if obj else ""
    job = next((str(obj[k]) for k in JOB_KEYS if obj and obj.get(k) not in (None, "")), None)
    if job is not None and not opaque_id(job):
        job = None  # not an id (too long, or it has control characters)
    text = redact(text, secrets)  # a partner that echoes our header back does not get it into a model or a database
    base = dict(text=text, status=status[:40] or None, external_job_id=job, sent=True)  # kept in a 40-character column
    if kind == "lookup":
        return PartnerResult(OK, **base)  # a look-up changes nothing: whatever it answers is the answer, its own status words included
    if status in DONE_WORDS:
        return PartnerResult(OK, **base)
    if status in PENDING_WORDS:
        if tracking == "none":  # accepted, not finished, and nothing will tell us when it is: a person has to follow it
            return PartnerResult(UNKNOWN, **base, error="untracked")
        return PartnerResult(PENDING, **base)
    if status in FAILED_WORDS:
        return PartnerResult(FAILED, **base, error="rejected")
    return PartnerResult(UNKNOWN, **base, error="protocol")  # an action whose answer we cannot read may have happened


def classify_error(exc: BaseException, phase: str, kind: str) -> PartnerResult:
    """A transport or SDK exception as an outcome. `phase` is 'connect' (tools/call has not left) or 'call'."""
    errs = leaves(exc)
    first = errs[0]
    for e in errs:
        if isinstance(e, ssrf.Blocked):
            return PartnerResult(FAILED, "the partner's address is not allowed", error="blocked", sent=False)
        if isinstance(e, TooLarge):
            if kind == "lookup":
                return PartnerResult(FAILED, "the partner's answer was too large to read", error="too_large", sent=True)
            return PartnerResult(UNKNOWN, "the partner answered, but the answer was too large to read",
                                 error="too_large", sent=True)
        if isinstance(e, McpError):
            code = getattr(e.error, "code", None)
            if code == REQUEST_TIMEOUT:
                return PartnerResult(UNKNOWN, "no answer in time; the request may still be running at the partner",
                                     error="timeout", sent=True)
            if "Session terminated" in str(e):  # HTTP 404 for a session the server forgot: it did not run
                return PartnerResult(FAILED, "the partner session had expired; the request did not run",
                                     error="session", sent=False)
            return PartnerResult(FAILED, "the partner refused the request", error="protocol", sent=phase == "call")
    if isinstance(first, asyncio.CancelledError):
        # a cancel nobody asked for: the transport task group died under us; we cannot tell whether it was sent
        return PartnerResult(UNKNOWN if phase == "call" else FAILED, "the connection to the partner broke",
                             error="transport", sent=None if phase == "call" else False)
    for e in errs:
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            if code in (401, 403):  # the gateway refused our key before anything ran
                return PartnerResult(FAILED, f"the partner refused our credentials (HTTP {code})", error="auth",
                                     sent=False)
            if 300 <= code < 400:  # we never follow it off the origin; the endpoint did not handle the request
                return PartnerResult(FAILED, "the partner redirected the request elsewhere", error="redirect",
                                     sent=False)
            if phase == "call":  # 5xx on tools/call: the partner may have run it before failing
                return PartnerResult(UNKNOWN, f"the partner answered HTTP {code} to the request", error="http",
                                     sent=None)
    if phase == "connect":
        return PartnerResult(FAILED, "could not reach the partner; the request was not sent", error="connect",
                             sent=False)
    if isinstance(first, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
        return PartnerResult(UNKNOWN, "no answer in time; the request may still be running at the partner",
                             error="timeout", sent=True)
    return PartnerResult(UNKNOWN, "the connection broke while waiting for the answer", error="transport", sent=None)

