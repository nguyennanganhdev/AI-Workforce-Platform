"""Grounding rules for Vinhomes answers.

Taken from the Reception agent's `violations()` (agents/reception/src/agent/loop.py), which is
the rule set the domain already trusts. The core's own check covers the last one there
(every figure must appear in the cited evidence). What this file adds is the wording:

  * internal words never reach the resident;
  * "it is done" only when the backend says the ticket is done (get_ticket prints
    "Trạng thái yêu cầu: resolved|closed|cancelled", and that line is the evidence);
  * "I recorded / passed it on" only when a tool did it (propose_plan prints "Phương án đã được gửi");
  * promises of time or "free of charge" only when a source says so.
"""
from __future__ import annotations

from awp.guard import PhraseRule, Rules

INTERNAL = ("ticket", "backend", "supervisor", "tool", "system prompt")
DONE_CLAIMS = ("đã hoàn tất", "đã xử lý xong", "đã sửa xong")
CANCEL_CLAIMS = ("đã được hủy", "đã hủy xong")
PROMISES = ("đang trên đường", "sẽ đến trong", "sẽ có mặt trong", "miễn phí", "trong vòng")
ACTION_CLAIMS = ("đã ghi nhận", "đã chuyển", "sẽ chuyển", "đã gửi", "đã báo", "đã tiếp nhận", "ghi nhận và")

# Reception's SAFE_REPLY asks the resident to write again; a case result cannot, so the second
# sentence points at the management office instead.
SAFE_REPLY = ("Mình chưa có thông tin chính thức về việc này. "
              "Ban quản lý sẽ xem xét và phản hồi bạn.")


def vinhomes_rules() -> Rules:
    return Rules(
        forbidden_words=INTERNAL,
        phrase_rules=[
            PhraseRule(DONE_CLAIMS, "khẳng định yêu cầu đã xong khi hệ thống chưa xác nhận",
                       unless=("trạng thái yêu cầu: resolved", "trạng thái yêu cầu: closed")),
            PhraseRule(CANCEL_CLAIMS, "khẳng định yêu cầu đã hủy khi hệ thống chưa xác nhận",
                       unless=("trạng thái yêu cầu: cancelled",)),
            PhraseRule(ACTION_CLAIMS, "nói đã ghi nhận hoặc đã chuyển nhưng chưa có công cụ nào làm việc đó",
                       unless=("phương án đã được gửi",)),
            # One rule per promise: a source that allows one phrase does not allow the others.
            *[PhraseRule((p,), "hứa thời gian, việc nhân viên đến hoặc miễn phí mà không có căn cứ", unless=(p,))
              for p in PROMISES],
        ],
        safe_reply=SAFE_REPLY)
