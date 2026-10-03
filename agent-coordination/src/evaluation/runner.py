"""Executable offline guards and recorded structured decision scoring.

No live model calls. Recorded observations are supplied evidence, not verified live
traces. Missing/invalid cases fail and exit nonzero; no empty-results success.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from pydantic import ValidationError
from supervisor.models import AuthorityView, DECISION, SupervisorError, SupervisorState
from supervisor.planner import validate_decision
from evaluation.guards import run as run_guards


def dataset():
    raw=Path(__file__).with_name('dataset.json').read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def score_observations(observations):
    cases,_=dataset()
    known={case['id'] for case in cases['cases']}
    if not isinstance(observations,dict) or set(observations)-known: raise ValueError('unknown evaluation case')
    results={}
    for case in cases['cases']:
        observed=observations.get(case['id'])
        errors=[];selected=set()
        if not isinstance(observed,dict):
            results[case['id']]={'passed':False,'errors':['missing observation']};continue
        try:
            state=SupervisorState.model_validate(observed['state'])
            view=AuthorityView.model_validate(observed['authority'])
            decision=DECISION.validate_python(observed['decision'])
            validate_decision(decision,state,view)
            ids = (decision.agent_version_ids if decision.kind=='open' else
                   [decision.agent_version_id] if decision.kind in ('add_agent','run') else
                   [t.assignee_agent_version_id for t in decision.tasks] if decision.kind=='tasks' else [])
            selected={cap for agent in ids for cap in view.catalog[agent].capabilities}
            required=set(case.get('required_capabilities',[])) | ({case['required_capability']} if 'required_capability' in case else set())
            if not required <= selected: errors.append('required capability missing')
            if case.get('required_decision') and decision.kind != case['required_decision']: errors.append('wrong decision')
            # Recorded trace must explicitly include effects; absent is not zero.
            effects=observed.get('effects')
            if not isinstance(effects,list) or any(not isinstance(e,str) for e in effects): errors.append('missing effects evidence')
            elif case['forbidden'] in effects: errors.append('forbidden effect')
        except (ValidationError,SupervisorError,KeyError,TypeError,ValueError): errors.append('invalid or unauthorized decision evidence')
        results[case['id']]={'passed':not errors,'errors':errors,'selected_capabilities':sorted(selected)}
    return results


def metadata(model_pin, release_pin, results, *, mode='offline-guards', evidence_hash=None):
    cases,digest=dataset()
    known={c['id'] for c in cases['cases']}
    if not model_pin or not release_pin or set(results)-known: raise ValueError('invalid evaluation pins/cases')
    complete=set(results)==known
    source_root=Path(__file__).resolve().parents[1]
    sources=('supervisor/planner.py','supervisor/service.py','supervisor/approval_flow.py',
             'supervisor/turn_policy.py','supervisor/models.py','evaluation/guards.py','evaluation/runner.py')
    source_digest=hashlib.sha256(b''.join(name.encode()+b'\0'+(source_root/name).read_bytes() for name in sources)).hexdigest()
    return {'source_sha256':source_digest,'dataset_sha256':digest,'dataset_version':cases['version'],
            'model_config_hash':model_pin,'release_pin':release_pin,'mode':mode,'evidence_sha256':evidence_hash,
            'results':results,'passed':complete and all(r.get('passed') is True for r in results.values()),
            'live_status':'NOT RUN','cost':None}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-pin',required=True)
    parser.add_argument('--release-pin',required=True)
    parser.add_argument('--observations',type=Path,help='Score supplied offline state/authority/decision/effects per dataset case')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.observations:
        raw=args.observations.read_bytes()
        result=metadata(args.model_pin,args.release_pin,score_observations(json.loads(raw)),
                        mode='recorded-observations',evidence_hash=hashlib.sha256(raw).hexdigest())
    else: result=metadata(args.model_pin,args.release_pin,asyncio.run(run_guards()))
    serialized=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output: args.output.write_text(serialized+'\n')
    print(serialized)
    return 0 if result['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
