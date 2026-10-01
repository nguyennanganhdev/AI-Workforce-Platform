"""Compile the reviewed V2 + V3 dictionaries into the application's Drizzle schema.

Run with Python 3. The checked-in TypeScript is the runtime entry point; Python is
not required to start the server or to generate a migration.
"""
from pathlib import Path
import json,re,hashlib

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'server/src/db/schema'
M=json.loads((OUT.parent/'design/v2.json').read_text(encoding='utf8'))
V3=json.loads((OUT.parent/'design/v3.json').read_text(encoding='utf8'))
M.update(V3['new']);M.update(V3['changed'])
SECURITY=json.loads((OUT.parent/'design/v3-security.json').read_text(encoding='utf8'))
# Preserve reviewed V2/V3 dictionaries; apply the newer approval-kind extension.
M['work_approvals']['rules']=M['work_approvals']['rules'].replace(
 'kind customer_repair/management_water_shutdown/customer_completion;',
 'kind '+ '/'.join(SECURITY['workApprovalKinds'])+';')
# Resident pre-intake images have a verified unit scope before a ticket exists.
# Keep this overlay with the 0006 migration so regeneration preserves the extension.
M['files']['rows'].insert(10, ['unit_id', 'UUID', 'NULL; FK \u2192 `units.id`', 'Verified resident apartment scope'])
M['files']['rules']=M['files']['rules'].replace('scope_kind ticket/channel/document/report;', 'scope_kind ticket/channel/document/report/resident;')
def camel(s):return re.sub(r'_([a-z])',lambda m:m[1].upper(),s)
def ident(s):return s if len(s)<=63 else s[:50]+'_'+hashlib.sha256(s.encode()).hexdigest()[:12]
names={n:camel(n) for n in M}
names['action_policy']='actionPolicy'
enum_types={'ROLE':'role','AGENT_TYPE':'agentType','CREDENTIAL_KIND':'credentialKind','AGENT_VISIBILITY':'agentVisibility','ROUTINE_RUN_STATUS':'routineRunStatus'}
compat={n for n,m in M.items() if m.get('source')}
defaults={('agents','purpose'):'specialist',('agents','status'):'active',('channels','kind'):'management',('credentials','scope_kind'):'platform'}
# Explicit conditional unique keys. All other dictionary UQ declarations are unconditional.
partial={
'users':[("lower(email)","email IS NOT NULL"),("phone_e164","phone_e164 IS NOT NULL")],
'execution_principals':[("tenant_id,user_id","kind='user'"),("tenant_id,workspace_id","kind='workspace_service'")],
'access_scopes':[("tenant_id","kind='tenant'")]+[(f'tenant_id,{c}',f"kind='{k}'") for k,c in [('management','management_unit_id'),('site','site_id'),('zone','zone_id'),('building','building_id')]],
'units':[("building_id,code","building_id IS NOT NULL"),("zone_id,code","building_id IS NULL")],
'model_profiles':[("tenant_id,code","workspace_id IS NULL"),("workspace_id,code","workspace_id IS NOT NULL")],
'agent_releases':[("agent_id","status='published' AND revoked_at IS NULL")],
'agents':[("tenant_id","purpose='reception' AND status='active'")],
'channels':[("workspace_id","is_dispatch_default AND deleted_at IS NULL")],
'runtime_session_bindings':[("tenant_id,channel_id,agent_id","audience_kind='personal' AND status IN ('active','provisioning','interrupted')"),("team_member_id","audience_kind='team' AND status IN ('active','provisioning','interrupted')")],
'memory_namespaces':[("owner_principal_id,kind,purpose","kind='personal'"),("team_id,purpose","kind='team'"),("workspace_id,purpose","kind='workspace'")],
'file_uploads':[("file_id","status IN ('issued','uploading','uploaded','verifying')")],
'file_deletion_requests':[("file_id","status IN ('pending','running','blocked')")],
'reception_waits':[("session_id","status IN ('preparing','open','resuming')")],
'work_assignments':[("work_order_id","status IN ('offered','accepted')")],
'knowledge_reviews':[("document_version_id,subject_seq","document_version_id IS NOT NULL"),("memory_candidate_id,subject_seq","memory_candidate_id IS NOT NULL")],
'memory_candidates':[("supersedes_candidate_id","supersedes_candidate_id IS NOT NULL")],
'ticket_triage_decisions':[("review_id","review_id IS NOT NULL AND outcome='applied'")],
'work_reassignment_requests':[("source_assignment_id","status IN ('requested','approved','executing')")],
'credentials':[("kind,provider,key_id","scope_kind='platform' AND revoked_at IS NULL"),("tenant_id,kind,provider,key_id","scope_kind='tenant' AND revoked_at IS NULL"),("tenant_id,workspace_id,kind,provider,key_id","scope_kind='workspace' AND revoked_at IS NULL")],
'skills':[("tenant_id,slug","workspace_id IS NULL AND owner_user_id IS NULL"),("tenant_id,owner_user_id,slug","workspace_id IS NULL AND owner_user_id IS NOT NULL"),("tenant_id,workspace_id,slug","workspace_id IS NOT NULL AND owner_user_id IS NULL"),("tenant_id,workspace_id,owner_user_id,slug","workspace_id IS NOT NULL AND owner_user_id IS NOT NULL")],
'ticket_assessment_evidence':[(f'assessment_id,fact_key,{c}',f'{c} IS NOT NULL') for c in ['message_id','event_id','evidence_item_id']],
}
extra_unique={
'accounts':['provider_id,account_id'],'sessions':['token'],'deployment_packages':['tenant_id','external_tenant_key'],
'runtime_session_bindings':['backend_id,runtime_session_key'],'runtime_identities':['tenant_id,id,backend_id'],
'knowledge_acl':[], 'routine_runs':['routine_id,scheduled_for'],
}
checks={
'users':["status IN ('pending','active','suspended','deleted')","status='deleted' OR email IS NOT NULL OR phone_e164 IS NOT NULL"],
'scoped_user_roles':["role_code IN ('management','staff','customer')","valid_to IS NULL OR valid_to>valid_from"],
'execution_principals':["(kind='user' AND user_id IS NOT NULL AND workspace_id IS NULL) OR (kind='workspace_service' AND user_id IS NULL AND workspace_id IS NOT NULL)"],
'credentials':["(scope_kind='platform' AND tenant_id IS NULL AND workspace_id IS NULL) OR (scope_kind='tenant' AND tenant_id IS NOT NULL AND workspace_id IS NULL) OR (scope_kind='workspace' AND tenant_id IS NOT NULL AND workspace_id IS NOT NULL)"],
'agents':["(purpose='reception' AND workspace_id IS NULL) OR (purpose IN ('supervisor','specialist') AND workspace_id IS NOT NULL)"],
'channels':["(kind='reception' AND workspace_id IS NULL) OR (kind IN ('management','agent_builder') AND workspace_id IS NOT NULL)"],
'agent_teams':["num_nonnulls(ticket_id,request_message_id)=1"],
'memory_namespaces':["(kind='personal' AND workspace_id IS NULL AND team_id IS NULL) OR (kind='workspace' AND workspace_id IS NOT NULL AND team_id IS NULL) OR (kind='team' AND workspace_id IS NOT NULL AND team_id IS NOT NULL)"],
'runtime_session_bindings':["(audience_kind='personal' AND customer_user_id IS NOT NULL AND team_member_id IS NULL) OR (audience_kind='team' AND customer_user_id IS NULL AND team_member_id IS NOT NULL)","generation>0"],
'knowledge_reviews':["num_nonnulls(document_version_id,memory_candidate_id)=1"],
'reception_waits':["status NOT IN ('open','resuming','consumed') OR interrupt_id IS NOT NULL"],
'files':["num_nonnulls(ticket_id,channel_id,document_id,report_id,unit_id)=1","(scope_kind='ticket' AND ticket_id IS NOT NULL) OR (scope_kind='channel' AND channel_id IS NOT NULL) OR (scope_kind='document' AND document_id IS NOT NULL) OR (scope_kind='report' AND report_id IS NOT NULL) OR (scope_kind='resident' AND unit_id IS NOT NULL)","status<>'ready' OR accepted_object_id IS NOT NULL"],
'file_objects':["size_bytes>=0","sha256 ~ '^[0-9a-f]{64}$'","variant_revision>0","variant='original' OR source_object_id IS NOT NULL","status<>'ready' OR (scan_status='clean' AND verified_at IS NOT NULL)","version_id<>'' AND version_id<>'null'"],
'file_uploads':["expected_size_bytes>0 AND expected_size_bytes<=max_size_bytes","upload_mode<>'multipart' OR multipart_upload_id IS NOT NULL"],
'file_upload_parts':["part_number BETWEEN 1 AND 10000","size_bytes>0"],
'work_approvals':["num_nonnulls(requested_to_user_id,required_scope_id)=1"],
'ticket_reviews':["score BETWEEN 1 AND 5"],
'payments':["amount>0"],'refunds':["amount>0"],'payment_allocations':["amount>0"],'refund_allocations':["amount>0"],
'invoice_lines':["quantity>0 AND unit_price>=0","tax_rate BETWEEN 0 AND 1","discount>=0","total_amount=net_amount+tax_amount"],
'invoices':["grand_total=subtotal+tax_total-discount_total","grand_total>=0"],
'triage_policy_versions':["version_no>0","unknown_priority IN ('normal','high','critical')","review_timeout_seconds>0 AND max_fact_age_seconds>0 AND max_queue_wait_seconds>0","status<>'published' OR (published_by IS NOT NULL AND published_at IS NOT NULL)"],
'triage_policy_bindings':["valid_to IS NULL OR valid_to>valid_from"],
'triage_rules':["precedence>0","rule_kind<>'emergency_floor' OR severity_result<>'not_applicable'"],
'ticket_assessments':["ticket_generation>=0 AND basis_ticket_version>=0","confidence IS NULL OR confidence BETWEEN 0 AND 1","(assessor_kind='agent' AND source_run_id IS NOT NULL AND assessor_user_id IS NULL) OR (assessor_kind='human' AND assessor_user_id IS NOT NULL AND source_run_id IS NULL) OR (assessor_kind='system' AND assessor_user_id IS NULL AND source_run_id IS NULL)"],
'ticket_assessment_evidence':["num_nonnulls(message_id,event_id,evidence_item_id)=1","(evidence_item_id IS NULL)=(object_id IS NULL)"],
'ticket_triage_decisions':["ticket_generation>=0 AND decision_seq>0","NOT is_emergency OR priority='critical'","(outcome='applied')=(applied_ticket_version IS NOT NULL)","(decision_mode IN ('human_confirmed','human_override') AND approved_by IS NOT NULL AND review_id IS NOT NULL) OR (decision_mode IN ('automatic','provisional') AND approved_by IS NULL)"],
'ticket_sla_cycles':["response_minutes_snapshot>0 AND resolution_minutes_snapshot>0","ticket_generation>=0"],
'ticket_sla_adjustments':["adjustment_kind<>'exception_extend' OR authorized_by IS NOT NULL"],
'dispatch_queue':["priority_rank IN (10,20,30,40)","NOT is_emergency OR priority_rank=40"],
'dispatch_attempts':["priority_rank_snapshot IN (10,20,30,40)","status<>'offered' OR assignment_id IS NOT NULL"],
'work_reassignment_requests':["num_nonnulls(requested_by,source_run_id)=1","status NOT IN ('executing','completed') OR (approved_by IS NOT NULL AND safe_stop_confirmed_by IS NOT NULL AND safe_stop_confirmed_at IS NOT NULL)","status<>'completed' OR new_assignment_id IS NOT NULL"],
'sla_policies':["response_minutes>0 AND resolution_minutes>0","effective_to IS NULL OR effective_to>effective_from","clock_basis='elapsed_24x7'"],
'tickets':["priority IS NULL OR priority IN ('low','normal','high','critical')","severity IN ('unknown','minor','moderate','major','critical','not_applicable')","request_kind IN ('incident','service_request')","NOT is_emergency OR priority='critical'"],
}
def raw(s):return 'sql`'+s+'`'
header='''// Generated by scripts/generate-db-schema.py from the reviewed V2 + V3 dictionaries.
// Framework-owned checkpoint/session tables intentionally do not belong to this schema.
import { sql } from "drizzle-orm";
import { pgTable, pgEnum, text, uuid, integer, smallint, bigint, boolean, timestamp, numeric, char, vector, customType, primaryKey, unique, uniqueIndex, index, check, foreignKey, pgPolicy, type PgTableExtraConfigValue } from "drizzle-orm/pg-core";
import { jsonb } from "./json";
export const role = pgEnum("role", ["admin", "user"]); // Read-only legacy migration data.
export const agentType = pgEnum("agent_type", ["built_in", "remote_ag_ui", "remote_mastra"]);
export const credentialKind = pgEnum("credential_kind", ["model", "connector", "agent", "mcp", "mcp_oauth_client", "mcp_user_token"]);
export const agentVisibility = pgEnum("agent_visibility", ["public", "private"]);
export const routineRunStatus = pgEnum("routine_run_status", ["succeeded", "failed", "skipped"]);
const bytea = customType<{data: Buffer; driverData: Buffer}>({dataType: () => "bytea"});
const tsvector = customType<{data: string}>({dataType: () => "tsvector"});
'''
result=[header]
for n,m in M.items():
 cols={r[0]:r for r in m['rows']}; pk=re.search(r'PK\(([^)]+)\)',m['rules'])
 pkcols=[s.strip() for s in pk[1].split(',')] if pk else [r[0] for r in m['rows'] if 'PK' in r[2]]
 if n=='sandboxed_components':pkcols=['tenant_id','name']
 fields=[];constraints=[]
 for c,typ,flags,desc in m['rows']:
  a=json.dumps(c); b=typ.upper()
  if b in enum_types:e=f'{enum_types[b]}({a})'
  elif b in ['TEXT','UUID','SMALLINT','BYTEA','TSVECTOR','JSONB']:e=f'{b.lower()}({a})'
  elif b in ['INT','INTEGER']:e=f'integer({a})'
  elif b in ['BOOL','BOOLEAN']:e=f'boolean({a})'
  elif b=='BIGINT':e=f'bigint({a}, {{ mode: "number" }})'
  elif b=='TEXT[]':e=f'text({a}).array()'
  elif b=='TIMESTAMPTZ':e=f'timestamp({a}, {{ withTimezone: true }})'
  elif b.startswith('NUMERIC'):
   p,s=map(int,re.findall(r'\d+',b));e=f'numeric({a}, {{ precision: {p}, scale: {s} }})'
  elif b.startswith('CHAR'):e=f'char({a}, {{ length: 3 }})'
  elif b.startswith('VECTOR'):e=f'vector({a}, {{ dimensions: 1536 }})'
  else:raise ValueError((n,c,b))
  if len(pkcols)==1 and c in pkcols:e+='.primaryKey()'
  elif 'NOT NULL' in flags:e+='.notNull()'
  default=re.search(r'DEFAULT ([^;]+)',flags)
  if default:
   d=default[1].strip()
   if d=='gen_random_uuid()':e+='.defaultRandom()'
   elif d=='now()':e+='.defaultNow()'
   elif b in ['TEXT','CHAR(3)'] or b.startswith('NUMERIC'):e+='.default('+json.dumps(d.strip('"\''))+')'
   elif d in ['{}','[]','true','false'] or re.fullmatch(r'-?\d+',d):e+='.default('+d+')'
   else:e+='.default('+raw(d)+')'
  elif (n,c) in defaults:e+='.default('+json.dumps(defaults[n,c])+')'
  # Legacy code obtains tenant/workspace from a trusted deployment-scoped DB connection.
  # Missing scope fails closed; no constant tenant is silently assigned.
  elif n in compat and c=='tenant_id' and 'NOT NULL' in flags:e+='.default(sql`nullif(current_setting(\'app.tenant_id\', true), \'\')::uuid`)'
  elif n in ['agents','channels','sandboxed_components'] and c=='workspace_id':e+='.default(sql`nullif(current_setting(\'app.workspace_id\', true), \'\')::uuid`)'
  if c=='updated_at':e+='.$onUpdate(() => new Date())'
  fields.append(f'  /** {desc.replace("*/", "")} */\n  {camel(c)}: {e},')
  fk=re.search(r'`(\w+)\.(\w+)`',flags)
  if fk:
   target,tc=fk.groups(); targetcols={r[0]:r for r in M[target]['rows']}
   composite=c!='tenant_id' and 'tenant_id' in cols and 'tenant_id' in targetcols and 'NOT NULL' in targetcols['tenant_id'][2]
   source=['tenant_id',c] if composite else [c];dest=['tenant_id',tc] if composite else [tc]
   sn=', '.join('t.'+camel(k) for k in source);dn=', '.join(names[target]+'.'+camel(k) for k in dest)
   delete='cascade' if n in ['sessions','accounts','user_instructions'] and target=='users' else 'restrict'
   constraints.append(f'foreignKey({{name: "{ident(n+"_"+c+"_fk")}", columns: [{sn}], foreignColumns: [{dn}]}}).onDelete("{delete}")')
 if len(pkcols)>1:constraints.append('primaryKey({columns: ['+', '.join('t.'+camel(c) for c in pkcols)+']})')
 if 'tenant_id' in cols:
  key='id' if 'id' in cols else pkcols[0] if len(pkcols)==1 else None
  if key and key!='tenant_id':constraints.append(f'unique("{ident(n+"_tenant_key_uq")}").on(t.tenantId,t.{camel(key)})')
  # Deployed server connections are tenant-bound; absent context sees no tenant records.
  pred="tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid"
  if 'NULL'==cols['tenant_id'][2].split(';')[0]:pred+=' OR tenant_id IS NULL'
  constraints.append(f'pgPolicy("{ident(n+"_tenant_policy")}", {{for: "all", using: {raw(pred)}, withCheck: {raw(pred)}}})')
 uq=[]
 for x in re.findall(r'(?:UNIQUE|UQ)\(([^()]+)\)',m['rules']):
  keys=[p.strip() for p in x.split(',')]
  if all(k in cols for k in keys) and keys!=pkcols:uq.append(','.join(keys))
 uq+=extra_unique.get(n,[])
 skip={p[0] for p in partial.get(n,[])}
 if n=='runtime_session_bindings':skip|={'identity_id,runtime_session_key,checkpoint_namespace'}
 if n=='skills':uq=[]
 if n=='tickets':uq=[key for key in uq if key!='channel_id']
 for k,key in enumerate(dict.fromkeys(uq)):
  if key in skip:continue
  constraints.append(f'unique("{ident(n+"_unique_"+str(k))}").on('+','.join('t.'+camel(c) for c in key.split(','))+')')
 for k,(key,where) in enumerate(partial.get(n,[])):
  if all(c in cols for c in key.split(',')):args=','.join('t.'+camel(c) for c in key.split(','))
  else:args=raw(key)
  constraints.append(f'uniqueIndex("{ident(n+"_partial_"+str(k))}").on({args}).where({raw(where)})')
 ch=list(checks.get(n,[]))
 # Read explicit slash-separated enum domains, without guessing arbitrary prose.
 for c,typ,flags,desc in m['rows']:
  if typ=='TEXT':
   match=re.search(r'\b'+re.escape(c)+r'\s+([a-z][a-z_]*(?:/[a-z][a-z_]*)+)',m['rules'])
   if not match and re.match(r'^[a-z][a-z_]*(?:/[a-z][a-z_]*)+',desc):match=re.match(r'([a-z][a-z_]*(?:/[a-z][a-z_]*)+)',desc)
   if match:
    vals=match[1].split('/');ch.append(c+' IN ('+','.join("'"+v+"'" for v in vals)+')')
 for k,c in enumerate(dict.fromkeys(ch)):constraints.append(f'check("{ident(n+"_check_"+str(k))}", {raw(c)})')
 for c in ['ticket_id','run_id','workspace_id','user_id','namespace_id']:
  if c in cols and c not in pkcols:constraints.append(f'index("{ident(n+"_"+c+"_idx")}").on('+('t.tenantId,' if 'tenant_id' in cols else '')+'t.'+camel(c)+')')
 result.append(f'\n/** {m["purpose"]}. See docs V2/V3 for operation-level invariants. */\nexport const {names[n]} = pgTable("{n}", {{\n'+ '\n'.join(fields)+'\n}, (t): PgTableExtraConfigValue[] => [\n  '+',\n  '.join(constraints)+'\n]);\n')
(OUT/'tables.ts').write_text(''.join(result),encoding='utf8')
# Preserve established import paths, all sharing the same table objects.
groups={}
for n,m in M.items():
 if m.get('source'):groups.setdefault(Path(m['source']).name,[]).append(names[n])
for file,exports in groups.items():
 if file=='core.ts':exports+=['role','agentType','credentialKind']
 if file=='coworker.ts':exports+=['agentVisibility','routineRunStatus']
 (OUT/file).write_text('// Compatibility import path; canonical schema is tables.ts.\nexport { '+', '.join(exports)+' } from "./tables";\n',encoding='utf8')
(OUT/'index.ts').write_text('/** Canonical application schema; excludes framework-managed runtime tables. */\nexport * from "./tables";\nexport * from "./security";\n',encoding='utf8')
(OUT.parent/'design/merged.json').write_text(json.dumps(M,ensure_ascii=False,indent=2),encoding='utf8')
extra=[]
immutable=['ticket_events','agent_versions','context_snapshots','knowledge_chunks','ticket_assessments','ticket_assessment_evidence','ticket_triage_decisions','ticket_sla_adjustments','payment_allocations','refund_allocations','file_access_logs','work_approval_evidence','runtime_identities']
for n,m in M.items():
 cs={r[0]:r for r in m['rows']}
 if 'tenant_id' in cs:extra.append(f'ALTER TABLE "{n}" FORCE ROW LEVEL SECURITY;')
 if 'updated_at' in cs and n not in immutable:extra.append(f'CREATE TRIGGER "{ident(n+"_touch")}" BEFORE UPDATE ON "{n}" FOR EACH ROW EXECUTE FUNCTION app_touch_updated_at();')
 if n in immutable:
  # Identity lifecycle may be revoked, but its mapping must not be reassigned.
  if n=='runtime_identities':continue
  extra.append(f'CREATE TRIGGER "{ident(n+"_immutable")}" BEFORE UPDATE OR DELETE ON "{n}" FOR EACH ROW EXECUTE FUNCTION app_append_only();')
  extra.append(f'CREATE TRIGGER "{ident(n+"_no_truncate")}" BEFORE TRUNCATE ON "{n}" FOR EACH STATEMENT EXECUTE FUNCTION app_append_only();')
extra += ['ALTER TABLE runtime_session_bindings ADD CONSTRAINT binding_identity_backend_fk FOREIGN KEY(tenant_id,identity_id,backend_id) REFERENCES runtime_identities(tenant_id,id,backend_id);',
 'CREATE INDEX dispatch_queue_priority_idx ON dispatch_queue(tenant_id,management_unit_id,is_emergency DESC,priority_rank DESC,dispatch_due_at,eligible_since,id) WHERE state=\'waiting\';',
 'CREATE INDEX triage_reviews_due_idx ON ticket_triage_reviews(tenant_id,due_at) WHERE status IN (\'pending\',\'claimed\');',
 'CREATE INDEX escalation_notify_idx ON ticket_escalations(tenant_id,next_notify_at) WHERE status IN (\'open\',\'acknowledged\');',
 'CREATE INDEX knowledge_chunks_search_idx ON knowledge_chunks USING gin(search_tsv);']
(OUT.parent/'generated-invariants.sql').write_text('-- Generated companion DDL. Included by db:generate, not a migration journal.\n'+'\n--> statement-breakpoint\n'.join(extra)+'\n',encoding='utf8')
print(f'Generated {len(M)} application tables.')
