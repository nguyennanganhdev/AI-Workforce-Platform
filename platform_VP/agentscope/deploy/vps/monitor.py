#!/usr/bin/env python3
"""Local structured alerts for systemd; no email/webhook is sent."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import urllib.request


def age_hours(value, now):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Evidence time must be timezone aware')
    return (now - parsed).total_seconds() / 3600


def check(config, now=None):
    now = now or datetime.now(timezone.utc)
    alerts = []
    backups = sorted(p for p in Path(config['backup_root']).iterdir() if (p/'COMPLETE').is_file())
    backup = backups[-1] if backups else None
    if not backup:
        alerts.append('BACKUP_MISSING')
        backup_age = None
    else:
        metadata = backup/'backup-evidence.json'
        at = json.loads(metadata.read_text())['started_at'] if metadata.exists() else (backup/'created-at').read_text().strip()
        backup_age = age_hours(at, now)
        if backup_age < 0 or backup_age > config['rpo_hours']:alerts.append('BACKUP_RPO_EXCEEDED')
    receipt_path = Path(config['offsite_receipt'])
    offsite_age = None
    if not receipt_path.exists():alerts.append('OFFSITE_MISSING')
    else:
        receipt = json.loads(receipt_path.read_text())
        offsite_age = age_hours(receipt['backup_created_at'], now)
        if receipt.get('transfer_verified') is not True:alerts.append('OFFSITE_NOT_VERIFIED')
        if offsite_age < 0 or offsite_age > config['rpo_hours']:alerts.append('OFFSITE_RPO_EXCEEDED')
    restore_path = Path(config['restore_evidence'])
    if not restore_path.exists():alerts.append('RESTORE_NOT_REHEARSED')
    else:
        restored = json.loads(restore_path.read_text())
        if restored.get('status') != 'PASS':alerts.append('RESTORE_FAILED')
        if age_hours(restored['finished_at'], now) > config['restore_max_age_days'] * 24:alerts.append('RESTORE_REHEARSAL_STALE')
        if restored.get('duration_seconds', float('inf')) > config['rto_seconds']:alerts.append('RESTORE_RTO_EXCEEDED')
    disk = shutil.disk_usage(config['disk_path'])
    free_ratio = disk.free / disk.total
    if free_ratio < config['min_disk_free_ratio']:alerts.append('DISK_LOW')
    try:
        with urllib.request.urlopen(config['health_url'], timeout=10) as response:
            healthy = json.loads(response.read())
        # Inspect component failures, not merely HTTP 200.
        def failed(value):
            if value is False:return True
            if isinstance(value, dict):return any(failed(v) for v in value.values())
            return isinstance(value, str) and value.lower() in {'error','failed','unhealthy','down'}
        if failed(healthy):alerts.append('HEALTH_COMPONENT_FAILED')
    except Exception:
        alerts.append('HEALTH_UNREACHABLE')
    return {'schema_version':1,'status':'ALERT' if alerts else 'PASS','environment':config['environment'],
            'source_revision':config['source_revision'],'checked_at':now.isoformat(), 'alerts':alerts,
            'backup_age_hours':backup_age,'offsite_age_hours':offsite_age,'disk_free_ratio':free_ratio,
            'rpo_objective_hours':config['rpo_hours'],'rto_rehearsal_objective_seconds':config['rto_seconds'],
            'production_cutover_rto_measured':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args=parser.parse_args()
    try:result=check(json.loads(args.config.read_text()))
    except Exception as exc:result={'status':'ALERT','alerts':['MONITOR_CONFIG_OR_EVIDENCE_INVALID'],'error_type':type(exc).__name__}
    args.evidence.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    args.evidence.write_text(json.dumps(result,indent=2));args.evidence.chmod(0o600)
    print(json.dumps(result))
    raise SystemExit(result['status']!='PASS')
