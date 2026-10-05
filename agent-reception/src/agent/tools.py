"""The tools the model may call, and the rules each one enforces before touching the backend.

The model chooses a tool and its arguments; everything that matters is decided here or by the
backend: who the resident is (the delegation), which home and management unit (verified
context and routing), whether something is an emergency (request policy), what a request says
(the resident's own words, chosen by the backend's intake rules), whether it is complete enough
to hand over, and that a conversation has one open request at a time.
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
    _function("file_request", "Tạo yêu cầu gửi Ban quản lý cho một sự cố hoặc nhu cầu dịch vụ. Mỗi ô chi tiết là NGUYÊN VĂN "
              "một cụm từ cư dân đã viết: chép y nguyên, không diễn đạt lại, không thêm. Hệ thống ghi lời cư dân vào yêu cầu "
              "và tự hỏi lại cư dân khi còn thiếu chi tiết. Không dùng cho câu hỏi thông tin hay lời chào.",
              {"symptom": {"type": "string", "description": "Hiện tượng hoặc nhu cầu, nguyên văn. Cư dân viết 'vòi bếp bị rò nước' thì ghi 'bị rò nước'."},
               "area": {"type": "string", "description": "Khu vực cư dân nêu, nguyên văn, ví dụ 'nhà tắm'. Bỏ trống nếu chưa nêu."},
               "item": {"type": "string", "description": "Thiết bị, vật hoặc điểm cụ thể bị ảnh hưởng, nguyên văn, ví dụ 'chân vòi lavabo'. "
                                                         "Bỏ trống nếu cư dân chưa nêu; không tự suy ra."},
               "item_unknown": {"type": "string", "description": "Chỉ khi cư dân nói họ không biết hoặc chưa xác định được vật hay điểm cụ thể: "
                                                                 "chép nguyên văn câu đó."},
               "kind": {"type": "string", "enum": ["incident", "service_request"],
                        "description": "incident: có thứ hỏng hoặc bất thường. service_request: cần một dịch vụ."},
               "category_code": {"type": "string", "description": "Một mã trong danh_muc_dich_vu."},
               "priority": {"type": "string", "enum": ["low", "normal", "high"]},
               "unit_code": {"type": "string", "description": "Chỉ cần khi cư dân có nhiều căn hộ."}},
              ["symptom", "kind", "category_code", "priority"]),
    _function("report_emergency", "Báo khẩn cấp cho Ban quản lý khi có nguy hiểm cho người hoặc tòa nhà. "
              "Yêu cầu ghi nguyên văn tin nhắn của cư dân.", {}, []),
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
        # `emergency` only once management was reached; `emergency_failed` when it could not be.
        self.emergency = self.emergency_failed = False
        # The intake rules' question for the resident. Once set, the turn ends with it.
        self.question: str | None = None
        self.clarification: str | None = None
        self.filings = 0
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

    async def _step(self, operation: str, value: dict, step: str) -> dict:
        # A second filing in the same turn has other content: it needs its own key, or the backend refuses the reuse.
        return await self._op(operation, value, step if self.filings <= 1 else f"{step}:{self.filings}")

    async def call(self, name: str, arguments: dict) -> dict:
        handler = getattr(self, "_" + name, None)
        if self.question:
            # A detail is missing and the resident is being asked: no other tool hands the request over instead.
            return {"error": "waiting_for_resident"}
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

    async def _intake(self, details: dict, kind: str, emergency: bool = False) -> dict:
        """What the backend would record for these details, and its question when one is missing."""
        return await self.backend.call("POST", f"/internal/reception/chats/{self.channel_id}/intake", self.context, {
            "message_id": self.message["id"], "details": details, "kind": kind, "emergency": emergency})

    async def _file(self, report: dict, kind: str, category_id: str, assessment: dict, reason: str) -> dict:
        """Draft, place, describe, assess, route and hand over: the backend's order, in one step for the model."""
        home = self.residence
        self.filings += 1
        draft = str((await self._op("create_ticket_draft", {
            "channel_id": self.channel_id, "client_message_id": "reception-draft:" + self._key("draft")[:40]}, "draft"))["draftId"])
        base = {"channel_id": self.channel_id, "draft_id": draft}
        # Title, description and photos are the backend's: it takes them from the resident's messages the facts cite.
        await self._step("update_ticket_incident", {**base, "fields": {
            **{name: str(home[name]) for name in ("domain_id", "building_id", "unit_id")},
            "category_id": category_id, "request_kind": kind, "facts": report["facts"],
            "source_message_id": self.message["id"]}}, "incident")
        await self._step("submit_ticket_assessment", {**base, "assessment": assessment}, "assessment")
        route = await self._step("resolve_management_destination", base, "route")
        if not route.get("managementUnitId"):
            return {"error": "no_management_unit",
                    "note": "Danh mục này chưa có Ban quản lý phụ trách cho căn hộ; thử mã danh mục khác nếu phù hợp."}
        handoff = await self._step("handoff_ticket", {
            **base, "handoff_reason": reason, "correlation_id": self._key("handoff"), "plan_required": False}, "handoff")
        if handoff.get("accepted") is not True:
            missing = handoff.get("missingFields") or []
            if any(str(name).startswith("verified_resident") for name in missing):
                return {"error": "resident_profile_incomplete",
                        "note": "Hồ sơ cư dân thiếu họ tên hoặc số điện thoại; mời cư dân cập nhật hồ sơ rồi báo lại."}
            return {"error": "handoff_refused", "missing": missing}
        self.filed_code = handoff["ticket"]["code"]
        self.open_request = {"id": str(handoff["ticket"]["id"]), "code": self.filed_code, "title": report["title"], "status": "open"}
        return {"filed": True}

    def _home(self, unit_code: str | None) -> dict | None:
        homes = self.residence["homes"]
        named = [home for home in homes if unit_code and str(home["unit_code"]).lower() == unit_code.strip().lower()]
        chosen = named[0] if len(named) == 1 else homes[0] if len(homes) == 1 else None
        if chosen:
            self.residence = {**self.residence, **chosen}
        return chosen

    async def _file_request(self, symptom: str, kind: str, category_code: str, priority: str, area: str | None = None,
                            item: str | None = None, item_unknown: str | None = None, unit_code: str | None = None) -> dict:
        if self.open_request:
            return {"error": "conversation_has_open_request",
                    "note": "Cuộc trò chuyện này đã có yêu cầu đang mở. Sự cố khác thì mời cư dân bấm 'Chat mới'."}
        category = next((c for c in self.categories if c["code"] == category_code), None)
        if category is None or priority not in ("low", "normal", "high") or kind not in ("incident", "service_request"):
            return {"error": "invalid_category_priority_or_kind", "valid_codes": [c["code"] for c in self.categories]}
        if not self.residence["homes"]:
            return {"error": "no_verified_home", "note": "Tài khoản chưa có căn hộ được xác minh; mời cư dân liên hệ Ban quản lý."}
        if self._home(unit_code) is None:
            return {"error": "choose_home", "homes": [str(home["unit_code"]) for home in self.residence["homes"]]}
        details = {key: value.strip() for key, value in (
            ("symptom", symptom), ("area", area), ("item", item), ("item_unknown", item_unknown)) if value and value.strip()}
        report = await self._intake(details, kind)
        if not report["ready"]:
            # The backend's question goes to the resident as it is; nothing is handed over this turn.
            self.question = report["question"]
            self.clarification = report["missing"] if report["missing"] in ("symptom", "item") else "symptom"
            return {"error": "needs_clarification", "not_in_the_residents_words": report["rejected"]}
        return await self._file(report, kind, str(category["id"]), {
            "priority": priority, "severity": "unknown", "is_emergency": False,
            "reason": "Cư dân chưa nêu được vật hoặc vị trí cụ thể sau hai lần hỏi; cần người kiểm tra." if report["review"]
            else "Đề xuất của lễ tân từ mô tả của cư dân."}, "needs_staff")

    async def _report_emergency(self) -> dict:
        # The model may raise an emergency the keywords missed; the backend's policy answers for it.
        policy = await self.backend.call("POST", "/internal/reception/policy/evaluate", self.context, {
            "message_text": self.message["text"], "assessment": {"proposed_action": "emergency_handoff"}})
        if policy.get("emergency") is not True:
            return {"error": "not_an_emergency_by_policy", "note": "Xử lý như một yêu cầu thường."}
        return await self.emergency_request()

    async def emergency_request(self) -> dict:
        """File at emergency level, or raise the conversation's open request. Used by policy and by the model.

        `emergency` is set only when management was reached: the resident is never told so otherwise.
        """
        try:
            outcome = await self._raise_emergency()
        except (OperationRejected, OperationUnknown, httpx.HTTPError):
            outcome = {"error": "unavailable"}
        self.emergency, self.emergency_failed = "error" not in outcome, "error" in outcome
        return outcome

    async def _raise_emergency(self) -> dict:
        reason = self.message["text"].strip()[:2000] or "Cư dân báo khẩn cấp."
        if not self.open_request:
            homes = self.residence["homes"]
            if not homes:
                return {"error": "no_verified_home"}
            several = self._home(None) is None
            if several:
                # An emergency is not held back to ask which home: management confirms it with the resident.
                self.residence = {**self.residence, **homes[0]}
            category = next((c for c in self.categories if c["code"] == "technical"), self.categories[0])
            filed = await self._file(await self._intake({}, "incident", emergency=True), "incident", str(category["id"]), {
                "priority": "critical", "severity": "critical", "is_emergency": True,
                "reason": "Policy xác nhận cần chuyển khẩn cấp." + (
                    " Cư dân có nhiều căn hộ: cần xác nhận căn đang gặp sự cố." if several else "")}, "emergency")
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
