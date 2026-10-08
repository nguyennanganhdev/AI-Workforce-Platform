"""A description the Factory refuses comes back with what to add, not with a bare refusal."""
from vinhomes_api.v3_agent_builder import factory_refusal


def test_open_questions_are_listed_one_per_line():
    said = factory_refusal({'code': 'NEEDS_INPUT', 'issues': [
        {'code': 'NEEDS_INPUT', 'path': 'unresolvedQuestions.0', 'message': 'Agent lấy lịch vệ sinh từ đâu?'},
        {'code': 'NEEDS_INPUT', 'path': 'unresolvedQuestions.1', 'message': 'Agent trả về\n gì?'},
    ]})
    assert said.splitlines() == ['Factory cần biết thêm trước khi soạn chỉ dẫn. Bổ sung vào ô Nhiệm vụ rồi tạo lại:',
                                 '- Agent lấy lịch vệ sinh từ đâu?', '- Agent trả về gì?']


def test_another_refusal_says_its_reason_and_a_malformed_one_still_reads_as_a_sentence():
    assert factory_refusal({'issues': [{'code': 'INTENT_MISMATCH', 'message': 'The goal differs.'}]}) \
        == 'Factory chưa soạn được chỉ dẫn từ nhiệm vụ này: The goal differs.'
    # A job the room has no tool for names the part nothing covers.
    assert factory_refusal({'issues': [{'code': 'BLOCKED_RESOURCE', 'message': 'No catalogue tool covers this need: Send email.'}]}).splitlines() \
        == ['Nhóm chưa có công cụ cho một phần của nhiệm vụ này. Bỏ phần đó khỏi ô Nhiệm vụ, hoặc nhờ quản trị viên thêm công cụ rồi tạo lại:',
            '- No catalogue tool covers this need: Send email.']
    for malformed in ({}, [], {'issues': 'x'}, {'issues': [3, None]}, {'issues': [{'code': 'NEEDS_INPUT'}]}):
        assert factory_refusal(malformed).startswith('Factory ')
    # At most four reasons, each bounded: the answer of another service is never passed on whole.
    long = factory_refusal({'issues': [{'code': 'NEEDS_INPUT', 'message': 'x' * 900}] * 9})
    assert len(long.splitlines()) == 5 and max(map(len, long.splitlines()[1:])) == 302
