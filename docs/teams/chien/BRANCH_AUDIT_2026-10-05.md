# Rà soát nhánh — 05/10/2026

Snapshot sau `git fetch origin --prune`. So sánh với remote `origin/develop`, không dùng local `develop` đang cũ. Số commit riêng không phải phần trăm hoàn thành.

| Nhánh | HEAD | Ngày commit | Riêng so với develop | Thiếu develop | Commit cuối |
|---|---|---|---:|---:|---|
| origin/dev_TeamChien | `904f1ca` | 2026-10-05 | 62 | 0 | docs: what the OpenBot features for management became, how they are deployed and what was checked |
| origin/dev_teamChien_HuyDo | `904f1ca` | 2026-10-05 | 62 | 0 | docs: what the OpenBot features for management became, how they are deployed and what was checked |
| origin/dev_TeamDong | `810e0bf` | 2026-10-04 | 2 | 0 | Merge remote-tracking branch 'origin/develop' into dev_TeamDong |
| origin/devTeamDong/dev5 | `0a698bb` | 2026-10-04 | 4 | 118 | feat(DEV-5): Implemented Schema V2 contracts & updated main endpoint |
| origin/develop | `b391952` | 2026-10-04 | 0 | 0 | Merge pull request #34 from dev_TeamHoang-HuyHoang |
| origin/dev_TeamHoang-HuyHoang | `48ea913` | 2026-10-04 | 0 | 181 | feat(reporting): add scoped report tools on Team Hoang base |
| origin/codex/report-agent-PHH | `518178a` | 2026-10-04 | 2 | 39 | feat(reporting): replace legacy tools with scoped bill ticket and star summaries |
| origin/devTeamPhai | `2c86dfe` | 2026-10-04 | 0 | 164 | Merge pull request #33 from nguyennanganhdev/devTeamPhai-DucAnh |
| origin/devTeamPhai-DucAnh | `3255640` | 2026-10-04 | 0 | 171 | Thêm tài liệu để đấu nối với backend |
| origin/integration/devTeamPhai-on-develop | `46e0093` | 2026-10-04 | 1 | 5 | Merge devTeamPhai into develop: Agent Factory and Security MCP tools |
| origin/devTeamPhai-PhaiHoang | `c0caa8b` | 2026-10-03 | 1 | 186 | test tạm chuyển sang deepseek |
| origin/devTeamDong/TienAnh-supervisor | `fb9d665` | 2026-10-03 | 0 | 115 | refactor: refactor agent coordination codebase: remove unused runner, enhance groupchat models, and improve runtime service |
| origin/devTeamPhai-HuyAnh | `acf62d1` | 2026-10-02 | 0 | 173 | Security MCP (P4): callback worker cho dispatch/escalation, ACK ủy quyền theo roster - mock-write: thêm WorkerCommands (interface Core nội bộ, spec §9) gồm   recordDispatchStatus, luồng gửi tin → NOTIFIED → ACK và expireEscalation.   Mỗi callback ghi event + evidence; trùng event_id thì trả replayed,   không ghi thêm hay tăng version. - delivery_failed của dispatch_guard/escalate_emergency ghi event + evidence   như một callback thật, guard được nhả. - emergency: ACK chấp nhận người được ủy quyền trong roster (§6.2);   ủy quyền cho contact khác, grant ký cho actor khác hoặc roster đã hết   ủy quyền → ACK_NOT_AUTHORIZED. Deadline vẫn thắng: từ ack_deadline_at   trở đi là ACK_TIMEOUT. - dispatch/emergency types: khai báo ToolIO cho provider bằng declaration   merging. - mock-provider: thêm liveScope() để lệnh worker tác động lên dữ liệu sống;   scope nhận thêm delegations. - Test: security-mcp-callbacks.test.ts (19 case) và fixture delegations.json. - Format Biome cho dispatch/ và emergency/. |
| origin/devTeamPhai-LeHoang | `63c90c2` | 2026-10-02 | 0 | 177 | test(security-tools): bỏ cổng chờ P3, test incident/audit chạy bắt buộc |
| origin/devTeamPhai-P3-Incident | `da67323` | 2026-10-02 | 0 | 182 | feat(security-tools): P3 Incident, Evidence, Timeline |
| origin/devTeamDong/dev3 | `9077390` | 2026-10-02 | 1 | 119 | Implement HMAC source proof authentication and reception ingress |
| origin/dev_TeamChien-beHuy | `6b8e166` | 2026-10-02 | 0 | 172 | feat(api): add Technical A2 endpoints with PostgreSQL persistence |
| origin/devTeamPhai-HoangViet | `8e79917` | 2026-10-02 | 0 | 182 | fix(security-tools): add Incident and IncidentType definitions to unblock typecheck |
| origin/dev_TeamQuang_ddhung04 | `20b7b46` | 2026-10-01 | 1 | 191 | docs(quang): add technical issue data for RAG POC |
| origin/frontend/ft-resident | `e1b1c4d` | 2026-10-01 | 0 | 146 | author accept admintrator |
| origin/dev_TeamQuang | `6094b53` | 2026-10-01 | 0 | 157 | Merge pull request #20 from nguyennanganhdev/phuc_rag |
| origin/phuc_rag | `d68b9c7` | 2026-10-01 | 0 | 190 | bỏ sung thêm hàm json tạo file |
| origin/dev_TeamHoang | `975565a` | 2026-10-01 | 0 | 182 | docs(hoang): hand off PH16 follow-ups to PD11 and PH17 |
| origin/dev_TeamHoang_PhanDung | `975565a` | 2026-10-01 | 0 | 182 | docs(hoang): hand off PH16 follow-ups to PD11 and PH17 |
| origin/technical_tool_Dat_merge | `155de53` | 2026-10-01 | 0 | 164 | docs(quang): record the merge of the two tool frameworks and one list of backend ports |
| origin/pre-develop-20260903/ngo-dinh-khanh | `e775113` | 2026-10-01 | 0 | 157 | fix(operations): restore own staff-screen edits lost with the merge revert |
| origin/devTeamDong/tiendo-ml-engineer | `84771cd` | 2026-09-30 | 10 | 182 | fix(ci): exclude docs and design jsons from biome format, fix adk test mock body |
| origin/dev_TeamDong_checkpointing | `56ca8f3` | 2026-09-30 | 6 | 182 | fix(ci): fix helm chart baseline fallback in check-new-values-keys.ts |
| origin/frontendNgoDinhKhanh | `c400a45` | 2026-09-30 | 0 | 162 | feat(operations): neutral shadcn redesign for staff screens, incidents and dashboard |
| origin/dev_TeamHoang_PHHoang | `5ac0382` | 2026-09-30 | 0 | 191 | PH01 |
| origin/devTeamDong/TienAnh-agent-room | `223ccc0` | 2026-09-30 | 0 | 185 | tests(agent-room): Add comprehensive tests for group chat functionality |
| origin/frondendVuVietAnh | `f760830` | 2026-09-30 | 0 | 179 | Merge develop into frondendVuVietAnh for database V3 synchronization |
| origin/backup/pre-develop-20260930/ngo-dinh-khanh | `c420607` | 2026-09-29 | 0 | 185 | feat(vinhomes-operations): simplify role-based operations interfaces |
| origin/backup/pre-develop-20260930/resident | `f1b97b9` | 2026-09-29 | 0 | 180 | add auth page |
| origin/source | `926eae3` | 2026-09-29 | 1 | 199 | feat(db): consolidate P0 database schema and documentation |
| origin/backup/pre-develop-20260930/vu-viet-anh | `1b480ad` | 2026-09-29 | 0 | 187 | feat(operations): integrate A5 workflow and task history |
| origin | `a655710` | 2026-09-26 | 0 | 204 | feat: initialize server structure with Hono framework and domain routes |
| origin/main | `a655710` | 2026-09-26 | 0 | 204 | feat: initialize server structure with Hono framework and domain routes |

Nhánh hiện tại lúc bắt đầu: `dev_teamChien_HuyDo` ở `04a5131`, trùng `origin/dev_TeamChien`, chứa đủ `origin/develop` (`b391952`), 57 commit riêng. Local `develop` ở `6fa4aa0` cũ hơn remote; không reset checkout đang dùng.

Trong phiên này, phiên MCP của người dùng đã bổ sung `77e3d6d` (lọc credential/audit retention), `b36dd76` (lịch agent), `4faa41a` (tri thức), `69cf151` (file trong phòng), `904f1ca` (tài liệu). Các commit đó được giữ nguyên; thay đổi hoàn thiện được đặt trong commit riêng.

PR #31: base `develop`, head `dev_TeamChien`. Người dùng cho phép bật CI và merge khi checks đạt.

Sau snapshot: `fa2674d` hoàn thiện Docker/tài khoản/đơn vị/preset/upload; `a34f68f` sửa pin Rust action cho CI.
PR #31 đã gộp vào `develop` tại `d5d5b2e` sau khi checks đạt. Bảng trên là snapshot trước các commit hoàn thiện,
không dùng số thiếu develop trong bảng để mô tả trạng thái sau merge.
