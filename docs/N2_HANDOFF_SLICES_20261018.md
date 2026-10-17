# Người 2 — handoff các slice từ baseline PR #99

Phạm vi theo hai kế hoạch đã chốt ngày 18/10 và chỉ dẫn mới nhất của chủ dự án.
Không dashboard BQL, exception queue, operator grant/approval bridge hoặc bot Discord chung.
Khách hàng dùng cùng UI/các trang Platform, dữ liệu riêng; Provider/MCP/Skill được cấp chỉ xem/chọn/dùng.
Không chạy test bằng model key thật; không bật production/cutover bằng kết quả fixture.

## S00 — Rebase

- WIP đã commit trước đó: `e6cb3495`, `88098c39`, `f64a07fc`; không còn file chưa commit trước rebase.
- Backup local: `backup/vin-user2-pre-rebase-20261018`.
- Rebase lên đúng `fe56707a966864ec7915be30421762d30cba4d15`, giữ eval sandbox/lịch/Discord của PR #99.
- Commit sau rebase: `45f02c27` (model resolver), `4b44dd3f` (shared KB), `3365b8c7` (UI consumer cũ).
- Một conflict tại `frontend/tests/client.test.mjs`: giữ bản upstream vì đã có origin mock và regression login.
- Kiểm tra: worktree sạch sau rebase; xem diff 50 file PR #99 và hướng dẫn eval/schedule/channel;
  test chức năng sẽ chạy lại theo từng slice tiếp theo, không tái dùng số test trước rebase làm proof.
- Chờ Người 1: commit C01/C02/C03 hoàn thiện để tích hợp. Hiện producer đang ở WIP `48e922bd`, cũng đã rebase.

## Yêu cầu cho owner Người 1 (không sửa file lane Người 1)

1. C01: capability view/bind/execute/manage cho catalog, agent, lịch và kênh; giữ BQL/admin cũ. Không dùng
   UI role làm authority. Chốt active workspace server; không cần một bộ chọn workspace mới để dùng AI cá nhân.
2. C02: resolver MCP/skill dùng chung callable có permission và owner/version. Public list/detail/schema
   chỉ trả allowlist, không secret. Credential alias phải có trong model picker mà không persist key user.
3. C05/C07: private customer session/Leader/case binding, self context và event/replay/consent receipt.
   `origin=platform` không phát `start_workflow` vào partner route hoặc Leader BQL; cần regression Domain.
4. C09: atomic logical-run claim, lease/fence, once-consumed trước dispatch, run outcome + delivery outbox
   độc lập; verified Discord user identity mặc định owner, bot credential reference và per-user sessions.
   Cấu hình allowlist trống phải deny; không suy owner từ người gửi đầu tiên.
5. N2-04 cần durable batch publish manifest/stable IDs/status/repair cursor + storage/CAS API. Boolean
   `claim_builder_publish` hiện tại không đủ phục hồi crash/partial activation; không dùng dict thay authority.

N2_CONTRACT_HANDOFF và N2_KET_QUA cũ là ảnh chụp trước rebase. Handoff này và các slice tiếp theo cập nhật
phạm vi mới; các đề xuất operator/BQL dashboard trong báo cáo cũ không còn thuộc phạm vi.
