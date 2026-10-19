"""Builder skill names remain safe and readable after restoring Dong's flow."""


def test_a_vietnamese_skill_name_keeps_its_letters():
    from agentscope.app._router._workforce_console import _slug

    assert _slug("Tư vấn và phân loại sự cố cho cư dân Đông") == "tu-van-va-phan-loai-su-co-cho-cu-dan-dong"
    assert _slug("!!!") == "generated-skill"
