"""The tools the model may call, and the rules each one enforces before touching the backend.

The model chooses a tool and its arguments; everything that matters is decided here or by the
backend: who the resident is (the delegation), which home and management unit (verified
context and routing), whether something is an emergency (request policy), and that a
conversation has one open request at a time.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from ..runtime.backend import BackendClient, OperationRejected, OperationUnknown

STATUS = {
    "open": "đã tiếp nhận, chờ Ban quản lý phân công", "triaging": "đang được phân loại",
    "assigned": "đã giao cho nhân viên", "in_progress": "đang được xử lý",
    "resolved": "đã xử lý xong, chờ bạn xác nhận", "closed": "đã hoàn tất", "cancelled": "đã hủy",
}


def _function(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}


SPECS = [
    _function("search_knowledge", "Tìm trong kho tri thức của Ban quản lý (nội quy, phí, tiện ích, thủ tục, số liên hệ). "
              "Trả về các đoạn văn có rank; chỉ được trả lời từ các đoạn này.",
              {"query": {"type": "string", "description": "Câu hỏi đầy đủ, viết có dấu, kèm tên khu/tòa nếu cư dân nêu."}}, ["query"]),
    _function("file_request", "Tạo yêu cầu gửi Ban quản lý cho một sự cố hoặc nhu cầu dịch vụ ĐÃ RÕ. "
              "Không dùng cho câu hỏi thông tin, lời chào, hay mô tả còn mơ hồ.",
              {"title": {"type": "string", "description": "Tiêu đề ngắn, ví dụ 'Vòi nước bếp bị rò'."},
               "description": {"type": "string", "description": "Những gì cư dân đã kể, không thêm suy đoán."},
               "category_code": {"type": "string", "description": "Một mã trong danh_muc_dich_vu."},
               "priority": {"type": "string", "enum": ["low", "normal", "high"]},
               "unit_code": {"type": "string", "description": "Chỉ cần khi cư dân có nhiều căn hộ."}},
              ["title", "description", "category_code", "priority"]),
    _function("report_emergency", "Báo khẩn cấp cho Ban quản lý khi có nguy hiểm cho người hoặc tòa nhà.",
              {"description": {"type": "string", "description": "Điều cư dân báo, nguyên văn ý chính."}}, ["description"]),
    _function("request_status", "Xem tình trạng yêu cầu đang mở của cuộc trò chuyện này.", {}, []),
    _function("cancel_request", "Gửi đề nghị hủy yêu cầu đang mở của cuộc trò chuyện này.",
              {"reason": {"type": "string"}}, ["reason"]),
    _function("ask_management", "Chuyển câu hỏi của cư dân tới Ban quản lý khi kho tri thức không có câu trả lời. "
              "Chỉ dùng cho câu hỏi về tòa nhà, dịch vụ, phí, quy định, thủ tục.", {}, []),
]


class Toolbox:
    """One resident turn. Collects what the tools returned, so the reply can be checked against it."""

    def __init__(self, backend: BackendClient, client: httpx.AsyncClient, knowledge_url: str | None,
                 context: dict, message: dict, open_request: dict | None, residence: dict, categories: list[dict]):
        self.backend, self.client, self.knowledge_url = backend, client, knowledge_url
        self.context, self.message, self.open_request = context, message, open_request
        self.residence, self.categories = residence, categories
        self.channel_id = context["channelId"]
        self.passages: dict[int, dict] = {}
        self.evidence: list[str] = []
        self.filed_code: str | None = None
        self.emergency = False
        self.status: str | None = None
        self.searched = self.forwarded = False

    @property
    def acted(self) -> bool:
        """Something reached management in this conversation: a request (now or earlier) or a forwarded question."""
        return bool(self.open_request or self.forwarded or self.emergency)

    def _key(self, step: str) -> str:
        return hashlib.sha256(f"{self.channel_id}\x1f{self.message['id']}\x1f{step}".encode()).hexdigest()

    async def _op(self, operation: str, value: dict, step: str) -> dict:
        return await self.backend.execute(self.context, operation, value, self._key(step))

    async def call(self, name: str, arguments: dict) -> dict:
        handler = getattr(self, "_" + name, None)
        try:
            if handler is None or name not in {spec["function"]["name"] for spec in SPECS}:
                return {"error": "unknown_tool"}
            result = await handler(**arguments)
        except TypeError:
            return {"error": "invalid_arguments"}
        except OperationRejected as error:
            result = {"error": "refused", "detail": str(error)}
        except (OperationUnknown, httpx.HTTPError):
            result = {"error": "unavailable"}
        self.evidence.append(str(result))
        return result

    async def _search_knowledge(self, query: str) -> dict:
        self.searched = True
        if not self.knowledge_url or not query.strip():
            return {"passages": [], "note": "Không có nguồn."}
        response = await self.client.post(
            self.knowledge_url.rstrip("/") + "/internal/knowledge/search", json={"query": query.strip()[:1000], "topK": 5},
            timeout=15, headers=self.backend.authorization(self.context))
        if response.status_code == 409:
            return {"passages": [], "note": "Cư dân có nhiều nơi ở; hỏi họ đang hỏi về căn nào."}
        response.raise_for_status()
        found = response.json()
        hits = [] if found.get("insufficientSources") else found.get("hits") or []
        for hit in hits:
            self.passages[hit["rank"]] = hit
        return {"passages": [{"rank": h["rank"], "title": h["title"], "text": h["text"], "unverified": h["unverified"]} for h in hits],
                **({} if hits else {"note": "Không có nguồn phù hợp."})}

    async def _file(self, title: str, description: str, category_id: str, assessment: dict, reason: str) -> dict:
        """Draft, place, describe, assess, route and hand over: the backend's order, in one step for the model."""
        home = self.residence
        draft = str((await self._op("create_ticket_draft", {
            "channel_id": self.channel_id, "client_message_id": "reception-draft:" + self._key("draft")[:40]}, "draft"))["draftId"])
        base = {"channel_id": self.channel_id, "draft_id": draft}
        await self._op("update_ticket_incident", {**base, "fields": {
            **{name: str(home[name]) for name in ("domain_id", "building_id", "unit_id")},
            "title": title.strip()[:300], "description": description.strip()[:10000], "category_id": category_id,
            "facts": [], "file_ids": self.message.get("fileIds", []), "source_message_id": self.message["id"]}}, "incident")
        await self._op("submit_ticket_assessment", {**base, "assessment": assessment}, "assessment")
        route = await self._op("resolve_management_destination", base, "route")
        if not route.get("managementUnitId"):
            return {"error": "no_management_unit", "note": "Chưa xác định được Ban quản lý phụ trách căn hộ này."}
        handoff = await self._op("handoff_ticket", {
            **base, "handoff_reason": reason, "correlation_id": self._key("handoff"), "plan_required": False}, "handoff")
        if handoff.get("accepted") is not True:
            raise OperationRejected("HANDOFF_REJECTED")
        self.filed_code = handoff["ticket"]["code"]
        self.open_request = {"id": str(handoff["ticket"]["id"]), "code": self.filed_code, "title": title, "status": "open"}
        return {"filed": True}

    def _home(self, unit_code: str | None) -> dict | None:
        homes = self.residence["homes"]
        named = [home for home in homes if unit_code and str(home["unit_code"]).lower() == unit_code.strip().lower()]
        chosen = named[0] if len(named) == 1 else homes[0] if len(homes) == 1 else None
        if chosen:
            self.residence = {**self.residence, **chosen}
        return chosen

    async def _file_request(self, title: str, description: str, category_code: str, priority: str,
                            unit_code: str | None = None) -> dict:
        if self.open_request:
            return {"error": "conversation_has_open_request",
                    "note": "Cuộc trò chuyện này đã có yêu cầu đang mở. Sự cố khác thì mời cư dân bấm 'Chat mới'."}
        if not title.strip() or not description.strip():
            return {"error": "title_and_description_required"}
        category = next((c for c in self.categories if c["code"] == category_code), None)
        if category is None or priority not in ("low", "normal", "high"):
            return {"error": "invalid_category_or_priority", "valid_codes": [c["code"] for c in self.categories]}
        if not self.residence["homes"]:
            return {"error": "no_verified_home", "note": "Tài khoản chưa có căn hộ được xác minh; mời cư dân liên hệ Ban quản lý."}
        if self._home(unit_code) is None:
            return {"error": "choose_home", "homes": [str(home["unit_code"]) for home in self.residence["homes"]]}
        return await self._file(title, description, str(category["id"]), {
            "priority": priority, "severity": "unknown", "is_emergency": False,
            "reason": "Đề xuất của lễ tân từ mô tả của cư dân."}, "needs_staff")

    async def _report_emergency(self, description: str) -> dict:
        # The backend's policy confirms; the model only raised it.
        policy = await self.backend.call("POST", "/internal/reception/policy/evaluate", self.context, {
            "message_text": self.message["text"], "assessment": {"proposed_action": "emergency_handoff"}})
        if policy.get("emergency") is not True:
            return {"error": "not_an_emergency_by_policy", "note": "Xử lý như một yêu cầu thường."}
        return await self.emergency_request(description)

    async def emergency_request(self, description: str) -> dict:
        """File at emergency level, or raise the conversation's open request. Used by policy and by the model."""
        self.emergency = True
        reason = description.strip()[:2000] or "Cư dân báo khẩn cấp."
        if not self.open_request:
            if not self.residence["homes"] or self._home(None) is None:
                return {"error": "no_single_verified_home"}
            category = next((c for c in self.categories if c["code"] == "technical"), self.categories[0])
            filed = await self._file(reason.split("\n")[0][:120], reason, str(category["id"]), {
                "priority": "critical", "severity": "critical", "is_emergency": True,
                "reason": "Policy xác nhận cần chuyển khẩn cấp."}, "emergency")
            if "error" in filed:
                return filed
        await self._op("escalate_emergency", {"ticket_id": self.open_request["id"], "reason": reason,
                                              "source_message_id": self.message["id"]}, "escalate")
        return {"emergency_reported": True}

    async def _request_status(self) -> dict:
        if not self.open_request:
            return {"error": "no_open_request"}
        status = (await self._op("get_ticket_status", {"ticket_id": self.open_request["id"]}, "status"))["ticket"]["status"]
        self.status = status
        return {"title": self.open_request["title"], "status": STATUS.get(status, "đang được xử lý")}

    async def _cancel_request(self, reason: str) -> dict:
        if not self.open_request:
            return {"error": "no_open_request"}
        submitted = self.open_request.get("submitted")
        if not submitted:
            # No Supervisor team received this request: only management can cancel it.
            return {"cancel": "needs_management", "note": "Đề nghị hủy được ghi trong hội thoại; Ban quản lý sẽ xem xét."}
        await self._op("request_ticket_cancellation", {"message": {
            **submitted, "message_id": "reception:" + self._key("cancel")[:48],
            "sent_at": datetime.now(timezone.utc).isoformat(), "message_type": "cancel_requested",
            "message": reason.strip()[:2000] or "Cư dân đề nghị hủy.", "source_message_id": self.message["id"],
            "ticket_version": str(self.open_request["version"]), "facts": [], "file_ids": []}}, "cancel")
        return {"cancel": "requested", "note": "Đã gửi đề nghị hủy; chưa phải là đã hủy."}

    async def _ask_management(self) -> dict:
        if not self.searched:
            # Only for an information question the knowledge base could not answer.
            return {"error": "search_knowledge_first",
                    "note": "Sự cố hay nhu cầu dịch vụ thì hỏi rõ rồi dùng file_request, không dùng công cụ này."}
        opened = await self.backend.call("POST", f"/internal/reception/chats/{self.channel_id}/inquiries", self.context,
                                         {"message_id": self.message["id"]})
        if opened.get("accepted") is True:
            self.forwarded = True
            return {"forwarded": True, "note": "Ban quản lý sẽ trả lời ngay trong cuộc trò chuyện này."}
        return {"forwarded": False, "note": "Chưa chuyển được; mời cư dân liên hệ trực tiếp Ban quản lý."}
