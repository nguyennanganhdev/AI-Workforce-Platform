"""Render the owner-run model test pack. This command has no network or SDK IO."""

import argparse
import json
from pathlib import Path
import sys


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Optional directory for a blank result sheet; never starts a model run')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    pack = json.loads((repo / 'docs/vin-platform/N2_MODEL_OWNER_TEST_20261018.json').read_text(encoding='utf-8'))
    estimate = sum(case['estimated_tokens'] for case in pack['cases'])
    assert estimate == pack['limits']['estimated_input_tokens'] + pack['limits']['estimated_output_tokens']
    assert estimate <= pack['limits']['estimated_total_tokens_with_margin'] <= pack['limits']['test_user_daily_tokens']
    print('PLAN ONLY: model calls 0; no credentials loaded; no SDK/client constructed.')
    print(f"Estimated input/output: {pack['limits']['estimated_input_tokens']}/{pack['limits']['estimated_output_tokens']} tokens")
    print(f"Estimate with margin: {pack['limits']['estimated_total_tokens_with_margin']}; server daily/monthly cap: {pack['limits']['test_user_daily_tokens']}")
    for case in pack['cases']:
        print(f"{case['id']} [{case['surface']}] ~{case['estimated_tokens']} tokens: {case['prompt']}")
    if args.output:
        folder = Path(args.output).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        result = {'schema_version': pack['schema_version'], 'executed': False, 'model': None, 'source_sha': None,
            'cases': [{'id': case['id'], 'status': 'NOT_RUN', 'input_tokens': None, 'output_tokens': None,
                'reserved_tokens': None, 'latency_ms': None, 'provider_request_ids': [], 'evidence': []} for case in pack['cases']]}
        target = folder / 'owner-results.json'
        if target.exists():
            parser.error('Result sheet already exists; choose a new output directory to preserve evidence')
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
