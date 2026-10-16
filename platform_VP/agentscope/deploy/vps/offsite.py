#!/usr/bin/env python3
"""Encrypt before SFTP; restore only into a new private, isolated directory.

Requires the age CLI. The backup host holds public recipients, never identities.
No secrets or plaintext backup files are sent to the configured SFTP target.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
import tarfile
import tempfile
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"host", "user", "port", "directory", "ssh_identity", "known_hosts", "recipients_file", "environment", "source_revision"}
    if set(config) != required:
        raise ValueError("Offsite config must contain exactly the documented fields")
    for key in ("host", "user"):
        if not isinstance(config[key], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", config[key]):
            raise ValueError(f"Invalid offsite {key}")
    if type(config["port"]) is not int or not 1 <= config["port"] <= 65535:
        raise ValueError("Invalid SFTP port")
    directory = config["directory"]
    if not isinstance(directory, str) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", directory) or directory == "/" or any(part in ("", ".", "..") for part in directory[1:].split("/")):
        raise ValueError("Use an explicit absolute SFTP directory without traversal")
    for key in ("ssh_identity", "known_hosts", "recipients_file"):
        candidate = Path(config[key])
        if not candidate.is_absolute() or not candidate.is_file() or candidate.is_symlink() or any(char in str(candidate) for char in ('\n', '\r', '"')):
            raise ValueError(f"{key} must be an existing absolute regular file")
    recipients = Path(config["recipients_file"]).read_text(encoding="utf-8")
    values = [line.strip() for line in recipients.splitlines() if line.strip() and not line.startswith("#")]
    if not values or any(not re.fullmatch(r"age1[0-9a-z]+", value) for value in values) or "AGE-SECRET-KEY" in recipients:
        raise ValueError("Backup host accepts only age public recipients, never private identities")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config["environment"]) or not re.fullmatch(r"[a-fA-F0-9]{7,64}(?:-dirty)?", config["source_revision"]):
        raise ValueError("Set explicit environment and source revision (append -dirty for WIP)")
    return config


def sftp(config: dict, lines: list[str]) -> None:
    command = ["sftp", "-b", "-", "-P", str(config["port"]), "-i", config["ssh_identity"], "-oBatchMode=yes", "-oStrictHostKeyChecking=yes", f"-oUserKnownHostsFile={config['known_hosts']}", f"{config['user']}@{config['host']}"]
    subprocess.run(command, input="\n".join(lines) + "\n", text=True, check=True, stdout=subprocess.DEVNULL)


def quoted(path: str | Path) -> str:
    value = str(path)
    if any(char in value for char in ('\n', '\r', '"', '\\')):
        raise ValueError("Unsafe SFTP path")
    return '"' + value + '"'


def validate_backup(backup: Path) -> list[Path]:
    if not (backup / "COMPLETE").is_file():
        raise ValueError("Backup is incomplete")
    required = {"postgres.dump", "redis.tar.gz", "minio.tar.gz", "workspaces.tar.gz", "runtime.env", "migration-head", "database-counts.json"}
    entries: set[str] = set()
    for line in (backup / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64}) [ *]([^/\\]+)", line)
        if not match or match[2] in (".", "..") or match[2] in entries:
            raise ValueError("Invalid backup checksum manifest")
        path = backup / match[2]
        if path.is_symlink() or not path.is_file() or digest(path) != match[1]:
            raise ValueError("Backup checksum mismatch")
        entries.add(match[2])
    if not required <= entries:
        raise ValueError("Backup manifest is missing a required store/config")
    files = list(backup.iterdir())
    if any(path.is_symlink() or not path.is_file() or path.name not in entries | {"SHA256SUMS", "COMPLETE"} for path in files):
        raise ValueError("Untracked or non-regular files in backup directory")
    return files


def encrypt(backup: Path, recipients: Path, output: Path) -> None:
    files = validate_backup(backup)
    process = subprocess.Popen(["age", "--encrypt", "--recipients-file", str(recipients), "--output", str(output)], stdin=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
            for path in sorted(files):
                archive.add(path, arcname=path.name, recursive=False)
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("age encryption failed")
    except BaseException:
        process.kill()
        process.wait()
        raise
    output.chmod(0o600)


def unpack(archive: Path, target: Path) -> None:
    """Accept only a flat backup directory; no links, devices or traversal."""
    target.mkdir(mode=0o700)
    with tarfile.open(archive, "r:") as stream:
        names: set[str] = set()
        for member in stream:
            if not member.isfile() or PurePosixPath(member.name).name != member.name or member.name in (".", "..") or member.name in names or "\\" in member.name:
                raise ValueError("Unsafe or duplicate archive entry")
            names.add(member.name)
            with stream.extractfile(member) as source, (target / member.name).open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
            (target / member.name).chmod(0o600)
    validate_backup(target)


def upload(backup: Path, config: dict, evidence: Path) -> dict:
    started = time.monotonic()
    backup = backup.resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", backup.name):
        raise ValueError("Unsafe backup name")
    # Retry never overwrites ciphertext referenced by an older trusted receipt.
    artifact = backup.name + "-" + secrets.token_hex(4) + ".tar.age"
    remote = config["directory"] + "/" + artifact
    # Validate before any network operation. The temporary plaintext archive is never materialized.
    with tempfile.TemporaryDirectory(prefix="awp-encrypted-") as workspace:
        local = Path(workspace) / artifact
        encrypt(backup, Path(config["recipients_file"]), local)
        metadata = json.loads((backup / "backup-evidence.json").read_text()) if (backup / "backup-evidence.json").is_file() else {}
        receipt = {"schema_version": 1, "environment": config["environment"], "source_revision": config["source_revision"], "backup_name": backup.name, "artifact": artifact, "encrypted_sha256": digest(local), "encrypted_bytes": local.stat().st_size, "backup_created_at": metadata.get("started_at") or (backup / "created-at").read_text().strip(), "uploaded_at": utc_now(), "transfer_verified": False, "restore_verified": False, "target": {key: config[key] for key in ("host", "user", "port", "directory")}}
        sftp(config, [f"put {quoted(local)} {quoted(remote + '.part')}", f"rename {quoted(remote + '.part')} {quoted(remote)}"])
        downloaded = Path(workspace) / "verify.age"
        sftp(config, [f"get {quoted(remote)} {quoted(downloaded)}"])
        if digest(downloaded) != receipt["encrypted_sha256"]:
            raise ValueError("Offsite ciphertext read-back checksum mismatch")
        receipt.update(transfer_verified=True, verified_at=utc_now(), duration_seconds=round(time.monotonic() - started, 3))
        receipt_path = Path(workspace) / "receipt.json"
        write_json(receipt_path, receipt)
        sftp(config, [f"put {quoted(receipt_path)} {quoted(remote + '.receipt.json.part')}", f"rename {quoted(remote + '.receipt.json.part')} {quoted(remote + '.receipt.json')}"])
        write_json(evidence, receipt)
    return receipt


def restore(receipt_path: Path, config: dict, identity: Path, work_root: Path, evidence: Path) -> dict:
    started = time.monotonic()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("transfer_verified") is not True or receipt.get("target") != {key: config[key] for key in ("host", "user", "port", "directory")}:
        raise ValueError("Use a trusted local receipt for this exact offsite target")
    artifact = receipt.get("artifact", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.tar\.age", artifact) or not re.fullmatch(r"[a-f0-9]{64}", receipt.get("encrypted_sha256", "")):
        raise ValueError("Invalid offsite receipt")
    if identity.is_symlink() or not identity.is_file():
        raise ValueError("Recovery identity must be a regular file")
    identity = identity.resolve(strict=True)
    if identity == Path(config["ssh_identity"]).resolve() or identity == Path(config["recipients_file"]).resolve() or "AGE-SECRET-KEY-" not in identity.read_text(encoding="utf-8"):
        raise ValueError("Restore requires a separate age private identity from the recovery custodian")
    work_root = work_root.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="awp-offsite-restore-", dir=work_root) as workspace:
        directory = Path(workspace)
        directory.chmod(0o700)
        encrypted = directory / "backup.age"
        sftp(config, [f"get {quoted(config['directory'] + '/' + artifact)} {quoted(encrypted)}"])
        if encrypted.stat().st_size != receipt["encrypted_bytes"] or digest(encrypted) != receipt["encrypted_sha256"]:
            raise ValueError("Offsite ciphertext checksum mismatch")
        plaintext = directory / "backup.tar"
        subprocess.run(["age", "--decrypt", "--identity", str(identity), "--output", str(plaintext), str(encrypted)], check=True)
        plaintext.chmod(0o600)
        backup = directory / "backup"
        unpack(plaintext, backup)
        restore_evidence = directory / "restore.json"
        environment = dict(os.environ, RESTORE_EVIDENCE=str(restore_evidence), DEPLOY_ENVIRONMENT=config["environment"], SOURCE_REVISION=config["source_revision"])
        subprocess.run(["bash", str(Path(__file__).with_name("verify-restore.sh")), str(backup)], env=environment, check=True)
        checks = json.loads(restore_evidence.read_text(encoding="utf-8"))
        if checks.get("status") != "PASS":
            raise ValueError("Isolated restore did not produce passing evidence")
        result = {"schema_version": 1, "status": "PASS", "scope": "offsite_download_decrypt_isolated_four_store_restore", "environment": config["environment"], "source_revision": config["source_revision"], "backup_name": receipt["backup_name"], "encrypted_sha256": receipt["encrypted_sha256"], "finished_at": utc_now(), "duration_seconds": round(time.monotonic() - started, 3), "checks": checks, "production_cutover_verified": False}
        write_json(evidence, result)
    return result


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upload", "upload-latest", "restore"))
    parser.add_argument("path", type=Path, help="Backup directory/root for upload, trusted local receipt for restore")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--work-root", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.action == "restore":
        if not args.identity or not args.work_root:
            parser.error("restore requires --identity and --work-root on the recovery host")
        result = restore(args.path, config, args.identity, args.work_root, args.evidence)
    else:
        backup = args.path
        if args.action == "upload-latest":
            candidates = sorted(path for path in backup.iterdir() if path.is_dir() and (path / "COMPLETE").is_file())
            if not candidates:
                raise ValueError("No completed backup exists")
            backup = candidates[-1]
        result = upload(backup, config, args.evidence)
    print(json.dumps({key: result[key] for key in ("environment", "source_revision", "backup_name")}))


if __name__ == "__main__":
    main()
