"""Tools the Vinhomes agents use. They call the domain with the platform's own client secret.

Each result is short Vietnamese text that carries the codes and numbers an answer may quote:
the core turns every tool result into evidence, and its guard only lets an answer state a figure
that appears in the evidence it cites. No tool returns personal data of a resident (the domain
does not send any on these endpoints, and the tools do not ask for it).

  get_ticket        read the ticket of this case (everyone)
  search_knowledge  keyword search in the domain's knowledge pack (everyone)
  propose_plan      leader only: send a repair plan for management to decide (changes data)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from typing import Literal

from pydantic import Field

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk

from awp.guard import check_text, figures_missing
from awp.runtime import Binding, Runtime

from .client import Conflict, VinhomesClient, VinhomesError

log = logging.getLogger("awp.vinhomes")

MAX_HITS = 3
SNIPPET_BEFORE, SNIPPET_AFTER = 150, 450


def _ok(text: str) -> ToolChunk:
    return ToolChunk(content=[TextBlock(text=text)], state=ToolResultState.SUCCESS)


def _err(text: str) -> ToolChunk:
    return ToolChunk(content=[TextBlock(text=text)], state=ToolResultState.ERROR)


# ---- knowledge pack -----------------------------------------------------------
def fold(text: str) -> str:
    """Lower-case without accents, same length as `text` (so a match position maps back).
    People type Vietnamese with and without accents; matching ignores the difference."""
    out = []
    for ch in text:
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        out.append(("d" if base in ("đ", "Đ") else base[:1].lower()) if base else " ")
    return "".join(out)


def search_documents(documents: list[dict], query: str, limit: int = MAX_HITS) -> list[str]:
    """The best `limit` documents as one-paragraph hits. Whole words only; title matches count three times."""
    words = [w for w in re.findall(r"\w+", fold(query)) if len(w) > 1]
    patterns = [re.compile(r"\b" + re.escape(w) + r"\b") for w in words]
    scored = []
    for doc in documents:
        title, body = fold(doc.get("title", "")), fold(doc.get("body_md", ""))
        score = sum(3 * len(p.findall(title)) + min(len(p.findall(body)), 5) for p in patterns)
        if score:
            scored.append((score, doc, body))
    scored.sort(key=lambda s: -s[0])
    hits = []
    for _score, doc, body in scored[:limit]:
        text = doc.get("body_md", "")
        pos = min((m.start() for m in (p.search(body) for p in patterns) if m), default=0)
        snippet = re.sub(r"\s+", " ", text[max(0, pos - SNIPPET_BEFORE): pos + SNIPPET_AFTER]).strip()
        scope = doc.get("scope") or {}
        where = ", ".join(scope.get("zone_codes") or [])
        since = (doc.get("effective_from") or "")[:10]
        meta = ", ".join(x for x in (f"hiệu lực từ {since}" if since else "", f"khu {where}" if where else "") if x)
        hits.append(f"[{doc.get('id')}] {doc.get('title')} ({meta}): {snippet}" if meta
                    else f"[{doc.get('id')}] {doc.get('title')}: {snippet}")
    return hits


class Knowledge:
    """The domain's knowledge pack, kept for `ttl` seconds and refreshed with `since=<version>`
    (the domain answers "unchanged" without resending the documents)."""

    def __init__(self, client: VinhomesClient, ttl: float = 300.0) -> None:
        self.client, self.ttl = client, ttl
        self._cache: dict[str, tuple[float, str, list[dict]]] = {}

    async def documents(self, audience: str) -> list[dict]:
        hit = self._cache.get(audience)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[2]
        try:
            data = await self.client.knowledge_pack(audience, since=hit[1] if hit else None)
        except VinhomesError:
            if hit:  # an old pack is better than none; the next call tries again
                log.warning("knowledge pack refresh failed; using the copy from before")
                return hit[2]
            raise
        docs = hit[2] if (hit and data.get("unchanged")) else data.get("documents", [])
        self._cache[audience] = (time.monotonic(), data.get("version", ""), docs)
        return docs


# ---- what a ticket looks like to an agent ---------------------------------------
def describe_ticket(data: dict) -> str:
    """One paragraph. The status line is worded exactly as rules.py expects."""
    t, plan = data["ticket"], data.get("plan")
    due = lambda v: v or "chưa có"  # noqa: E731
    lines = [
        f"Yêu cầu {t['code']}. Trạng thái yêu cầu: {t['status']}. Phiên bản: {t['version']}. "
        f"Số lần mở lại: {t.get('reopen_count', 0)}. Ưu tiên: {t['priority']}. Mức độ: {t['severity']}. "
        f"Khẩn cấp: {'có' if t.get('is_emergency') else 'không'}. Loại: {t['request_kind']}. "
        f"Nhóm dịch vụ: {'đã phân loại' if t.get('category_id') else 'chưa phân loại'}. "
        f"Hạn phản hồi: {due(t.get('response_due_at'))}. Hạn xử lý: {due(t.get('resolution_due_at'))}."]
    lines.append(f"Phương án mới nhất: \"{plan['title']}\", trạng thái phương án: {plan['status']}."
                 if plan else "Chưa có phương án nào cho yêu cầu này.")
    return "\n".join(lines)


async def ticket_id_of(rt: Runtime, case_id: str) -> str:
    case = await rt.cases.get_case(case_id)
    return case["intake"]["attributes"]["ticket_id"]


def _explain(e: VinhomesError) -> str:
    if e.retryable:
        return f"Hệ thống Vinhomes tạm thời chưa trả lời ({e.status}). Có thể thử lại sau; nếu vẫn lỗi hãy ghi CaseGap."
    return f"Hệ thống Vinhomes từ chối ({e.status} {e.code}): {e.message}"


# ---- tools ---------------------------------------------------------------------
class _NoP(ParamsBase):
    pass


class _SearchP(ParamsBase):
    query: str = Field(description="Từ khóa cần tra, ví dụ 'giờ thi công', 'biểu phí gửi xe', 'cắt nước'.")
    audience: Literal["resident", "staff"] = Field(
        default="resident",
        description="resident: tài liệu cư dân được đọc (có thể trích dẫn). "
                    "staff: tài liệu nội bộ cho nhân viên, chỉ để hiểu quy trình, không trích nguyên văn cho cư dân.")


class _PlanP(ParamsBase):
    summary: str = Field(description="Tóm tắt phương án, tối đa 300 ký tự.")
    steps: list[str] = Field(description="1 đến 4 bước xử lý, mỗi bước một câu.")
    estimated_amount: int = Field(default=0, description="Chi phí dự kiến (đồng). Chỉ điền số có trong biểu phí hoặc tri thức; "
                                                         "không có thì để 0 để Ban quản lý báo giá.")
    cost_bearer: Literal["management", "resident", "warranty", "contractor"] = Field(
        default="resident", description="Ai chịu chi phí, chỉ đổi khi quy định nêu rõ.")
    requires_outage: bool = Field(default=False, description="Có cần cắt nước hoặc điện không.")
    estimated_duration_min: int | None = Field(default=None, description="Thời gian làm dự kiến (phút), nếu có căn cứ.")


class _DomainTool(ToolBase):
    is_read_only = True
    is_concurrency_safe = True

    def __init__(self, client: VinhomesClient, rt: Runtime, binding: Binding, knowledge: Knowledge) -> None:
        super().__init__()
        self.client, self.rt, self.b, self.knowledge = client, rt, binding, knowledge

    async def check_permissions(self, *args, **kwargs) -> PermissionDecision:
        # The profile's tool list is the gate; see ToolGateMiddleware in the core.
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="domain tool")


class GetTicket(_DomainTool):
    name = "get_ticket"
    description = ("Đọc yêu cầu của hồ sơ này từ hệ thống Vinhomes: mã, trạng thái hiện tại, ưu tiên, mức độ, hạn xử lý, "
                   "phương án mới nhất. Đây là nguồn duy nhất để biết việc đã xong hay chưa.")
    input_schema = _NoP.model_json_schema()

    async def call(self) -> ToolChunk:
        try:
            data = await self.client.get_case(await ticket_id_of(self.rt, self.b.case_id))
        except VinhomesError as e:
            return _err(_explain(e))
        return _ok(describe_ticket(data))


class SearchKnowledge(_DomainTool):
    name = "search_knowledge"
    description = ("Tra cẩm nang, quy định, biểu phí và thông báo đang có hiệu lực của Vinhomes theo từ khóa. "
                   "Trả tối đa 3 đoạn kèm tên tài liệu. Không thấy thì ghi CaseGap, không đoán.")
    input_schema = _SearchP.model_json_schema()

    async def call(self, query: str, audience: str = "resident") -> ToolChunk:
        try:
            docs = await self.knowledge.documents(audience if audience in ("resident", "staff") else "resident")
        except VinhomesError as e:
            return _err(_explain(e))
        hits = search_documents(docs, query)
        if not hits:
            return _ok(f"Không tìm thấy tài liệu nào khớp với '{query}' trong gói tri thức ({len(docs)} tài liệu).")
        return _ok("\n".join(hits))


class ProposePlan(_DomainTool):
    name = "propose_plan"
    description = ("Chỉ trưởng nhóm. Gửi phương án xử lý tới Ban quản lý để duyệt; sau đó cư dân phải đồng ý. "
                   "Phương án chưa có hiệu lực cho tới khi hai bên quyết định. Mỗi yêu cầu chỉ có một phương án đang chờ.")
    input_schema = _PlanP.model_json_schema()
    is_read_only = False
    is_concurrency_safe = False

    async def call(self, summary: str, steps: list[str], estimated_amount: int = 0,
                   cost_bearer: str = "resident", requires_outage: bool = False,
                   estimated_duration_min: int | None = None) -> ToolChunk:
        if self.b.role != "leader":
            return _err("Chỉ trưởng nhóm được gửi phương án.")
        steps = [s.strip() for s in steps if s and s.strip()]
        if not summary.strip() or not 1 <= len(steps) <= 4 or len(summary.strip()) > 300:
            return _err("Phương án cần tóm tắt (tối đa 300 ký tự) và từ 1 đến 4 bước.")
        # The same rule as every answer: a figure must come from evidence already in the case file.
        sources = [i.data.get("text", "") for i in await self.rt.cases.items(self.b.case_id, kinds=("evidence",))]
        problems = check_text(" ".join([summary, *steps]), sources, await self.rt.case_rules(self.b.case_id))
        if estimated_amount and figures_missing(str(estimated_amount), sources):
            problems.append(f"số tiền {estimated_amount} không có trong bằng chứng; để 0 nếu chưa có biểu phí")
        if problems:
            return _err("Chưa gửi: " + "; ".join(problems))

        body = {"summary": summary.strip(), "steps": steps, "estimated_amount": estimated_amount,
                "cost_bearer": cost_bearer, "requires_outage": requires_outage,
                "estimated_duration_min": estimated_duration_min}
        ticket_id = await ticket_id_of(self.rt, self.b.case_id)
        try:
            current = await self.client.get_case(ticket_id)  # the domain wants the version it has now
            # Same case and same content give the same key, so calling twice sends one plan.
            fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
            plan = await self.client.post_plan(
                ticket_id, {**body, "ticket_version": int(current["ticket"]["version"])},
                f"awp-plan-{self.b.case_id}-{fingerprint}")
        except Conflict as e:
            return _err(f"Chưa gửi được: {e.message}. Đọc lại yêu cầu bằng get_ticket rồi quyết định; không gửi lại y nguyên.")
        except VinhomesError as e:
            return _err(_explain(e))
        return _ok(f"Phương án đã được gửi tới Ban quản lý (mã {plan.get('id')}), trạng thái phương án: "
                   f"{plan.get('status')}. Chưa có hiệu lực cho tới khi Ban quản lý duyệt và cư dân đồng ý.")
