"""The API decides pass/fail with the evaluator's own contract code: the copy must stay verbatim."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_vendored_contracts_match_the_evaluator():
    source = ROOT / 'agent-coordination/src/agent_eval/contracts.py'
    copy = ROOT / 'services/vinhomes-api/src/vinhomes_api/_vendor/agent_eval/contracts.py'
    assert copy.read_bytes().replace(b'\r\n', b'\n') == source.read_bytes().replace(b'\r\n', b'\n'), \
        'Copy agent-coordination/src/agent_eval/contracts.py into _vendor/agent_eval/ again'
