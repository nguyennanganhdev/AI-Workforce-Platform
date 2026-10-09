from awp.guard import check_text
from awp_vinhomes.rules import SAFE_REPLY, vinhomes_rules

RULES = vinhomes_rules()
OPEN = "Yêu cầu VH-0001. Trạng thái yêu cầu: open. Phiên bản: 7."
DONE = "Yêu cầu VH-0001. Trạng thái yêu cầu: resolved. Phiên bản: 8."


def blocked(text, *sources):
    return bool(check_text(text, list(sources), RULES))


def test_done_is_only_said_when_the_system_says_so():
    assert blocked("Yêu cầu VH-0001 đã sửa xong.", OPEN)
    assert blocked("Mình đã xử lý xong rồi nhé.", OPEN)
    assert not blocked("Yêu cầu VH-0001 đã sửa xong.", DONE)
    assert not blocked("Yêu cầu VH-0001 đã hoàn tất.", DONE.replace("resolved", "closed"))


def test_cancelled_is_its_own_condition():
    assert blocked("Yêu cầu đã được hủy.", OPEN)
    assert blocked("Yêu cầu đã được hủy.", DONE)  # resolved is not cancelled
    assert not blocked("Yêu cầu đã được hủy.", DONE.replace("resolved", "cancelled"))


def test_a_figure_nobody_gave_is_blocked():
    assert blocked("Chi phí là 999000 đồng.", OPEN)
    assert not blocked("Yêu cầu VH-0001 đang ở phiên bản 7.", OPEN)
    assert not blocked("Biểu phí gửi xe là 120000 đồng.", "Phí gửi xe máy: 120000 đồng/tháng.")


def test_internal_words_never_reach_the_resident():
    for text in ("Ticket của bạn đang chờ.", "Hệ thống backend đang bận.", "Supervisor sẽ xem.", "Dùng tool để tra."):
        assert blocked(text, OPEN), text
    assert not blocked("Yêu cầu của bạn đang chờ.", OPEN)


def test_promises_need_a_source_each():
    assert blocked("Nhân viên sẽ đến trong hôm nay.", OPEN)
    assert blocked("Dịch vụ này miễn phí.", OPEN)
    assert not blocked("Dịch vụ này miễn phí.", "Gói kiểm tra định kỳ: miễn phí cho cư dân.")
    # a source for one promise does not excuse another
    assert blocked("Nhân viên sẽ đến trong hôm nay.", "Gói kiểm tra định kỳ: miễn phí.")


def test_saying_it_was_sent_needs_a_tool_that_sent_it():
    assert blocked("Mình đã gửi phương án cho Ban quản lý.", OPEN)
    assert blocked("Mình đã chuyển yêu cầu.", OPEN)
    sent = "Phương án đã được gửi tới Ban quản lý (mã plan-1), trạng thái phương án: management_pending."
    assert not blocked("Mình đã gửi phương án cho Ban quản lý.", sent)


def test_the_safe_reply_is_friendly_and_clean():
    assert RULES.safe_reply == SAFE_REPLY
    assert not blocked(SAFE_REPLY, "")
    assert "Ban quản lý" in SAFE_REPLY
