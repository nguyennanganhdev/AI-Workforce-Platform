# Dọn Docker và gói release Platform — 17/10/2026

Đã hoàn tất lúc 23:17 giờ Việt Nam. Thu hồi khoảng **9,32 GB** trên VPS Platform; dung lượng sử dụng giảm **95% → 71%**. Đây là dung lượng ổ đĩa, không phải RAM. RAM sau kiểm tra còn khoảng 2,85 GB khả dụng trên tổng 4,13 GB.

| Chỉ số VPS | Trước | Sau |
|---|---:|---:|
| Ổ `/dev/vda1` đã dùng | 37,67 GB | 28,34 GB |
| Dung lượng khả dụng | 2,39 GB | 11,71 GB |
| Tỷ lệ sử dụng theo `df` | 95% | 71% |
| Payload trong thư mục release | 6,95 GB | 0,15 GB |

Đơn vị GB trong bảng là 1.000.000.000 byte. Linux còn dành riêng một phần dung lượng filesystem nên used + available không bằng toàn bộ kích thước partition.

## Đã xóa

- VPS: 60 image Platform cũ không được container nào tham chiếu, gồm 56 image có tag và 4 image không còn tag đã xác định được revision Platform.
- VPS: 70 payload release đã lỗi thời hoặc dư thừa, gồm archive image/source và thư mục build đã giải nén. Giữ metadata, ghi chú và snapshot cấu hình riêng tư.
- VPS: 29 record cache build đã xác định thuộc Platform, chỉ xóa khi đang `Reclaimable=true`, `Shared=false`. Dùng allowlist ID; không chạy `docker system prune` hoặc prune volume. Cơ chế lọc tham chiếu [Docker buildx prune](https://docs.docker.com/reference/cli/docker/buildx/prune/).
- Docker local: 42 image Platform cũ không dùng. Giữ image đang chạy, cặp image rollback `c0ad625c`, và fixture phục vụ test offline.
- Gói local: bỏ 5 payload/thư mục trung gian trùng nội dung trong gói hoàn chỉnh, giảm khoảng 674,5 MB file. Đã đối chiếu SHA-256 cho 30 file payload bên trong archive trước khi xóa bản sao.

## Đã giữ và kiểm chứng

- VPS còn nguyên 7 container và 4 volume; image, mount và trạng thái chạy không thay đổi trong quá trình dọn. Landing và các dịch vụ lưu trữ được giữ nguyên.
- Giữ bản đang chạy `d6693197-no-jev-20261017` và cặp image rollback `c0ad625c-builder-c4df-20261017`.
- Không xóa backup dữ liệu: khoảng 15,22 GB trong hai thư mục backup vẫn được giữ. Hai bộ backup đầy đủ gần nhất đã kiểm tra lại toàn bộ checksum đạt; bản trước rollback JEV đã khôi phục thử tách biệt đạt trước đó. Không tìm thấy thêm bản archive image có thể gộp bằng hard-link.
- Health local và HTTPS Platform đạt sau dọn. Không đổi source ứng dụng, schema dữ liệu, env hoặc credential trong đợt dọn dung lượng này.
- Không gọi API model/embedding thật. Không compact VHDX Docker Desktop; số image đã xóa không đồng nghĩa file VHDX trên Windows tự thu nhỏ ngay.

## Gói bàn giao còn lại

`E:/AWP-Releases/builder-no-jev-20261017/AWP-Builder-No-JEV-d6693197-complete.tar`

Kích thước 554.270.720 byte; SHA-256:

```text
90f6a4c9dab7e5e63d7f4e9edc628f7768bda6b6a1b8d8982167e7d19a1b8da5
```

Gói chứa source theo commit, hai image đúng ID đã triển khai trên VPS, manifest và bằng chứng kiểm tra. Không chứa env/credential riêng tư. Giải nén gói trước khi kiểm tra `PACKAGE-SHA256SUMS` hoặc nạp `images.tar.gz`; các bản sao đứng riêng đã được dọn.

Bằng chứng và allowlist thao tác nằm tại `E:/AWP-Releases/builder-no-jev-20261017/disk-cleanup/`, đặc biệt `disk-cleanup-final.json`, `cache-cleanup.json`, `local-image-cleanup.json`, `package-deep-check.json` và `local-package-compaction.json`. VPS giữ các bằng chứng tương ứng trong release hiện tại.

Để tránh tích lũy lại, các lần triển khai sau cần kết thúc bằng việc đối chiếu gói bàn giao, xóa context/archive trung gian đã thừa và duy trì danh sách image đang chạy/rollback được bảo vệ. Chính sách lưu giữ backup dữ liệu chưa được thay đổi trong đợt này.
