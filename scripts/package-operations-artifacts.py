"""Package only the final Operations acceptance evidence requested by the user.

Default: inspect and print a deterministic plan. Writing requires --final-ready after the final
verification has completed. No environment files, account files, dumps or unselected captures.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.codex-artifacts/operations-ui-2026-10-06'
REPORT = ROOT / 'docs/UI_PLATFORM_UPDATE_2026-10-06.md'
TARGET = ROOT / '.codex-artifacts/packages/operations-ui-2026-10-06'
FIXED_ZIP_TIME = (2026, 10, 6, 0, 0, 0)
JSON_FILES = ('verification.json', 'ui-test-results.json', 'runtime-acceptance.json',
              'factory-acceptance.json', 'factory-building-only-refusal.json',
              'session-runtime-acceptance.json', 'deployment.json')
LOG_FILES = ('api-final.log', 'api-graph-connections.log', 'coordination-final.log', 'factory-final.log')


def load_json(name):
    return json.loads((SOURCE / name).read_text(encoding='utf-8-sig'))


def safe_name(name, suffix):
    if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name or not name.endswith(suffix):
        raise ValueError(f'Invalid evidence filename: {name!r}')
    return name


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def package_files():
    verification = load_json('verification.json')
    if not isinstance(verification, list) or not verification:
        raise ValueError('Final browser verification must contain captured states.')
    if any(row.get('overflow') or row.get('errors') or row.get('primary_visible') is False
           or row.get('session_header_height', 0) > 96 for row in verification):
        raise ValueError('Browser verification contains a failed check.')
    screenshots = sorted({safe_name(row['screenshot'], '.png') for row in verification})
    ui_results = load_json('ui-test-results.json')
    if not ui_results or any(row['exit_code'] != 0 for row in ui_results):
        raise ValueError('Final UI test results contain a failed run.')
    ui_logs = sorted({safe_name(row.get('log', row['file'] + '.final.log'), '.final.log') for row in ui_results})
    files = {}
    for name in sorted(set(JSON_FILES + LOG_FILES) | set(screenshots) | set(ui_logs)):
        path = SOURCE / name
        if not path.is_file():
            raise ValueError(f'Missing selected final evidence: {name}')
        files['evidence/' + name] = path.read_bytes()
    report = REPORT.read_text(encoding='utf-8-sig')
    report = report.replace('../.codex-artifacts/operations-ui-2026-10-06/', 'evidence/')
    report = report.replace('../deploy/vinhomes/README.md', 'deployment-guide.md')
    report = report.replace('../.codex-artifacts/packages/operations-ui-2026-10-06/README.md', 'README.md')
    report = report.replace('../.codex-artifacts/packages/operations-ui-2026-10-06.zip', '../operations-ui-2026-10-06.zip')
    files[REPORT.name] = report.encode('utf-8')
    guide = (ROOT / 'deploy/vinhomes/README.md').read_text(encoding='utf-8-sig')
    guide = guide.replace('[biên bản nghiệm thu](../../docs/teams/chien/COMPLETION_ACCEPTANCE_2026-10-05.md)',
                          'biên bản nghiệm thu ngày 05/10 trong repository gốc (tài liệu lịch sử, không kèm gói này)')
    files['deployment-guide.md'] = guide.encode('utf-8')
    # Verify every report link points to a packaged target, including the evidence folder itself.
    for link in re.findall(r'\]\(([^)]+)\)', report):
        if '://' in link or link.startswith('#'):
            continue
        target = link.split('#', 1)[0]
        if target and not (target in files or target in ('evidence/', 'README.md', '../operations-ui-2026-10-06.zip')):
            raise ValueError(f'Report link is outside the package: {target}')
    readme = f'''# Bàn giao UI Platform BQL và Admin — 06/10/2026

Giao diện local: **http://localhost:3022/operations**. API local: **http://127.0.0.1:8020**.
Dùng tài khoản hiện có. Gói này không chứa mật khẩu, token, file môi trường hoặc bản dump database.
Mã nguồn trong workspace chưa commit hoặc push theo yêu cầu của người dùng.

- Đọc [báo cáo triển khai]({REPORT.name}) để xem chức năng, quyền, kết quả và giới hạn.
- [Kiểm chứng browser](evidence/verification.json) tham chiếu đúng {len(screenshots)} ảnh cuối của {len(verification)} màn/trạng thái; ảnh cũ không được đưa vào gói.
- [Kết quả UI](evidence/ui-test-results.json) đi kèm {len(ui_logs)} log `.final.log` tương ứng.
- [API](evidence/api-final.log), [graph/kết nối](evidence/api-graph-connections.log), [coordination](evidence/coordination-final.log), [Factory](evidence/factory-final.log) lưu kết quả kiểm thử cuối. Số bài bỏ qua giữ nguyên trong log.
- [Hỏi agent riêng](evidence/runtime-acceptance.json), [hỏi trong phiên](evidence/session-runtime-acceptance.json), [Factory thành công](evidence/factory-acceptance.json), [Factory giữ an toàn khi mở rộng phạm vi](evidence/factory-building-only-refusal.json) ghi nghiệm thu dùng model thật.
- [Docker/database/backup](evidence/deployment.json) ghi snapshot local; [hướng dẫn triển khai](deployment-guide.md) là tài liệu trong repository, có ghi chú lịch sử từ đợt trước.

Phạm vi đã nghiệm thu là **Docker local**, chưa phải production host/domain/TLS bên ngoài hoặc restore off-host. Cơ chế MCP ghi từng lần đã được kiểm tra với PostgreSQL và host kiểm soát trong test; chưa nghiệm thu kết nối thật Google Drive/Lịch Google/kho vật tư. Supervisor vẫn tự duyệt phương án; ghi qua MCP vẫn cần BQL cho phép từng lần. Agent Factory nghiệm thu còn là bản nháp, chưa tự phát hành.

`manifest.json` ghi kích thước và SHA256 từng tệp nội dung. `SHA256SUMS` gồm các tệp nội dung và manifest; checksum của chính `SHA256SUMS` không tự tham chiếu. Bản ZIP, nếu có, chứa cùng bộ tệp với thứ tự và metadata thời gian cố định. Có thể kiểm tra bằng PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\\evidence\\verification.json
```

Các script kiểm chứng nằm trong thư mục `scripts/` của repository gốc. Script đóng gói `scripts/package-operations-artifacts.py` chọn bằng danh sách cho phép; chạy không tham số chỉ in kế hoạch, `--final-ready --zip` mới ghi gói bàn giao.
'''
    files['README.md'] = readme.encode('utf-8')
    # Refuse recognizable raw credentials without ever echoing the matched value.
    secret_pattern = re.compile(r'Bearer\s+[A-Za-z0-9_-]{24,}|sk-[A-Za-z0-9_-]{24,}|postgres(?:ql)?(?:\+asyncpg)?://[^\s:/]+:[^\s@]+@')
    for name, content in files.items():
        if not name.endswith('.png') and secret_pattern.search(content.decode('utf-8', errors='replace')):
            raise ValueError(f'Raw credential pattern found; packaging refused for {name}')
    manifest = {'package': TARGET.name, 'scope': 'local Docker UI and runtime acceptance',
                'browser_states': len(verification), 'screenshots': len(screenshots), 'ui_test_files': len(ui_logs),
                'files': [{'path': name, 'bytes': len(data), 'sha256': sha256(data)} for name, data in sorted(files.items())]}
    files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    files['SHA256SUMS'] = ''.join(f'{sha256(data)}  {name}\n' for name, data in sorted(files.items())).encode('utf-8')
    return files, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final-ready', action='store_true', help='Write only after the final verification is ready.')
    parser.add_argument('--zip', action='store_true', help='Create deterministic ZIP alongside the directory.')
    args = parser.parse_args()
    files, manifest = package_files()
    result = {'target': str(TARGET.relative_to(ROOT)), 'file_count': len(files),
              'browser_states': manifest['browser_states'], 'screenshots': manifest['screenshots'],
              'ui_test_files': manifest['ui_test_files'], 'bytes': sum(map(len, files.values())),
              'writing': args.final_ready, 'files': sorted(files)}
    if args.final_ready:
        unexpected = {p.relative_to(TARGET).as_posix() for p in TARGET.rglob('*') if p.is_file()} - set(files) if TARGET.exists() else set()
        if unexpected:
            raise ValueError('Destination contains unselected files; no files removed: ' + ', '.join(sorted(unexpected)))
        for name, data in sorted(files.items()):
            path = TARGET / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        # Check the copied bytes, not just the source inventory.
        for row in manifest['files']:
            assert sha256((TARGET / row['path']).read_bytes()) == row['sha256'], row['path']
        if args.zip:
            zip_path = TARGET.with_suffix('.zip')
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for name, data in sorted(files.items()):
                    item = zipfile.ZipInfo(TARGET.name + '/' + name, date_time=FIXED_ZIP_TIME)
                    item.compress_type = zipfile.ZIP_DEFLATED
                    item.create_system = 3
                    item.external_attr = 0o100644 << 16
                    archive.writestr(item, data)
            result['zip'] = str(zip_path.relative_to(ROOT))
            result['zip_sha256'] = sha256(zip_path.read_bytes())
            with zipfile.ZipFile(zip_path, 'r') as archive:
                assert archive.testzip() is None, 'ZIP integrity failure'
                assert set(archive.namelist()) == {TARGET.name + '/' + name for name in files}
                for name, data in files.items():
                    assert sha256(archive.read(TARGET.name + '/' + name)) == sha256(data), name
            result['zip_integrity'] = 'passed'
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
