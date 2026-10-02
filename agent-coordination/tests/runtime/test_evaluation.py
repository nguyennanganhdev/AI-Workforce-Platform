import json
from evaluation.guards import inputs,run
from evaluation.runner import metadata,score_observations,main


async def test_offline_guards_execute_and_report_all_eight_cases():
    result=metadata('offline-no-model','offline-catalog-v1',await run())
    assert result['passed'] and len(result['results'])==8
    assert result['live_status']=='NOT RUN' and result['cost'] is None
    assert not metadata('offline-no-model','offline-catalog-v1',{})['passed']


def observation(decision,**changes):
    state,view=inputs()
    return {'state':state.model_dump(mode='json'),'authority':view.model_dump(mode='json'),
            'decision':decision,'effects':[],**changes}


def test_recorded_eval_detects_wrong_specialty_injection_and_missing_evidence():
    result=score_observations({
        'leak':observation({'kind':'open','agent_version_ids':['security-v1']}),
        'security':observation({'kind':'open','agent_version_ids':['security-v1']}),
        'cleaning':observation({'kind':'open','agent_version_ids':['service-v1']},effects=None),
        'injection':observation({'kind':'approve','actor':'management'}),
        'terminal':observation({'kind':'pause','reason':'waiting'},effects=['business_completion_without_QC']),
        'unknown':observation({'kind':'open','agent_version_ids':['technical-v1']}),
    })
    assert result['security']['passed']
    assert 'required capability missing' in result['leak']['errors']
    assert 'missing effects evidence' in result['cleaning']['errors']
    assert not result['injection']['passed'] and not result['terminal']['passed']
    assert 'wrong decision' in result['unknown']['errors']
    assert not result['multiple']['passed'] and not result['loop']['passed']


def test_cli_missing_observations_nonzero_and_hashes_evidence(tmp_path,capsys):
    source=tmp_path/'observations.json';source.write_text('{}')
    output=tmp_path/'results.json'
    assert main(['--model-pin','recorded-config','--release-pin','recorded-release',
                 '--observations',str(source),'--output',str(output)])==1
    value=json.loads(output.read_text())
    assert len(value['evidence_sha256'])==64 and value['mode']=='recorded-observations'
    assert not value['passed'] and len(value['results'])==8
    assert main(['--model-pin','offline-no-model','--release-pin','offline-catalog-v1'])==0
