"""Real encryption round-trip plus malicious archive/config/alert cases."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


def module(name):
    path = Path(__file__).resolve().parents[1]/"deploy/vps"/(name+".py")
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def backup(path):
    path.mkdir()
    for name in ["postgres.dump","redis.tar.gz","minio.tar.gz","workspaces.tar.gz","runtime.env","migration-head","database-counts.json","created-at"]:
        (path/name).write_text("backup fixture secret data" if name != "created-at" else "2026-10-16T00:00:00Z")
    (path/"SHA256SUMS").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.name+"\n" for p in sorted(path.iterdir())))
    (path/"COMPLETE").touch()


def test_real_age_roundtrip_wrong_key_corruption_and_no_plaintext_transport(tmp_path):
    offsite=module("offsite")
    if not shutil.which("age"):pytest.fail("Install age CLI to exercise real encryption")
    identity=tmp_path/"identity";other=tmp_path/"other"
    for key in [identity,other]:subprocess.run(["age-keygen","-o",str(key)],check=True,capture_output=True)
    recipient=tmp_path/"recipients";recipient.write_bytes(subprocess.check_output(["age-keygen","-y",str(identity)]))
    source=tmp_path/"source";backup(source)
    ciphertext=tmp_path/"backup.age";offsite.encrypt(source,recipient,ciphertext)
    assert b"backup fixture secret data" not in ciphertext.read_bytes()
    wrong=subprocess.run(["age","-d","-i",str(other),str(ciphertext)],capture_output=True)
    assert wrong.returncode != 0
    plaintext=tmp_path/"plain.tar"
    subprocess.run(["age","-d","-i",str(identity),"-o",str(plaintext),str(ciphertext)],check=True,capture_output=True)
    offsite.unpack(plaintext,tmp_path/"restored")
    assert (tmp_path/"restored/runtime.env").read_bytes()==(source/"runtime.env").read_bytes()
    corrupted=tmp_path/"corrupt.age";data=bytearray(ciphertext.read_bytes());data[-2]^=0x40;corrupted.write_bytes(data)
    assert subprocess.run(["age","-d","-i",str(identity),str(corrupted)],capture_output=True).returncode != 0


@pytest.mark.parametrize("name", ["../escape","/absolute","duplicate"])
def test_unsafe_archive_is_rejected(tmp_path,name):
    offsite=module("offsite");archive=tmp_path/"bad.tar"
    with tarfile.open(archive,"w") as t:
        entry=tarfile.TarInfo(name);entry.size=1;t.addfile(entry,io.BytesIO(b"x"))
        if name=="duplicate":t.addfile(entry,io.BytesIO(b"x"))
    with pytest.raises(ValueError):offsite.unpack(archive,tmp_path/"out")
    assert not (tmp_path/"escape").exists()


def test_checksum_and_config_fail_closed(tmp_path):
    offsite=module("offsite");source=tmp_path/"source";backup(source)
    (source/"runtime.env").write_text("tampered")
    with pytest.raises(ValueError,match="checksum"):offsite.validate_backup(source)
    config=tmp_path/"config.json";config.write_text('{"host":"-oProxyCommand=bad"}')
    with pytest.raises(ValueError):offsite.load_config(config)


def test_alerts_cover_missing_offsite_restore_rpo_and_http200_component_failure(tmp_path):
    monitor=module("monitor");root=tmp_path/"backups";root.mkdir();backup(root/"old")
    config={"backup_root":str(root),"offsite_receipt":str(tmp_path/"absent"),"restore_evidence":str(tmp_path/"absent-restore"),
            "disk_path":str(tmp_path),"rpo_hours":26,"restore_max_age_days":7,"rto_seconds":3600,
            "min_disk_free_ratio":0,"health_url":"http://unused.test/health","environment":"test","source_revision":"abc-dirty"}
    response=io.BytesIO(b'{"docker":false}')
    with patch.object(monitor.urllib.request,"urlopen",return_value=response):
        result=monitor.check(config,datetime(2026,10,18,tzinfo=timezone.utc))
    assert set(result["alerts"])=={"BACKUP_RPO_EXCEEDED","OFFSITE_MISSING","RESTORE_NOT_REHEARSED","HEALTH_COMPONENT_FAILED"}
    assert not result["production_cutover_rto_measured"]
