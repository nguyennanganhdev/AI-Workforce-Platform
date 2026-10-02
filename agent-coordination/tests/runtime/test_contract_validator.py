import json
import pytest
from runtime.contracts import SchemaValidator,KINDS
from adapters.backend.errors import ValidationError


def test_all_eight_schema_kinds_are_required_and_not_permissive():
    with pytest.raises(ValueError): SchemaValidator({})
    with pytest.raises(ValueError): SchemaValidator(dict.fromkeys(KINDS,{}))
    # Consumer test schema, not a producer contract or production override.
    schema={'type':'object','properties':{'id':{'type':'string','minLength':1}},'required':['id'],'additionalProperties':False}
    schemas={kind:schema for kind in KINDS}
    validator=SchemaValidator(schemas)
    for kind in KINDS:
        with pytest.raises(ValidationError): validator.validate(kind,{'unknown':True})
    with pytest.raises(ValidationError): validator.validate('unknown',{'id':'a'})
    with pytest.raises(ValueError): SchemaValidator(schemas|{'response':{'$ref':'https://untrusted.test/schema'}})
