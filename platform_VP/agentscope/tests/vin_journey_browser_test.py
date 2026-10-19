"""Whole browser journeys; run with scripts/workforce/check_vin_journey.py."""

import json
import os
import time
from uuid import UUID

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("VIN_UI_DIST"), reason="Run the disposable journey runner with a Vin frontend build")

from test_resident_contract import database as database  # noqa: E402,F401
from vin_journey_fixture import journey as journey, browser_bridge, login, evidence, staff_complete  # noqa: E402,F401


def browser(journey, playwright, user="alice"):
    result = playwright.chromium.launch(headless=True)
    context = result.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
    login(journey, user)
    context.add_cookies([{"name": item.name, "value": item.value, "domain": "127.0.0.1", "path": "/api/auth", "httpOnly": True}
        for item in journey.client.cookies.jar])
    page = context.new_page()
    page.set_default_timeout(8000)
    browser_bridge(page, journey)
    return result, page


def test_admin_policy_override_inactive_catalog_grants_memberships_and_library(journey):
    from playwright.sync_api import sync_playwright, expect
    from vin_fixtures import seed_admin_catalog
    from agentscope.app.storage import KnowledgeBaseRecord, KnowledgeBaseData, KnowledgeDocumentRecord, KnowledgeDocumentData, EmbeddingModelConfig

    async def prepare():
        ids = await seed_admin_catalog(journey.authority)
        from agentscope.app.vin_platform import QuotaPolicy
        for index in range(11):
            await journey.authority.set_policy(await journey.authority.context('admin'), f'user:page-{index:02}',
                QuotaPolicy(daily_tokens=100, monthly_tokens=1000, models=['test-model'], enabled=True), expected_revision=0)
        await journey.storage.upsert_knowledge_base('admin', KnowledgeBaseRecord(id='vin-library', user_id='admin',
            data=KnowledgeBaseData(name='Vin fixture library', retrieval_mode='lexical', collection_name='',
                embedding_model_config=EmbeddingModelConfig(type='lexical', credential_id='', model='lexical-no-embedding', dimensions=1))))
        await journey.storage.upsert_knowledge_document('admin', KnowledgeDocumentRecord(id='fixture-policy', user_id='admin', knowledge_base_id='vin-library', status='ready',
            data=KnowledgeDocumentData(filename='fixture-policy.md', size=35, blob_uri='private://not-public', text_content='Offline policy only', version='v1', review_status='candidate')))
        return ids
    ids = journey.client.portal.call(prepare)
    with sync_playwright() as playwright:
        instance, page = browser(journey, playwright, 'admin')
        try:
            page.goto(journey.url + '/admin')
            page.get_by_role('button', name='Quota & thư viện Vin', exact=True).click()
            policies = page.get_by_role('region', name='Chính sách đã lưu', exact=True)
            policies.get_by_role('button', name='Trang sau', exact=True).click()
            expect(policies.get_by_role('button', name='Gỡ ghi đè user:page-10', exact=True)).to_be_visible()
            page.get_by_label('Loại đối tượng', exact=True).select_option('user')
            page.get_by_label('ID đối tượng', exact=True).fill('alice')
            page.get_by_role('button', name='Đọc chính sách', exact=True).click()
            expect(page.get_by_label('Token mỗi ngày', exact=True)).to_have_value('500')
            async def concurrent_edit():
                from agentscope.app.vin_platform import QuotaPolicy
                await journey.authority.set_policy(await journey.authority.context('admin'), 'user:alice',
                    QuotaPolicy(daily_tokens=490, monthly_tokens=5000, models=['test-model'], enabled=True), expected_revision=1)
            journey.client.portal.call(concurrent_edit)
            page.get_by_label('Token mỗi ngày', exact=True).fill('450')
            page.get_by_role('button', name='Áp dụng chính sách thay thế', exact=True).click()
            expect(page.get_by_role('alert').filter(has_text='phiên bản')).to_be_visible()
            page.get_by_role('button', name='Đọc chính sách', exact=True).click()
            expect(page.get_by_label('Token mỗi ngày', exact=True)).to_have_value('490')
            page.get_by_label('Token mỗi ngày', exact=True).fill('450')
            page.get_by_role('button', name='Áp dụng chính sách thay thế', exact=True).click()
            expect(page.get_by_text('Đã lưu chính sách quota.', exact=True)).to_be_visible()
            page.get_by_label('Lọc chính sách theo đối tượng', exact=True).fill('user:alice')
            page.get_by_role('button', name='Gỡ ghi đè user:alice', exact=True).click()
            expect(page.get_by_text('Đã gỡ ghi đè; hạn mức quay về chính sách nhóm/vai trò.', exact=True)).to_be_visible()
            page.get_by_role('tab', name='Catalog', exact=True).click()
            expect(page.get_by_text('Vin fixture library · v1', exact=False)).to_be_visible()
            page.get_by_role('button', name='Duyệt tài liệu Vin fixture library', exact=True).click()
            page.get_by_role('button', name='Duyệt fixture-policy.md', exact=True).click()
            expect(page.get_by_text('Đã duyệt tài liệu thư viện.', exact=True)).to_be_visible()
            page.get_by_role('tab', name='Cấp quyền & nhóm', exact=True).click()
            page.get_by_role('button', name='Thu hồi quyền pilot', exact=True).click()
            expect(page.get_by_text('Đã thu hồi quyền catalog.', exact=True)).to_be_visible()
            page.get_by_role('button', name='Thu hồi thành viên alice', exact=True).click()
            expect(page.get_by_text('Đã thu hồi thành viên nhóm.', exact=True)).to_be_visible()
            evidence(journey, 'admin-reviewed', page)
            async def verify():
                admin = await journey.authority.context('admin')
                override = (await journey.authority.administration.page(admin, 'policies', subject='user:alice'))['items'][0]
                assert override['revision'] == 4 and not override['active']
                grants = await journey.authority.administration.page(admin, 'grants', catalog_id=ids['catalog_id'])
                assert not grants['items'][0]['active'] and grants['items'][0]['revision'] == 2
                docs = await journey.authority.administration.documents(admin, ids['catalog_id'])
                assert docs['items'][0]['review_status'] == 'approved'
            journey.client.portal.call(verify)
            assert not journey.model_calls
        finally:
            from pathlib import Path
            Path('.artifacts/vin-journey/admin-debug.txt').write_text(page.url + '\n' + page.locator('body').inner_text(), encoding='utf-8')
            page.screenshot(path='.artifacts/vin-journey/admin-debug.png', full_page=True)
            instance.close()


def test_builder_eval_batch_publish_and_reload_has_one_version(journey, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    from agentscope.app._agent_spec import AgentSpec, SpecTest
    from agentscope.app._router._workforce_console import ProposalView, ProposedAgentView, _persist_builder_turn
    from agentscope.app.storage import ChatModelConfig, SessionConfig
    from test_agent_studio_api import _Model

    async def prepare():
        config = ChatModelConfig(type='openai_credential', credential_id='vin-platform-openai', model='test-model', parameters={})
        await journey.storage.upsert_session('alice', 'workforce-builder', session_id='journey-builder',
            config=SessionConfig(workspace_id=await journey.manager.assign_workspace_id(user_id='alice', agent_id='workforce-builder', session_id='journey-builder'), chat_model_config=config))
        spec = AgentSpec(name='Offline leak adviser', description='Give only fixture safety advice',
            tests=[SpecTest(id=f'fixture-{index}', scenario=f'Fixture leak advice {index}', expected='Khóa van trước', safety_critical=index == 0) for index in range(5)])
        proposal = ProposalView(conversation_id='journey-builder', proposal_id='journey-proposal', revision=1, status='blocked',
            assistant_message='Offline reviewed draft; evaluate before publication', agents=[ProposedAgentView(name=spec.name,
                objective=spec.description, system_prompt='Use only fixture facts.', selected_tools=[], skill_name='', skill_markdown='',
                spec=spec.model_dump(mode='json'), evaluation={'checks': {'fixture': True}, 'passed': False})], chat_model_config=config, fixed_config={})
        await _persist_builder_turn(journey.storage, 'alice', 'journey-builder', 'Reviewed offline draft', proposal)
    journey.client.portal.call(prepare)

    async def get_model(*args, **kwargs):
        journey.model_calls.append('builder-eval')
        return _Model()
    monkeypatch.setattr('agentscope.app._router._workforce_console.get_model', get_model)
    monkeypatch.setenv('WORKFORCE_PLATFORM_OPENAI_API_KEY', 'offline-scripted-no-sdk-no-network')
    with sync_playwright() as playwright:
        instance, page = browser(journey, playwright)
        try:
            page.goto(journey.url + '/workforce/builder?conversation_id=journey-builder')
            page.get_by_role('button', name='Chạy lại eval · giữ cấu hình', exact=True).click()
            expect(page.get_by_role('button', name='Phát hành toàn bộ agent', exact=True)).to_be_visible(timeout=15000)
            page.get_by_role('button', name='Phát hành toàn bộ agent', exact=True).click()
            expect(page.get_by_text('Đã phát hành', exact=False).first).to_be_visible(timeout=15000)
            count = len(journey.model_calls)
            page.reload()
            expect(page.get_by_text('Offline leak adviser', exact=True).first).to_be_visible()
            async def verify():
                agents = await journey.storage.list_agents('alice')
                published = [agent for agent in agents if agent.data.name == 'Offline leak adviser']
                assert len(published) == 1 and published[0].data.published_version == 1 and len(published[0].data.versions) == 1
            journey.client.portal.call(verify)
            assert count == len(journey.model_calls) == 1
            evidence(journey, 'builder-published', page)
        finally:
            instance.close()


def test_automation_once_discord_duplicate_and_saved_delivery_ledger(journey, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import asyncio
    import httpx
    from agentscope.app._service._discord_identity import _identity_id
    from agentscope.app._service._personal_jobs import enqueue_channel
    from agentscope.app._router._workforce_console import _leader
    from agentscope.app.storage import ScheduleRecord, ScheduleData, ChatModelConfig, ChannelRecord, RoutingConfig, ChannelBinding, SessionSettings
    from agentscope.app.channel import DiscordChannel
    from agentscope.app.channel._base import ChannelEvent
    from agentscope.message import TextBlock
    from agentscope.model import ChatResponse
    from utils import MockModel

    class ScriptedModel(MockModel):
        def __init__(self):
            super().__init__(stream=False, context_size=100000)
        async def count_tokens(self, *args, **kwargs):
            return 1000
        async def _call_api(self, *args, **kwargs):
            from agentscope.app.vin_platform._context import execution_context
            context = execution_context.get()
            assert context.initiator_user_id == context.billing_subject_id == 'alice'
            journey.model_calls.append(context.purpose)
            return ChatResponse(content=[TextBlock(text='Offline fixture summary; operational outcome unverified.')], is_last=True)

    async def get_model(*args, **kwargs):
        return ScriptedModel()
    monkeypatch.setattr('agentscope.app._service._chat.get_model', get_model)

    async def prepare():
        context = await journey.authority.context('alice')
        await journey.authority.automation_put(context, _identity_id(context), 'channel',
            {'state': 'verified', 'discord_user_id': '100', 'verified_at': 1})
        agent, _ = await _leader('alice', journey.storage, journey.manager)
        # An unattended business agent uses the same publication gate. The
        # fixed Leader's evidence-repair turns are tested in the customer case.
        agent.data.system_role = 'business'
        await journey.storage.upsert_agent('alice', agent)
        config = ChatModelConfig(type='openai_credential', credential_id='vin-platform-openai', model='test-model', parameters={})
        record = ChannelRecord(id='journey-channel', name='Offline personal bot', channel_type='discord', user_id='alice',
            credentials={'application_id': '99', 'bot_token': 'offline-never-dispatched'},
            platform_config={'owner_user_id': '100', 'allowed_user_ids': ['100']},
            routing=RoutingConfig(bindings=[ChannelBinding(agent_id=agent.id)]), session=SessionSettings(chat_model_config=config.model_dump(mode='json')))
        await journey.storage.upsert_channel(record, '99')
        schedule = ScheduleRecord(id='journey-once', user_id='alice', agent_id=agent.id,
            data=ScheduleData(name='Offline once summary', description='Summarize only fixture content', cron_expression='* * * * *', timezone='UTC',
                once=True, chat_model_config=config, deliver_channel_id=record.id, deliver_chat_id='77'))
        await journey.storage.upsert_schedule('alice', schedule)
        discord = DiscordChannel(record.id, DiscordChannel.Credentials(bot_token='offline-never-dispatched', application_id='99'),
            DiscordChannel.Config(owner_user_id='100', allowed_user_ids=['100']), private_account=True)
        # Gateway channel metadata is an external Discord SDK IO seam. Keep
        # it synthetic; saved-message REST still executes its real code.
        from agentscope.app.channel._base import ChatKind
        monkeypatch.setattr(discord, 'chat_kind', AsyncMock(return_value=ChatKind.PRIVATE))
        monkeypatch.setattr(discord, 'chat_name', AsyncMock(return_value='Offline DM'))
        sent = {}
        def transport(request):
            if request.method == 'GET':
                return httpx.Response(200, json={'type': 1, 'recipients': [{'id': '100'}]})
            body = json.loads(request.content)
            assert body['enforce_nonce'] and body['allowed_mentions'] == {'parse': []}
            receipt = sent.setdefault(body['nonce'], 'offline-message-' + str(len(sent)))
            journey.deliveries.append(body)
            return httpx.Response(200, json={'id': receipt})
        discord._saved_http_client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        journey.app.state.chat_service._channel_clients = SimpleNamespace(get=AsyncMock(return_value=discord))
        manager = journey.app.state.scheduler_manager
        # Two timer owners have the same old snapshot, SQL owns deduplication.
        await asyncio.gather(manager._build_trigger(schedule)(), manager._build_trigger(schedule)())
        return record, discord
    record, discord = journey.client.portal.call(prepare)
    with sync_playwright() as playwright:
        instance, page = browser(journey, playwright)
        try:
            def finished(kind, count):
                async def read():
                    rows = await journey.authority.jobs.list(await journey.authority.context('alice'), kind)
                    return len(rows) == count and all(row.status == 'succeeded' for row in rows)
                return journey.client.portal.call(read)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not finished('delivery', 1):
                page.wait_for_timeout(100)
            assert finished('schedule-run', 1) and finished('delivery', 1)
            assert len(journey.model_calls) == 1
            page.goto(journey.url + '/schedule')
            page.get_by_role('tab', name='Danh sách', exact=True).click()
            page.get_by_text('Offline once summary', exact=True).click()
            expect(page.get_by_role('region', name='Lịch sử chạy cá nhân')).to_contain_text('Đã gửi')
            evidence(journey, 'schedule-once-ledger', page)
            event = ChannelEvent(channel_id=record.id, channel_user_id='100', chat_id='77', channel_message_id='same-message',
                content=[TextBlock(text='Summarize offline fixture')], metadata={'chat_type': 'dm'})
            async def submit():
                first, second = await asyncio.gather(enqueue_channel(journey.storage, record, event), enqueue_channel(journey.storage, record, event))
                assert first.job_id == second.job_id
            journey.client.portal.call(submit)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not finished('delivery', 2):
                page.wait_for_timeout(100)
            assert finished('channel-event', 1) and finished('delivery', 2)
            assert len(journey.model_calls) == 2 and len(journey.deliveries) == 2
            page.goto(journey.url + '/channel')
            page.get_by_text('Offline personal bot', exact=True).click()
            expect(page.get_by_role('region', name='Lịch sử chạy cá nhân')).to_contain_text('Đã gửi')
            evidence(journey, 'discord-run-ledger', page)
            # Replay a saved delivery transport. The same nonce returns the
            # same receipt and does not dispatch another model run.
            async def resend():
                body = journey.deliveries[-1]
                return await discord.send_saved_private({'chat_id': '77', 'recipient_id': '100', 'body': body['content'], 'nonce': body['nonce']})
            journey.client.portal.call(resend)
            assert len(journey.model_calls) == 2
            # Terminal historical fixtures exercise the actual HTTP/UI reader;
            # they cannot be claimed by the background worker or call a model.
            async def history():
                from datetime import timedelta
                from uuid import uuid4
                from sqlalchemy import insert, select
                from agentscope.app.workforce.foundation._tables import durable_jobs
                async with journey.authority.engine.begin() as db:
                    original = dict((await db.execute(select(durable_jobs).where(durable_jobs.c.job_type == 'schedule-run'))).mappings().one())
                    rows = []
                    for index in range(125):
                        stamp = original['created_at'] + timedelta(microseconds=index + 1)
                        rows.append({**original, 'id': uuid4().hex, 'idempotency_key': 'n2-history-' + str(index),
                            'created_at': stamp, 'updated_at': stamp, 'status': 'failed' if index == 124 else 'succeeded',
                            'error': {'code': 'FIXTURE_HISTORY_125'} if index == 124 else None, 'result': {'state': 'succeeded'}})
                    await db.execute(insert(durable_jobs), rows)
            journey.client.portal.call(history)
            page.goto(journey.url + '/schedule')
            page.get_by_role('tab', name='Danh sách', exact=True).click()
            page.get_by_text('Offline once summary', exact=True).click()
            region = page.get_by_role('region', name='Lịch sử chạy cá nhân')
            expect(region.locator('article')).to_have_count(25)
            for number in range(2, 7):
                region.get_by_role('button', name='Trang sau', exact=True).click()
                expect(region.get_by_text('Trang ' + str(number), exact=True)).to_be_visible()
            expect(region).to_contain_text('FIXTURE_HISTORY_125')
            expect(region.get_by_role('button', name='Trang sau', exact=True)).to_be_disabled()
            evidence(journey, 'history-past-125', page)
            assert len(journey.model_calls) == 2
        finally:
            instance.close()
            journey.client.portal.call(discord._saved_http_client.aclose)


@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_customer_plan_own_revision_ui_click_and_receipt_replay(journey, decision):
    from uuid import uuid4
    from playwright.sync_api import sync_playwright, expect
    from agentscope.app._service import _customer_cases as cases
    from agentscope.app.vin_platform._domain import DomainAdapter
    from test_resident_contract import CATEGORY, client

    with sync_playwright() as playwright:
        instance, page = browser(journey, playwright)
        try:
            link_resident(page, journey)
            jwt = login(journey)
            auth = {'Authorization': 'Bearer ' + jwt}
            response = journey.client.get('/workforce/console/leader/bootstrap', headers=auth)
            assert response.status_code == 200, response.text
            leader = response.json()
            async def create():
                linked = (await cases.linked_context(journey.storage, 'alice', leader['agent_id'], leader['session_id']))['items'][0]
                created = await cases.create_request(journey.storage, 'alice', leader['agent_id'], leader['session_id'],
                    link_id=linked['link_id'], apartment_id=linked['apartments'][0]['id'], category_id=CATEGORY,
                    description='Voi nuoc bep can sua theo phuong an rieng.', location='Bep duoi bon rua')
                snapshot = await DomainAdapter(journey.authority).get_case(await journey.authority.context('alice'), created['id'], refresh=True)
                return created['id'], snapshot['data']['domain']['tickets'][0]['id']
            case_id, ticket_id = journey.client.portal.call(create)
            with client(journey.database, 'management') as staff:
                ticket = staff.get('/tickets/' + ticket_id).json()['ticket']
                proposed = staff.post('/tickets/' + ticket_id + '/plans', json={'title': 'Reviewed repair plan',
                    'ticket_version': ticket['version'], 'idempotency_key': uuid4().hex, 'estimated_amount': '120000.00',
                    'steps': [{'category_id': CATEGORY, 'description': 'Replace fixture seal'}]})
                assert proposed.status_code == 201, proposed.text
                plan_id = proposed.json()['id']
                approved = staff.post('/plans/' + plan_id + '/management-decision', json={
                    'version': proposed.json()['version'], 'decision': 'approve', 'note': 'Internal fixture note'})
                assert approved.status_code == 200, approved.text
                plan_version = approved.json()['version']
            page.goto(journey.url + '/workforce/leader')
            page.get_by_test_id('customer-cases').locator('summary').click()
            label = ('Đồng ý' if decision == 'approve' else 'Từ chối') + ' phương án: Reviewed repair plan'
            button = page.get_by_role('button', name=label, exact=True)
            expect(button).to_be_visible()
            expect(page.get_by_text('Replace fixture seal', exact=True)).to_be_visible()
            button.click()
            expect(page.get_by_role('dialog')).to_contain_text('120000.00')
            page.get_by_role('button', name='Quay lại', exact=True).click()
            assert not journey.decisions
            button.click()
            page.get_by_role('dialog').locator('textarea').fill('Tôi đã xem đầy đủ phương án và gửi lựa chọn.')
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/decisions')) as sent:
                page.get_by_role('button', name='Xác nhận gửi quyết định', exact=True).click()
            assert sent.value.status == 200, sent.value.text()
            body = sent.value.request.post_data_json
            assert body['action'] == 'plan-decision' and body['payload']['plan_id'] == plan_id
            assert body['payload']['expectedVersion'] == plan_version and body['payload']['decision'] == decision
            assert len(journey.decisions) == 1
            # Use a fresh HTTP session after the browser has rotated its cookie.
            jwt = login(journey)
            replay = journey.client.post('/service-cases/' + case_id + '/decisions', json=body, headers={'Authorization': 'Bearer ' + jwt})
            assert replay.status_code == 200 and replay.json() == sent.value.json()
            assert len(journey.decisions) == 1 and not journey.model_calls
            expect(button).to_have_count(0)
            evidence(journey, 'plan-' + decision, page)
        finally:
            instance.close()


def link_resident(page, journey):
    from playwright.sync_api import expect
    page.goto(journey.url + "/connections")
    page.get_by_role("button", name="Liên kết Vinhomes", exact=True).click()
    page.locator('button[name="decision"][value="allow"]').click()
    page.get_by_role("button", name="Hoàn tất liên kết", exact=True).click()
    expect(page.get_by_role("button", name="Thu hồi liên kết", exact=True)).to_be_visible()


@pytest.mark.parametrize('browser_link', [True, False], ids=['browser-link', 'http-link'])
def test_customer_leader_staff_photo_final_click_and_revoke(journey, monkeypatch, browser_link):
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
            return ChatResponse(content=[TextBlock(text="Yêu cầu đã được ghi nhận. Vui lòng xem thẻ dịch vụ trên Platform.")], is_last=True)

    async def get_model(*args, **kwargs):
        return ScriptedLeader()
    monkeypatch.setattr("agentscope.app._service._chat.get_model", get_model)
    with sync_playwright() as playwright:
        instance, page = browser(journey, playwright)
        try:
            if browser_link:
                link_resident(page, journey)
            else:
                # Exercise the downstream runtime even while a producer HTML
                # redirect bug blocks the separate complete browser-link case.
                import re
                from urllib.parse import parse_qs, urlsplit
                async def start():
                    return await DomainAdapter(journey.authority).start(await journey.authority.context('alice'), 'vinhomes')
                begun = journey.client.portal.call(start)
                response = journey.domain.get(begun['authorization_url'])
                assert response.status_code == 200
                consent = journey.domain.post('https://domain.invalid/platform/link/authorize', data={
                    'transaction': re.search(r'name="transaction" value="([^"]+)"', response.text)[1],
                    'csrf': re.search(r'name="csrf" value="([^"]+)"', response.text)[1], 'decision': 'allow'}, follow_redirects=False)
                assert consent.status_code == 303
                query = parse_qs(urlsplit(consent.headers['location']).query)
                async def complete():
                    return await DomainAdapter(journey.authority).complete(await journey.authority.context('alice'), 'vinhomes', begun['transaction_id'], query['state'][0], query['code'][0])
                journey.client.portal.call(complete)

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
            expect(editor).to_have_attribute('placeholder', 'Trao đổi với Leader hoặc @agent của bạn…')
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
                        rows = (await db.execute(select(t.cases.c.id, t.cases.c.data))).mappings().all()
                        return [row['id'] for row in rows if row['data'].get('domain', {}).get('tickets')]
                found = journey.client.portal.call(read_cases)
                if found:
                    case_id = found[0]
                    break
                page.wait_for_timeout(100)
            if case_id is None:
                async def diagnostics():
                    values = []
                    for agent in await journey.storage.list_agents('alice'):
                        sessions = await journey.storage.list_sessions('alice', agent.id)
                        for session in sessions:
                            messages, _ = await journey.storage.list_messages('alice', session.id, limit=20)
                            values.extend(msg.model_dump(mode='json') for msg in messages)
                    return values
                from pathlib import Path
                Path('.artifacts/vin-journey/runtime-debug.json').write_text(json.dumps(journey.client.portal.call(diagnostics), ensure_ascii=False, indent=2), encoding='utf-8')
            assert case_id is not None, "Scripted Leader did not create a real C05 case; see fixture runtime-debug.json"
            expect(page.get_by_text('Yêu cầu đã được ghi nhận. Vui lòng xem thẻ dịch vụ trên Platform.', exact=True)).to_be_visible()
            assert journey.model_calls == ['leader', 'leader']
            current = cases()
            domain_case = current["data"]["domain"]
            ticket_id = domain_case["tickets"][0]["id"]
            assert journey.model_calls and not journey.decisions
            page.get_by_test_id("customer-cases").locator("summary").click()
            workflow = staff_complete(journey, domain_case['id'], ticket_id)
            try:
                for index, (stage, photo_id) in enumerate(workflow):
                    page.get_by_role("button", name="Tải lại tiến độ", exact=True).click()
                    approve = page.get_by_role('button', name='Đồng ý', exact=True)
                    expect(approve).to_be_visible()
                    if stage == 'completion':
                        expect(page.get_by_test_id('customer-case').locator('img')).to_have_count(1)
                        expect(page.get_by_test_id('customer-case').locator('img')).to_be_visible()
                        assert any(path.endswith('/photos/' + photo_id) for _, path in journey.domain_calls)
                    approve.click()
                    expect(page.get_by_role('dialog')).to_be_visible()
                    assert len(journey.decisions) == index
                    page.get_by_role('button', name='Quay lại', exact=True).click()
                    assert len(journey.decisions) == index
                    approve.click()
                    page.get_by_role('dialog').locator('textarea').fill('Tôi đã xem nội dung và đồng ý bản hiện tại.')
                    with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/decisions')) as response:
                        page.get_by_role('button', name='Xác nhận gửi quyết định', exact=True).click()
                    assert response.value.status == 200, response.value.text()
                    assert len(journey.decisions) == index + 1
                    exact = response.value.request.post_data_json
                    jwt = login(journey)
                    replay = journey.client.post('/service-cases/' + case_id + '/decisions', json=exact, headers={'Authorization': 'Bearer ' + jwt})
                    assert replay.status_code == 200 and replay.json() == response.value.json()
            finally:
                workflow.close()
            assert len(journey.decisions) == 2 and all(item['action'] == 'work-approval' for item in journey.decisions)
            async def verify_persisted_closure():
                import asyncpg
                db = await asyncpg.connect(journey.database['admin'])
                try:
                    assert await db.fetchval('SELECT count(*) FROM platform_commands WHERE ticket_id=$1', UUID(ticket_id)) == 0
                    assert await db.fetchval('SELECT status FROM vh_resident_cases WHERE id=$1', UUID(domain_case['id'])) == 'completed'
                finally:
                    await db.close()
            journey.client.portal.call(verify_persisted_closure)
            expect(page.get_by_test_id('customer-case').get_by_text('Hoàn tất', exact=True)).to_be_visible()
            assert not any("ticket-grants" in path for _, path in journey.browser_calls)
            evidence(journey, "customer-completed", page)
            page.goto(journey.url + "/connections")
            page.get_by_role("button", name="Thu hồi liên kết", exact=True).click()
            page.get_by_role("button", name="Xác nhận thu hồi", exact=True).click()
            expect(page.get_by_role("button", name="Liên kết Vinhomes", exact=True)).to_be_enabled()
            evidence(journey, "customer-revoked", page)
        finally:
            instance.close()
