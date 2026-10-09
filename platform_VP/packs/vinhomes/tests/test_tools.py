import asyncio
from types import SimpleNamespace

from agentscope.message import ToolResultState

from awp.casefile import CaseStore
from awp.db import Database
from awp.runtime import Binding
from awp_vinhomes import mapping
from awp_vinhomes.rules import vinhomes_rules
from awp_vinhomes.tools import GetTicket, Knowledge, ProposePlan, SearchKnowledge, fold, search_documents
from fake_vinhomes import PHONE, TICKET, doc, stack, submitted

run = asyncio.run

DOCS = [
    doc("policy:1", "Quy định thi công", "Giờ thi công từ 8 giờ đến 17 giờ. Cấm thi công vào Chủ nhật. Đặt cọc 5000000 đồng.",
        zones=["S1"]),
    doc("policy:2", "Biểu phí gửi xe", "Xe máy 120000 đồng mỗi tháng. Ô tô 1500000 đồng mỗi tháng.", kind="fee_table"),
    doc("handbook:3", "Cẩm nang cắt nước", "Khi cắt nước theo kế hoạch, BQL báo trước 24 giờ."),
]


def text(chunk) -> str:
    return "\n".join(b.text for b in chunk.content)


async def setup(state, client, role="leader"):
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_all()
    cases = CaseStore(db)
    intake = mapping.intake_from_message(submitted())
    case_id = await cases.create_case(tenant="t", domain="vinhomes", external_ref=TICKET, user_id="u",
                                      intake=intake.model_dump())
    rt = SimpleNamespace(cases=cases)

    async def rules_of(_case_id):
        return vinhomes_rules()
    rt.case_rules = rules_of
    b = Binding(case_id, "s1", "a1", "Dieu-phoi-BQL" if role == "leader" else "Ky-thuat", role, "u")
    know = Knowledge(client, ttl=60)
    return rt, b, know, cases, case_id, db


def test_fold_ignores_accents_and_keeps_length():
    assert fold("Đặt cọc Thi Công") == "dat coc thi cong"
    sample = "Giờ thi công từ 8 giờ"
    assert len(fold(sample)) == len(sample)


def test_search_finds_with_or_without_accents_and_ranks_titles():
    for q in ("thi công", "thi cong", "THI CONG"):
        hits = search_documents(DOCS, q)
        assert hits and hits[0].startswith("[policy:1]") and "8 giờ đến 17 giờ" in hits[0] and "khu S1" in hits[0]
    assert search_documents(DOCS, "gửi xe")[0].startswith("[policy:2]")
    assert search_documents(DOCS, "bóng đá") == []
    assert len(search_documents(DOCS * 3, "giờ", limit=2)) == 2


def test_get_ticket_reports_status_in_the_words_the_rules_expect():
    async def go():
        async with stack() as (state, client):
            rt, b, know, *_ = await setup(state, client)
            out = await GetTicket(client, rt, b, know).call()
            t = text(out)
            assert out.state == ToolResultState.SUCCESS
            assert "VH-0001" in t and "Trạng thái yêu cầu: open" in t and "Phiên bản: 7" in t
            assert "Chưa có phương án" in t and PHONE not in t and "S1.01-1201" not in t
            state.status = "resolved"
            assert "Trạng thái yêu cầu: resolved" in text(await GetTicket(client, rt, b, know).call())
            state.fail = [503]
            bad = await GetTicket(client, rt, b, know).call()
            assert bad.state == ToolResultState.ERROR and "thử lại" in text(bad)
    run(go())


def test_search_knowledge_uses_the_pack_and_caches_it():
    async def go():
        async with stack() as (state, client):
            state.knowledge["resident"] = DOCS
            rt, b, know, *_ = await setup(state, client, "worker")
            tool = SearchKnowledge(client, rt, b, know)
            out = await tool.call("giờ thi công")
            assert "8 giờ đến 17 giờ" in text(out)
            await tool.call("biểu phí")
            assert len(state.knowledge_calls) == 1  # second search came from the copy in memory
            empty = text(await tool.call("tàu ngầm hạt nhân"))
            assert "Không tìm thấy" in empty and "3 tài liệu" in empty
            # staff pack is a separate one
            state.knowledge["staff"] = [doc("policy:9", "Quy trình nội bộ", "Báo trưởng ca trước 7 giờ.")]
            assert "policy:9" in text(await tool.call("quy trình", audience="staff"))
    run(go())


def test_the_pack_is_refreshed_with_since_and_survives_an_outage():
    async def go():
        async with stack() as (state, client):
            state.knowledge["resident"] = DOCS
            know = Knowledge(client, ttl=0)  # always stale
            assert len(await know.documents("resident")) == 3
            assert len(await know.documents("resident")) == 3  # "unchanged" keeps the copy
            assert state.knowledge_calls[-1]["since"] == state.knowledge_version
            state.fail = [503]
            assert len(await know.documents("resident")) == 3  # old copy beats nothing
    run(go())


PLAN = dict(summary="Thay gioăng vòi bếp", steps=["Khóa van", "Thay gioăng", "Kiểm tra rò rỉ"])


def test_propose_plan_sends_one_plan_even_if_asked_twice():
    async def go():
        async with stack() as (state, client):
            rt, b, know, *_ = await setup(state, client)
            tool = ProposePlan(client, rt, b, know)
            first = await tool.call(**PLAN)
            again = await tool.call(**PLAN)
            assert first.state == again.state == ToolResultState.SUCCESS
            assert "Phương án đã được gửi" in text(first) and "management_pending" in text(first)
            assert text(first) == text(again) and len(state.plans) == 1
            sent = next(iter(state.plans.values()))[1]
            assert sent["proposed_by_client_id"] == "platform"
    run(go())


def test_propose_plan_refuses_what_is_not_grounded_or_not_allowed():
    async def go():
        async with stack() as (state, client):
            rt, b, know, cases, case_id, _db = await setup(state, client)
            tool = ProposePlan(client, rt, b, know)
            # a worker may not propose
            w = Binding(case_id, "s2", "a2", "Ky-thuat", "worker", "u")
            assert (await ProposePlan(client, rt, w, know).call(**PLAN)).state == ToolResultState.ERROR
            # an amount nobody gave
            out = await tool.call(**PLAN, estimated_amount=750000)
            assert out.state == ToolResultState.ERROR and "750000" in text(out)
            # the same amount once the fee table is in the case file
            await cases.add(case_id, "evidence", "Chi-phi", {"tool": "search_knowledge", "text": "Công thay gioăng: 750000 đồng"})
            assert (await tool.call(**PLAN, estimated_amount=750000)).state == ToolResultState.SUCCESS
            # a made-up hour in a step
            bad = await tool.call(summary="Hẹn thợ", steps=["Thợ đến lúc 14:30"])
            assert bad.state == ToolResultState.ERROR and "14:30" in text(bad)
            # shape
            assert (await tool.call(summary="x", steps=[])).state == ToolResultState.ERROR
            assert (await tool.call(summary="x", steps=list("abcde"))).state == ToolResultState.ERROR
            assert state.plan_posts == 1
    run(go())


def test_propose_plan_reports_the_domains_refusal_without_retrying():
    async def go():
        async with stack() as (state, client):
            rt, b, know, *_ = await setup(state, client)
            state.plan = {"id": "p0", "status": "management_pending", "version": 1, "title": "cũ"}
            out = await ProposePlan(client, rt, b, know).call(**PLAN)
            assert out.state == ToolResultState.ERROR and "Decide the plan already waiting" in text(out)
            assert state.plan_posts == 1
            state.plan = None
            state.category = None  # not classified yet: 422
            out = await ProposePlan(client, rt, b, know).call(**PLAN)
            assert out.state == ToolResultState.ERROR and "classified" in text(out)
    run(go())


def test_tools_are_read_only_except_the_plan():
    assert GetTicket.is_read_only and SearchKnowledge.is_read_only and not ProposePlan.is_read_only
