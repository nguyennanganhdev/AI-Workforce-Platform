"""One resident turn of the model-led agent: tool calls, then a reply checked against evidence."""

from __future__ import annotations

import json
import re

from .tools import SPECS, Toolbox

MAX_STEPS = 6
EMERGENCY_REPLY = "Mình đã chuyển yêu cầu của bạn đến Ban quản lý ở mức khẩn cấp."
SAFE_REPLY = ("Mình chưa có thông tin chính thức về việc này. Bạn nhắn lại giúp mình nội dung cần hỗ trợ, "
              "hoặc mình có thể chuyển câu hỏi tới Ban quản lý.")
INTERNAL = re.compile(r"\b(ticket|backend|supervisor|tool|system prompt)\b", re.IGNORECASE)
# Things only the backend can establish. Allowed in a reply only when a tool said so this turn.
DONE_CLAIMS = ("đã hoàn tất", "đã xử lý xong", "đã sửa xong", "đã được hủy", "đã hủy xong")
PROMISES = ("đang trên đường", "sẽ đến trong", "sẽ có mặt trong", "miễn phí", "trong vòng")
# Saying something was recorded or passed on is only true when a tool did it, or when the
# conversation already has an open request that management reads.
ACTION_CLAIMS = ("đã ghi nhận", "đã chuyển", "sẽ chuyển", "đã gửi", "đã báo", "đã tiếp nhận", "ghi nhận và")
FIGURE = re.compile(r"\d[\d .,:]*\d|\d")


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def violations(reply: str, toolbox: Toolbox, conversation: str) -> list[str]:
    """Why a reply may not be sent. Empty when it says nothing beyond its evidence."""
    problems = []
    if INTERNAL.search(reply):
        problems.append("dùng từ nội bộ (ticket, backend, Supervisor, tool)")
    lowered = reply.lower()
    if toolbox.status not in ("closed", "resolved", "cancelled") and any(claim in lowered for claim in DONE_CLAIMS):
        problems.append("khẳng định yêu cầu đã xong hoặc đã hủy khi hệ thống chưa xác nhận")
    if not toolbox.acted and any(claim in lowered for claim in ACTION_CLAIMS):
        problems.append("nói đã ghi nhận hoặc đã chuyển cho Ban quản lý nhưng chưa gọi công cụ nào làm việc đó")
    evidence = " ".join(toolbox.evidence).lower()
    if any(promise in lowered and promise not in evidence for promise in PROMISES):
        problems.append("hứa thời gian, việc nhân viên đến hoặc miễn phí mà không có căn cứ")
    # Every figure (fee, phone number, hour, date) must come from a tool result or from the resident.
    known = _digits(evidence + " " + conversation)
    for figure in FIGURE.findall(reply):
        number = _digits(figure)
        if len(number) >= 2 and number not in known:
            problems.append(f"nêu con số '{figure.strip()}' không có trong nguồn")
            break
    return problems


def _final(content: str | None) -> tuple[str, list[int]] | None:
    try:
        value = json.loads(content or "")
        reply, sources = value["reply"], value.get("sources") or []
        if isinstance(reply, str) and reply.strip() and isinstance(sources, list):
            return reply.strip(), [rank for rank in sources if isinstance(rank, int)]
    except (ValueError, KeyError, TypeError):
        pass
    return None


async def run_agent(model, toolbox: Toolbox, system: str, history: list[dict]) -> str:
    """The reply for the last resident message in `history`."""
    # Earlier replies are shown in the same JSON shape the model must answer in.
    messages = [{"role": "system", "content": system}] + [
        {"role": "user", "content": item["text"]} if item["role"] == "resident"
        else {"role": "assistant", "content": json.dumps({"reply": item["text"], "sources": []}, ensure_ascii=False)}
        for item in history]
    # What the reply may rely on besides tool results: the resident's words and the backend's facts.
    conversation = " ".join(item["text"] for item in history) + " " + system
    retried = False
    for _ in range(MAX_STEPS):
        answer = await model.complete(messages, SPECS)
        calls = answer.get("tool_calls") or []
        if calls:
            messages.append({"role": "assistant", "content": answer.get("content"), "tool_calls": calls})
            for call in calls:
                try:
                    arguments = json.loads(call["function"]["arguments"] or "{}")
                except ValueError:
                    arguments = None
                result = await toolbox.call(call["function"]["name"], arguments) if isinstance(arguments, dict) \
                    else {"error": "invalid_arguments"}
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
            if toolbox.emergency:
                # An emergency is acknowledged with the fixed sentence; it does not wait for wording.
                return EMERGENCY_REPLY
            continue
        final = _final(answer.get("content"))
        problems = ["không đúng định dạng JSON {reply, sources}"] if final is None else violations(final[0], toolbox, conversation)
        if not problems:
            reply, sources = final
            # A question handed to management was not answered from the passages, whatever the model lists.
            used = [] if toolbox.forwarded else [toolbox.passages[rank] for rank in sources if rank in toolbox.passages]
            if not used and not toolbox.forwarded:
                # The model forgot to name its sources: a figure in the reply still shows where it came from.
                figures = [_digits(figure) for figure in FIGURE.findall(reply) if len(_digits(figure)) >= 2]
                used = [p for p in toolbox.passages.values() if any(f in _digits(p["text"]) for f in figures)]
            # Three titles are enough to show where an answer comes from.
            titles = list(dict.fromkeys(str(passage["title"]) for passage in used))[:3]
            return reply + ("\n(Nguồn: " + "; ".join(titles) + ")" if titles else "")
        if retried:
            break
        retried = True
        messages.append({"role": "assistant", "content": answer.get("content") or ""})
        messages.append({"role": "user", "content": "[Hệ thống] Câu trả lời vừa rồi không gửi được vì: " + "; ".join(problems)
                         + ". Viết lại câu trả lời, chỉ dùng thông tin có trong kết quả công cụ và lời cư dân."})
    return SAFE_REPLY
