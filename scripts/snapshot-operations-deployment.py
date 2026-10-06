"""Read-only deployment evidence without environment values or credentials."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'.codex-artifacts/operations-ui-2026-10-06/deployment.json'
compose=['docker','compose','--env-file','deploy/vinhomes/deployment.env','-f','deploy/vinhomes/compose.yml']
def run(command):
    result=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=25)
    if result.returncode:raise RuntimeError('Deployment read-only probe failed.')
    return result.stdout.strip()
raw=run(compose+['ps','--format','json'])
rows=[json.loads(row) for row in raw.splitlines() if row.strip()]
services=[{key:row.get(key) for key in ('Service','State','Health','Image','Ports')} for row in rows]
tables=['vh_private_chats','vh_private_chat_sources','vh_connection_policy','vh_external_call_confirmations',
        'vh_agent_skills','admin_model_registry','admin_role_models','vh_session_sources']
query="select json_build_object('migrations',(select count(*) from drizzle.__drizzle_migrations),'tables',(select json_agg(tablename order by tablename) from pg_tables where schemaname='public' and tablename in ("+','.join("'"+t+"'" for t in tables)+")))"
database=json.loads(run(['docker','exec','vinhomes-postgres-1','psql','-U','vinhomes_seed','-d','vinhomes_docker_complete','-At','-c',query]))
auto=run(['docker','exec','vinhomes-api-1','python','-c',"import os;print(os.getenv('VINHOMES_API_SUPERVISOR_APPROVES_PLANS',''))"])
backups=json.loads(run(compose+['--profile','maintenance','run','--rm','--no-deps','--entrypoint','python','backup','-c',
                               "import pathlib,json;print(json.dumps([p.name for p in pathlib.Path('/backups').iterdir() if p.is_dir()]))"]))
result={'captured_at':datetime.now(timezone.utc).isoformat(),'operations_url':'http://localhost:3022/operations',
        'database':'vinhomes_docker_complete','schema':database,'supervisor_autoapproves':auto=='1',
        'backup_directories':backups,
        'services':services,'running_services':sum(s['State']=='running' for s in services),
        'healthy_services':sum(s['Health']=='healthy' for s in services),
        'passed':all(s['State']=='running' and (s['Service']=='agents-net' or s['Health']=='healthy') for s in services)
                 and database['migrations']==20 and len(database['tables'])==len(tables) and auto=='1'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
raise SystemExit(0 if result['passed'] else 1)
