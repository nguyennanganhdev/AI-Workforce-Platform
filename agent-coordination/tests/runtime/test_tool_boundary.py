import pytest
from adapters.backend.errors import AdapterError
from agents.releases import ReleasedSession
from runtime.tools import AuthorizedTools
from tests.runtime.test_releases_remote import invocation,release


class Producer:
    valid=False
    receipt_valid=False
    calls=0
    async def authorize_tool(self,*args):return {'producer_signed_authorization':'test-proof'}
    async def verify_tool_authorization(self,*args):return self.valid
    async def apply_tool(self,proof,i,name,args,op,run,call):
        self.calls+=1
        return dict(operation_id=op,run_id=run,call_id=call,producer_signed_receipt='test-receipt')
    async def verify_tool_receipt(self,*args):return self.receipt_valid


async def test_unverified_authorization_never_reaches_apply_and_unverified_receipt_is_unknown():
    producer=Producer();boundary=AuthorizedTools(producer);i=invocation();r=ReleasedSession.model_validate(release(i))
    with pytest.raises(AdapterError,match='authorization_unverified'):
        await boundary.execute_authorized(i,r,'read',{},'op','run','call')
    assert producer.calls==0
    producer.valid=True
    with pytest.raises(AdapterError,match='receipt_unverified') as exc:
        await boundary.execute_authorized(i,r,'read',{},'op','run','call')
    assert exc.value.outcome_unknown and producer.calls==1
    producer.receipt_valid=True
    assert (await boundary.execute_authorized(i,r,'read',{},'new-op','run','new-call'))['call_id']=='new-call'
    with pytest.raises(AdapterError,match='invalid_tool_arguments'):
        await boundary.execute_authorized(i,r,'read',{'secret_field':'forged'},'op','run','call')
    assert producer.calls==2
