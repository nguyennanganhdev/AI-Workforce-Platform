"""Strict validator for pinned producer schemas + existing local wire guards.

No schema means fail closed. JSON schemas must be bundled locally; remote refs
are rejected to avoid network/schema substitution during validation.
"""
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from adapters.backend.errors import ValidationError
from adapters.backend.messages import validate_event, validate_request
from adapters.backend.reception_messages import validate_input, validate_output, validate_scope

KINDS = frozenset(('request','response','event','reception_input','reception_output',
                   'reception_delivery','reception_response','reception_verified'))


class SchemaValidator:
    def __init__(self, schemas):
        if set(schemas) != KINDS:
            raise ValueError('all eight pinned producer schemas required')
        self.schemas = {}
        for kind,schema in schemas.items():
            if not isinstance(schema,dict) or not any(k in schema for k in ('type','oneOf','anyOf','$ref')):
                raise ValueError('nontrivial pinned object schemas required')
            encoded = json.dumps(schema)
            def references(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key == '$ref' and (not isinstance(item,str) or not item.startswith('#/')):
                            raise ValueError('only bundled local schema refs allowed')
                        references(item)
                elif isinstance(value,list):
                    for item in value: references(item)
            references(schema)
            Draft202012Validator.check_schema(schema)
            self.schemas[kind] = Draft202012Validator(json.loads(encoded))

    @classmethod
    def directory(cls, directory):
        root = Path(directory)
        return cls({kind:json.loads((root / f'{kind}.schema.json').read_text()) for kind in KINDS})

    def validate(self, kind, value):
        if kind not in self.schemas:
            raise ValidationError()
        try:
            self.schemas[kind].validate(value)
            if kind == 'request': validate_request(value)
            elif kind == 'event': validate_event(value)
            elif kind == 'reception_input': validate_input(value)
            elif kind == 'reception_output': validate_output(value)
            elif kind == 'reception_delivery':
                if set(value) != {'message','context'}: raise ValueError()
                validate_output(value['message']); validate_scope(value['message'],value['context'])
        except Exception:
            raise ValidationError() from None
