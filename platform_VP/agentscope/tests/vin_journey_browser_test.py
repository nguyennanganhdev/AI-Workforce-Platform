"""Whole browser journeys; run with scripts/workforce/check_vin_journey.py."""

import json
import os
import time
from uuid import UUID

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("VIN_UI_DIST"), reason="Run the disposable journey runner with a Vin frontend build")

from test_resident_contract import database as database, sql  # noqa: E402,F401
from vin_journey_fixture import journey as journey, browser_bridge, login, evidence, staff_complete  # noqa: E402,F401


def browser(journey, playwright):
    result = playwright.chromium.launch(headless=True)
    context = result.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
    login(journey)
    context.add_cookies([{"name": item.name, "value": item.value, "url": journey.url, "httpOnly": True}
        for item in journey.client.cookies.jar])
    page = context.new_page()
    browser_bridge(page, journey)
    return result, page


def link_resident(page, journey):
    from playwright.sync_api import expect
    page.goto(journey.url + "/connections")
    page.get_by_role("button", name="Liên kết Vinhomes", exact=True).click()
    page.locator('button[name="decision"][value="allow"]').click()
    page.get_by_role("button", name="Hoàn tất liên kết", exact=True).click()
    expect(page.get_by_role("button", name="Thu hồi liên kết", exact=True)).to_be_visible()


def test_customer_leader_staff_photo_final_click_and_revoke(journey, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    from utils import MockModel
    from agentscope.message import TextBlock, ToolCallBlock
    from agentscope.model import ChatResponse
    from agentscope.app.vin_platform._domain import DomainAdapter

    command = {}

    class ScriptedLeader(MockModel):
        def __init__(self):
            super().__init__(stream=False, context_size=100000)
            self.turn = 0

        async def count_tokens(self, messages, tools=None):
            return 1000

        async def _call_api(self, *args, **kwargs):
            self.turn += 1
            journey.model_calls.append("leader")
            if self.turn == 1:
                return ChatResponse(content=[ToolCallBlock(id="offline-customer-create", name="CustomerService", input=json.dumps(command))], is_last=True)
            return ChatResponse(content=[TextBlock(text="Please review the service card on Platform.")], is_last=True)

    async def get_model(*args, **kwargs):
        return ScriptedLeader()
    monkeypatch.setattr("agentscope.app._service._chat.get_model", get_model)
    with sync_playwright() as playwright:
        instance, page = browser(journey, playwright)
        try:
            link_resident(page, journey)

            async def prepare():
                from agentscope.app.vin_platform._router import link_list
                context = await journey.authority.context("alice")
                linked = (await link_list(who=(journey.authority, context)))["items"][0]
                profile = await DomainAdapter(journey.authority).request(context, linked["id"], "GET", "/me")
                return linked["id"], profile
            link_id, profile = journey.client.portal.call(prepare)
            from test_resident_contract import CATEGORY
            command.update(operation="create", link_id=link_id, apartment_id=profile["apartments"][0]["id"],
                description="Voi nuoc bep ro lien tuc, vui long tao yeu cau sua.", location="Bep duoi bon rua", category_id=CATEGORY)
            page.goto(journey.url + "/workforce/leader")
            editor = page.locator("textarea").last
            editor.fill(command["description"])
            editor.press("Enter")
            # Actual chat runtime executes CustomerService; wait for its SQL
            # binding before refreshing the visible canonical case card.
            def cases():
                async def read():
                    return await DomainAdapter(journey.authority).get_case(await journey.authority.context("alice"), case_id)
                return journey.client.portal.call(read)

            deadline = time.monotonic() + 25
            case_id = None
            while time.monotonic() < deadline:
                async def read_cases():
                    from agentscope.app.vin_platform import _tables as t
                    from sqlalchemy import select
                    async with journey.authority.engine.connect() as db:
                        return (await db.execute(select(t.cases.c.id))).scalars().all()
                found = journey.client.portal.call(read_cases)
                if found:
                    case_id = found[0]
                    break
                page.wait_for_timeout(100)
            assert case_id is not None, "Scripted Leader did not create a real C05 case"
            current = cases()
            domain_case = current["data"]["domain"]
            ticket_id = domain_case["ticket_id"]
            assert journey.model_calls and not journey.decisions
            photo_id = staff_complete(journey, domain_case["id"], ticket_id)
            page.get_by_test_id("customer-cases").locator("summary").click()
            page.get_by_role("button", name="Tải lại tiến độ", exact=True).click()
            expect(page.get_by_text("Offline repair verified by staff", exact=True)).to_be_visible()
            expect(page.get_by_test_id("customer-case").locator("img")).to_have_count(1)
            expect(page.get_by_test_id("customer-case").locator("img")).to_be_visible()
            assert any(path.endswith("/photos/" + photo_id) for _, path in journey.domain_calls)
            page.get_by_role("button", name="Xác nhận hoàn tất", exact=True).click()
            expect(page.get_by_role("dialog")).to_be_visible()
            assert not journey.decisions
            page.get_by_role("button", name="Quay lại", exact=True).click()
            assert not journey.decisions
            page.get_by_role("button", name="Xác nhận hoàn tất", exact=True).click()
            page.get_by_role("button", name="Xác nhận gửi quyết định", exact=True).click()
            expect(page.get_by_text("Dịch vụ đã ghi nhận quyết định của bạn.", exact=True)).to_be_visible()
            assert len(journey.decisions) == 1 and journey.decisions[0]["action"] == "confirm"
            assert sql(journey.database, "SELECT count(*) AS n FROM platform_commands WHERE ticket_id=$1", UUID(ticket_id))[0]["n"] == 0
            assert sql(journey.database, "SELECT status FROM vh_resident_cases WHERE id=$1", UUID(domain_case["id"]))[0]["status"] == "completed"
            assert not any("ticket-grants" in path for _, path in journey.browser_calls)
            evidence(journey, "customer-completed", page)
            page.goto(journey.url + "/connections")
            page.get_by_role("button", name="Thu hồi liên kết", exact=True).click()
            page.get_by_role("button", name="Xác nhận thu hồi", exact=True).click()
            expect(page.get_by_role("button", name="Liên kết Vinhomes", exact=True)).to_be_enabled()
            evidence(journey, "customer-revoked", page)
        finally:
            instance.close()
