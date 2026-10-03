"""Regenerate published room contracts with the pinned Pydantic environment."""
import json
from pathlib import Path

from pydantic import TypeAdapter
from groupchat.models import Command, Query, Result, ScopeState


def main():
    destination = Path(__file__).resolve().parents[2] / 'docs/teams/dong/agent-room-schemas'
    for name, model in (('command', Command), ('query', Query), ('result', Result), ('state', ScopeState)):
        schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                  **TypeAdapter(model).json_schema()}
        (destination / f'{name}.schema.json').write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
