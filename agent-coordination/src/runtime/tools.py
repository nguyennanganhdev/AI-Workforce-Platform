"""Tool authorization + receipt boundary; producer owns mutation and signed proof."""
from jsonschema import Draft202012Validator
from adapters.backend.errors import AdapterError


class AuthorizedTools:
    def __init__(self, producer): self.producer = producer

    async def execute_authorized(self, invocation, release, name, arguments, operation_id, run_id, call_id):
        descriptor = next((t for t in release.tool_descriptors if t['name']==name),None)
        if descriptor is None: raise AdapterError('tool_not_granted')
        try: Draft202012Validator(descriptor['parameters']).validate(arguments)
        except Exception: raise AdapterError('invalid_tool_arguments') from None
        # Do not mint or treat model-provided strings as signed backend authorization.
        proof = await self.producer.authorize_tool(invocation,release,name,arguments,operation_id,run_id,call_id)
        if not proof: raise AdapterError('tool_authorization_missing')
        verify = getattr(self.producer,'verify_tool_authorization',None)
        if not callable(verify) or await verify(proof,invocation,release,name,arguments,operation_id,run_id,call_id) is not True:
            raise AdapterError('tool_authorization_unverified')
        receipt = await self.producer.apply_tool(proof,invocation,name,arguments,operation_id,run_id,call_id)
        if (receipt.get('operation_id'),receipt.get('run_id'),receipt.get('call_id')) != (operation_id,run_id,call_id):
            raise AdapterError('tool_receipt_mismatch',outcome_unknown=True)
        verify_receipt = getattr(self.producer,'verify_tool_receipt',None)
        if not callable(verify_receipt) or await verify_receipt(receipt,proof,invocation,operation_id,run_id,call_id) is not True:
            raise AdapterError('tool_receipt_unverified',outcome_unknown=True)
        return receipt
