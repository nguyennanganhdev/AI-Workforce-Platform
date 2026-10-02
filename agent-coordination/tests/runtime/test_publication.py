import importlib.util
from pathlib import Path
import json
import pytest
from adapters.backend.errors import AdapterError
from adapters.backend.messages import fingerprint
from groupchat.context_builder import reception_context
from groupchat.reception import ReceptionMessage
from persistence.sqlite import DevelopmentStore
from runtime.publication import DraftPublisher
from supervisor.models import Action,SupervisorState,AuthorityView,DECISION
from supervisor.service import SupervisorService,prepare_decision
from support.fakes import make_context

from tests.adapters.reception import support as fixtures


def v2():
    raw=fixtures.input_message()
    ctx=make_context()
    for k in ('tenant_id','domain_id','workspace_id','ticket_id','ticket_generation'): raw[k]=getattr(ctx,k)
    return ctx,ReceptionMessage.model_validate(raw)


def test_context_projection_preserves_explicit_unknown():
    ctx,msg=v2()
    msg.facts[0].value=None
    item=reception_context(msg,ctx,msg.ticket_version,['technical'])
    assert 'value' in json.loads(item.content)['facts'][0]
    assert json.loads(item.content)['facts'][0]['value'] is None


async def test_publish_receipt_binds_exact_wire_and_version():
    action=Action(action_id='op',channel='draft',operation='question',wire={'request_id':'op','kind':'question','content':{'question':'?'}},plan_version=1)
    class Backend:
        bad=False
        async def publish_coordination_intent(self,state,a):
            return dict(request_id=a.action_id,status='accepted',payload_hash='wrong' if self.bad else fingerprint(a.wire),canonical_id='backend-question',ticket_version='new-v2')
    backend=Backend();publisher=DraftPublisher(backend)
    assert (await publisher.dispatch(None,action))['canonical_id']=='backend-question'
    backend.bad=True
    with pytest.raises(AdapterError,match='receipt_mismatch'): await publisher.dispatch(None,action)


async def test_draft_question_checkpoint_receipt_restart_then_pending(tmp_path):
    ctx,msg=v2()
    state=SupervisorState(context=ctx,groupchat_version_id='group',turn_policy={},reception=msg,
        ticket_version=msg.ticket_version,supervisor_run_id='supervisor-run',question_draft='Có khóa nước không?')
    store=DevelopmentStore(tmp_path/'f.sqlite');assert await store.commit(state,None)
    service=SupervisorService(store=store,authority=None,verifier=None,event_types={},planner=None,room=None,backend=None,
        groupchat_version_id='group',publisher=object())
    view=AuthorityView(context=ctx,state_version=state.version)
    assert service._prepare_publication(state,view)
    wire=state.action.wire.copy();key=state.action.wire['draft_key']
    state=await service._save(state,state.version)
    receipt=dict(request_id=state.action.action_id,status='accepted',payload_hash=fingerprint(wire),canonical_id='question-backend',ticket_version='version-next')
    state=await service._record(state,receipt)
    restarted=await DevelopmentStore(store.path).load(ctx)
    assert restarted.draft_receipts[key]==receipt and restarted.action is None
    # Receipt alone does not approve/notify; wait for canonical Authority projection.
    assert not service._prepare_publication(restarted,AuthorityView(context=ctx,state_version=restarted.version))
    assert restarted.pending_resident is None
    from supervisor.service import prepare_next
    view=AuthorityView(context=ctx,state_version=restarted.version,ticket_version='version-next',
        resident_request_type='information_requested',resident_request_message=restarted.question_draft)
    from datetime import datetime,timezone
    assert prepare_next(restarted,view,datetime.now(timezone.utc))
    assert restarted.pending_resident=='information_requested'
    assert restarted.action.channel=='reception'
