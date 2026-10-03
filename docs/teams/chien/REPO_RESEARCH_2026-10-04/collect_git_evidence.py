"""Read-only Git/GitHub evidence collection; writes only this report directory."""
import collections
import datetime as dt
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

def run(*args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    if p.returncode:
        raise RuntimeError(f'{args[0]} {args[1]} failed: {p.stderr.decode("utf-8", "replace")}')
    return p.stdout.decode('utf-8', 'replace').strip()

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

captured = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).isoformat()
refs = run('git', 'for-each-ref', '--sort=-committerdate', '--format=%(refname:short)|%(objectname)|%(committerdate:iso8601)|%(authorname)|%(subject)', 'refs/remotes/origin').splitlines()
branches = []
for row in refs:
    ref, sha, date, author, subject = row.split('|', 4)
    if ref == 'origin':
        continue
    behind, ahead = map(int, run('git', 'rev-list', '--left-right', '--count', 'origin/develop...' + ref).split())
    branches.append(dict(ref=ref, sha=sha, date=date, author=author, subject=subject, ahead=ahead, behind=behind,
                         changed_paths=run('git', 'diff', '--name-only', 'origin/develop', ref).splitlines(),
                         exclusive_commits=run('git', 'log', '--no-merges', '--format=%h|%an|%s', 'origin/develop..' + ref).splitlines()))
save('branches.json', branches)
files = run('git', '-c', 'core.quotepath=false', 'ls-files', '-z').rstrip('\x00').split('\x00')
inventory = collections.defaultdict(lambda: dict(files=0, bytes=0, readable_text=0, text_lines=0, extensions=collections.Counter()))
for name in files:
    path = ROOT / name
    bucket = inventory[name.split('/')[0] if '/' in name else '(root)']
    bucket['files'] += 1
    bucket['extensions'][path.suffix or '(none)'] += 1
    if path.is_file():
        data = path.read_bytes()
        bucket['bytes'] += len(data)
        if b'\x00' not in data:
            try:
                content = data.decode('utf-8')
                bucket['readable_text'] += 1
                bucket['text_lines'] += len(content.splitlines())
            except UnicodeDecodeError:
                pass
save('file_inventory.json', inventory)
rows = run('git', 'log', '--all', '--no-merges', '--since=2026-09-26T00:00:00+07:00', '--format=%H|%aI|%an|%s').splitlines()
authors = collections.defaultdict(list)
for row in rows:
    sha, date, author, subject = row.split('|', 3)
    authors[author].append(dict(sha=sha, date=date, subject=subject,
                               paths=run('git', 'diff-tree', '--no-commit-id', '--name-only', '-r', sha).splitlines()))
save('contributors.json', authors)
member_md = ['# Bằng chứng đóng góp Git — 26/09 đến 04/10/2026', '',
             'Phạm vi: commit không phải merge, reachable từ tất cả ref local/remote sau fetch. Đây là 29 tên tác giả Git, không phải 29 người đã xác minh danh tính. Một người có thể dùng nhiều alias; commit nhập snapshot cũng không chứng minh tác giả tự viết toàn bộ nội dung.', '',
             'Số commit chỉ dùng tra cứu, không xếp hạng năng suất hoặc phần trăm hoàn thành. Các branch cũ và backup có thể giữ commit không còn trên develop.', '',
             '| Tác giả Git | Commit | Commit gần nhất | Nội dung gần nhất |', '|---|---:|---|---|']
for author, commits in sorted(authors.items(), key=lambda x: -len(x[1])):
    c = commits[0]
    subject = c['subject'].replace('|', '/')
    summary = subject if len(subject) <= 180 else subject[:177] + '…'
    member_md.append(f'| {author} | {len(commits)} | `{c["sha"][:7]}` | {summary} |')
for author, commits in sorted(authors.items(), key=lambda x: -len(x[1])):
    member_md += ['', f'## {author}', '']
    for c in commits:
        member_md.append(f'- `{c["sha"][:7]}` ({c["date"]}): {c["subject"]}')
    directories = collections.Counter(p.split('/')[0] for c in commits for p in c['paths'])
    member_md += ['', 'Nhóm đường dẫn thay đổi: ' + ', '.join(f'`{name}` ({count} lượt file)' for name, count in directories.most_common()) + '.']
(OUT / 'CONTRIBUTORS.md').write_text('\n'.join(member_md) + '\n', encoding='utf-8')
inventory_md = ['# Kiểm kê checkout', '', f'{len(files)} file được Git theo dõi. Đọc thống kê byte/UTF-8 của file hiện tại; không tính node_modules, .git, worktree và thư mục local bị ignore. Số dòng là thống kê, không phải cam kết đã review thủ công từng dòng.', '',
                '| Folder | File | Text UTF-8 | Dòng text | Bytes |', '|---|---:|---:|---:|---:|']
for folder, item in sorted(inventory.items(), key=lambda x: -x[1]['files']):
    inventory_md.append(f'| `{folder}` | {item["files"]} | {item["readable_text"]} | {item["text_lines"]} | {item["bytes"]} |')
(OUT / 'INVENTORY.md').write_text('\n'.join(inventory_md) + '\n', encoding='utf-8')
prs = json.loads(run('gh', 'pr', 'list', '--state', 'all', '--limit', '100', '--json', 'number,title,state,isDraft,baseRefName,headRefName,mergedAt,updatedAt,url,author'))
save('pull_requests.json', prs)
runs = json.loads(run('gh', 'run', 'list', '--limit', '50', '--json', 'databaseId,workflowName,headBranch,headSha,status,conclusion,createdAt,url'))
save('github_runs.json', runs)
save('snapshot.json', dict(captured=captured, root=str(ROOT), head=run('git', 'rev-parse', 'HEAD'), branch=run('git', 'branch', '--show-current'),
                         develop=run('git', 'rev-parse', 'origin/develop'), main=run('git', 'rev-parse', 'origin/main'),
                         status=run('git', 'status', '--short', '--branch'), file_count=len(files), branch_count=len(branches),
                         authors=len(authors), recent_nonmerge_commits=len(rows), pr_count=len(prs),
                         worktrees=run('git', 'worktree', 'list')))
md = ['# Toàn bộ nhánh remote — 04/10/2026', '', f'Chụp lúc `{captured}`. So với `origin/develop` `{run("git", "rev-parse", "--short", "origin/develop")}`.',
      'Ahead/behind là số commit theo quan hệ tổ tiên, không phải số tính năng hay phần trăm tiến độ. 0 ahead nghĩa là lịch sử nhánh đã nằm trong develop; không bảo đảm mỗi hành vi vẫn giữ nguyên sau sửa đổi khác.', '',
      '| Nhánh | Tip | Ahead | Behind | Commit cuối (UTC+offset) | Tác giả commit cuối |', '|---|---|---:|---:|---|---|']
for b in branches:
    md.append(f'| `{b["ref"].removeprefix("origin/")}` | `{b["sha"][:7]}` | {b["ahead"]} | {b["behind"]} | {b["date"]} | {b["author"]} |')
md += ['', '## PR đang mở', '', '| PR | Nhánh nguồn → đích | Nội dung |', '|---|---|---|']
for p in prs:
    if p['state'] == 'OPEN':
        md.append(f'| [#{p["number"]}]({p["url"]}) | `{p["headRefName"]}` → `{p["baseRefName"]}` | {p["title"]} |')
md += ['', '## Dữ liệu đối chiếu', '', '`branches.json` có full SHA, danh sách đường dẫn khác develop và các commit riêng của từng nhánh. `pull_requests.json` là trạng thái API GitHub, không suy đoán từ tên merge commit.']
(OUT / 'BRANCHES.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print(json.dumps(dict(files=len(files), branches=len(branches), authors=len(authors), commits=len(rows),
                      open_prs=[p['number'] for p in prs if p['state'] == 'OPEN'],
                      latest_runs=[{k:r[k] for k in ['databaseId','headBranch','conclusion']} for r in runs[:8]]), ensure_ascii=False))
