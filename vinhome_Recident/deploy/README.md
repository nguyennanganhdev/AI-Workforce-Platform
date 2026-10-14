# Đóng gói domain Vinhomes

Một lệnh dựng cả hệ thống trên một máy có Docker: dữ liệu nằm trong PostgreSQL, ảnh và tệp nằm trong MinIO (chuẩn S3). Người dùng chỉ biết **một địa chỉ**, của `gateway`.

## Chạy

Từ thư mục `vinhome_Recident`:

```powershell
deploy\new-env.ps1          # Linux/macOS: sh deploy/new-env.sh
# mở deploy/deployment.env, dán OPENAI_API_KEY
docker compose --env-file deploy/deployment.env -f deploy/compose.yml up -d --build
```

- Lệnh thứ nhất tạo `deploy/deployment.env` với các bí mật ngẫu nhiên (mật khẩu database, khóa MinIO, khóa ký, mật khẩu của các tài khoản mẫu). Tệp này không được commit. Chạy lại thì lệnh **từ chối ghi đè**: bí mật trong tệp là bí mật mà database và kho ảnh đã được tạo cùng.
- Điền `OPENAI_API_KEY`, tạo admin riêng và cung cấp dữ liệu vận hành đã xác nhận. Mặc định production không tạo tài khoản/căn hộ/giao dịch mẫu (`VINHOMES_SAMPLE_WORLD=0`), không tự nạp lại tri thức (`VINHOMES_LOAD_KNOWLEDGE=0`).
- Mở `http://localhost:8080`. Lần đầu cần tải image và build hai app web nên mất vài phút; bước chuẩn bị dữ liệu mất khoảng nửa phút.
- Đổi cổng: sửa `GATEWAY_PORT` **và** `VINHOMES_ALLOWED_ORIGINS` cùng lúc (đăng nhập kiểm tra địa chỉ trình duyệt đang dùng). Nếu máy đã có chương trình khác dùng cổng 8000, sửa `VINHOMES_API_PORT`; cổng này chỉ để gọi thẳng API khi cần, người dùng không đi qua nó.

## Những gì được khởi động

| Dịch vụ | Việc | Mở ra máy chủ |
|---|---|---|
| `postgres` | Toàn bộ dữ liệu nghiệp vụ và kho tri thức (image `pgvector/pgvector:pg17`: PostgreSQL có sẵn pgvector, dùng để tìm tri thức theo nghĩa). Volume `postgres-data`. | không |
| `minio` | Ảnh và tệp, trong một bucket riêng tư. Volume `minio-data`. | không |
| `init` | Nâng schema, bootstrap tổ chức và ba hồ sơ dự án tham chiếu, cấp quyền API, chuẩn bị storage. Chỉ tạo fixture khi bật sample mode; chỉ nạp tri thức khi yêu cầu rõ ràng. Không tự tạo admin/người dùng production. | không |
| `api` | Backend nghiệp vụ; chờ `init` xong. | `127.0.0.1:8000` |
| `scheduler` | Mỗi phút: cảnh báo và báo quá hạn xử lý, cho đặt chỗ chưa thanh toán và lượt khách không tới hết hạn. | không |
| `platform-sync` | Cầu nối với platform AI: gửi lệnh và sự kiện tiến độ, ghi lời của agent điều phối vào chat. Chưa khai báo platform thì chỉ chờ. | không |
| `reception` | Agent lễ tân; gọi `api`, tìm tri thức qua `api`. | không |
| `resident` | Landing page `/`, ứng dụng cư dân `/resident` và trang đăng nhập chung `/login`. | không |
| `operations` | Quản trị Domain và nhân viên hiện trường. BQL sử dụng Platform. | không |
| `gateway` | Địa chỉ duy nhất: `/` là landing page, `/resident` là app cư dân, `/login` là đăng nhập, `/operations` là app nhân viên, `/api/business` là API. | `127.0.0.1:8080` |

Gateway cũng chuyển `/mcp` tới API cho platform. Chỉ cấu hình `VINHOMES_API_PLATFORM_MCP_TOKEN` là đủ để onboarding/discovery; không cần bật cầu nối `VINHOMES_API_PLATFORM_URL`. Mọi yêu cầu MCP phải có `Authorization: Bearer <token>`; key không nằm trong frontend. `/api/business/mcp` và `/mcp/` không phải endpoint MCP. Khi gateway mở công khai, dùng HTTPS hoặc kết nối riêng/tunnel để token không đi qua HTTP Internet.

Database và kho ảnh không mở cổng ra ngoài. Ảnh do trình duyệt gửi đi qua API (qua `gateway`, tối đa 25 MB), API lưu vào MinIO và cũng là nơi duy nhất trả ảnh ra, sau khi kiểm tra người hỏi.

API chạy bằng vai trò database `vinhomes_api`: không phải chủ database, không vượt được phân quyền theo dòng. Chỉ `init` dùng vai trò chủ.

## Đăng nhập thế giới mẫu (chỉ môi trường phát triển)

Phần này chỉ áp dụng khi chủ động bật `VINHOMES_SAMPLE_WORLD=1` trên database thử riêng. Tài khoản BQL mẫu không còn được cấp quyền đăng nhập Domain; BQL dùng Platform. Không dùng bộ tài khoản này để nghiệm thu dữ liệu vận hành thật.

Mật khẩu của mọi tài khoản dưới đây là giá trị `DEMO_PASSWORD` trong `deploy/deployment.env`. Tên đăng nhập là email:

| Tên đăng nhập | Người | Vào đâu |
|---|---|---|
| `local-v3-admin@example.invalid` | Quản trị viên | Quản lý tài khoản |
| `mock-hoa@example.invalid` | Kỹ thuật viên Hoa, ca 06:00 đến 14:00 | Việc của tôi |
| `mock-s09@…`, `mock-s18@…` | hai kỹ thuật viên nữa của ca 06:00 đến 14:00 | Việc của tôi |
| `mock-s02@…`, `mock-s11@…`, `mock-s20@…` | kỹ thuật viên ca 14:00 đến 22:00 | Việc của tôi |
| `mock-s03@…`, `mock-s12@…`, `mock-s21@…` | kỹ thuật viên ca 22:00 đến 06:00 | Việc của tôi |
| `mock-giang@example.invalid` | Bảo vệ Giang | Việc của tôi |
| `mock-an@example.invalid` | Anh An, chủ căn S1.01-1201 | App cư dân |
| `mock-binh@example.invalid` | Chị Bình, thuê căn S1.02-0803 | App cư dân |
| `mock-dung@example.invalid` | Anh Dũng, có hai nhà (căn hộ và villa) | App cư dân |

- Việc sửa chữa mới chỉ được mời tới kỹ thuật viên đang trong ca, còn chỗ và không dở tay việc khác. Trong thế giới mẫu đó là chín người ở bảng trên, mỗi ca ba người (đuôi email đều là `@example.invalid`); sáu kỹ thuật viên còn lại đã kín việc nên không có tài khoản.
- Trang chủ `/` mở công khai, không gọi API dữ liệu cư dân. Mọi người đăng nhập ở `/login`; cư dân được chuyển đến `/resident`. Liên kết cũ `/#/...` vẫn mở đúng app cư dân. Tài khoản vừa là cư dân vừa là nhân viên được hỏi chọn nơi vào.
- API cũng nhận số điện thoại gõ kiểu Việt Nam (`0901000001`, `0901 000 001`, `+84901000001`), nhưng **trang đăng nhập hiện chỉ cho gõ email**, nên khi demo hãy dùng email ở bảng trên.
- Thế giới mẫu được dựng **một lần**, ngày tháng tính theo ngày dựng. Các lần khởi động sau giữ nguyên nó cùng mọi việc mọi người đã làm; muốn có thế giới mới thì đặt lại (xem dưới).
- `DEMO_PASSWORD` chỉ được dùng **một lần cho mỗi tài khoản**. Sửa nó sau khi đã chạy không đổi mật khẩu đã có; muốn đổi thì đăng nhập rồi đổi mật khẩu, hoặc đặt lại thế giới mẫu.
- Thêm tài khoản mẫu khác (ví dụ `mock-chau`):

```powershell
docker compose --env-file deploy/deployment.env -f deploy/compose.yml run --rm init python -m vinhomes_api.database accounts --users mock-chau --password-env DEMO_PASSWORD
```

## Việc thường làm

Các lệnh dưới viết gọn `dc` thay cho `docker compose --env-file deploy/deployment.env -f deploy/compose.yml`.

**Xem trạng thái và nhật ký**

```powershell
dc ps
dc logs init        # bước chuẩn bị đã làm gì, lỗi ở đâu
dc logs -f api
```

**Vào database**

```powershell
dc exec postgres psql -U vinhomes_owner vinhomes
```

**Đặt lại thế giới mẫu trên môi trường phát triển riêng** (xóa dữ liệu và ảnh của stack đó; không chạy trên VPS đang vận hành):

```powershell
dc down -v
dc up -d
```

Nếu một migration cũ bị đổi checksum, dừng và đối chiếu bản đã chạy; không sửa checksum hoặc xóa volume để vượt qua kiểm tra. Với dữ liệu cần giữ, backup và chuẩn bị database riêng theo [hướng dẫn làm sạch](../docs/domain/OWNER_DATA_REQUIREMENTS_20261014.md#làm-sạch-và-quay-lại), kiểm chứng trước khi chuyển URL.

**Sao lưu và khôi phục.** Dịch vụ `backup` tự chạy mỗi ngày lúc `BACKUP_HOUR` giờ (mặc định 2 giờ sáng, giờ Việt Nam): một bản dump database (giữ `BACKUP_KEEP` bản mới nhất, mặc định 7) và một bản sao mọi tệp của kho ảnh. Nơi lưu là volume `backup-data`, hoặc thư mục trên máy chủ nếu đặt `BACKUP_DIR`. Lần sao lưu gần nhất hỏng thì `dc ps` báo `backup` là `unhealthy` và `dc logs backup` nói vì sao.

```powershell
dc run --rm backup now        # sao lưu ngay
dc logs backup                # các lần đã chạy, dung lượng
```

Khôi phục vào một hệ thống vừa `dc down -v` (database và kho ảnh đang trống):

```powershell
dc up -d --wait postgres minio
dc run --rm backup restore    # bản dump mới nhất; thêm tên tệp để chọn bản khác
dc up -d
```

`init` cấp lại quyền cho vai trò của API khi khởi động. Giữ kèm `deploy/deployment.env`: thiếu nó thì bản sao lưu không dùng lại được với đúng mật khẩu và khóa. Bản sao lưu nằm cùng máy với dữ liệu; muốn an toàn khi hỏng máy thì đặt `BACKUP_DIR` vào một ổ khác hoặc chép thư mục đó đi nơi khác.

Đã thử thật (12/10): sao lưu, xóa sạch volume, khôi phục; số yêu cầu, người dùng, tài khoản, tin nhắn, vector tri thức giống hệt, đăng nhập bằng mật khẩu cũ được, ảnh đọc lại được qua API.

**Chạy nhiều bản API hoặc Reception.** Đặt `VINHOMES_API_PORT=` (để trống) trong `deployment.env`, rồi:

```powershell
dc up -d --scale api=2 --scale reception=2
```

Giới hạn đăng nhập và thứ tự lượt trả lời của từng hộp chat được giữ trong PostgreSQL, nên các bản dùng chung một mức và một hộp chat không bao giờ có hai lượt chạy cùng lúc. Chỉ chạy một bản `platform-sync`, `scheduler`, `backup`. Khi để trống cổng, mỗi bản API nhận một cổng ngẫu nhiên trên máy; platform chạy cùng máy cần một cổng cố định thì giữ một bản API. Đã thử thật với hai bản mỗi loại: đăng nhập một lần dùng được ở cả hai bản, tắt một bản thì cổng chung vẫn trả lời. Chưa thử Reception hai bản với model thật.

**Đăng ký platform** (một lần; lệnh in bí mật một lần, chạy lại là xoay bí mật):

```powershell
dc run --rm init python -m vinhomes_api.database client --id platform --kind platform --accepts-cases
```

## Nối với platform AI (Workforce v1)

Mặc định tắt: `VINHOMES_API_PLATFORM_URL` trống thì hệ thống chạy như không có platform. Để bật, làm theo [platform/README.md](platform/README.md): người vận hành platform chạy `deploy/platform/apply.py` với bộ khai báo `deploy/platform/vinhomes-declaration.json`, Vinhomes dán các khóa nhận được vào `deployment.env`, khởi động lại `api` và `platform-sync`, rồi xác nhận route. Cách nối này không dùng lệnh "Đăng ký platform" ở trên.

## Chạy với dữ liệu thật

1. Giữ `VINHOMES_SAMPLE_WORLD=0`, `VINHOMES_LOAD_KNOWLEDGE=0` trước lần chạy đầu tiên. Nếu đã có dữ liệu mẫu, backup và chuẩn bị database sạch riêng; không dùng `dc down -v` trên production.
2. `dc up -d --build`.
3. Tạo quản trị viên đầu tiên. Mật khẩu (12 đến 128 ký tự) đưa qua biến môi trường để không nằm trong lịch sử lệnh:

```powershell
$env:ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'Mật khẩu admin mới' -AsSecureString)).Password
dc run --rm -e ADMIN_PASSWORD init python -m vinhomes_api.database accounts --create-admin ten@congty.vn --password-env ADMIN_PASSWORD
Remove-Item Env:\ADMIN_PASSWORD
```

4. Chuẩn bị bộ dữ liệu theo [yêu cầu bàn giao OP1/2/3](../docs/domain/OWNER_DATA_REQUIREMENTS_20261014.md). Importer trong [NAP_DU_LIEU](../docs/domain/NAP_DU_LIEU.md) là bản legacy một site; sẽ từ chối tenant có ba site. Cần hoàn thiện staging/import theo `site_code` trước khi nạp master/roster thật. Không dùng seed làm dữ liệu thay thế.

5. Cho người đã nạp mật khẩu đầu tiên (theo mã người dùng hoặc email, cách nhau dấu phẩy). Người đã có mật khẩu được giữ nguyên; một tên không tồn tại thì lệnh dừng và không đổi gì:

```powershell
dc run --rm -e FIRST_PASSWORD init python -m vinhomes_api.database accounts --users a@congty.vn,b@congty.vn --password-env FIRST_PASSWORD
```

Bootstrap production đã tách khỏi seed: không sinh cư dân, nhân sự, căn hộ, giao dịch hoặc SLA giả. Các hồ sơ dự án công khai là tham chiếu, không chứng nhận đơn vị/phạm vi vận hành. `management_units` là cấu hình tổ chức/route, không phải role đăng nhập BQL.

Gói [tiện ích tham khảo OP1/2/3](reference-data/ocean-city-public-20261014.json) có URL nguồn chính thức, không có phí/giờ/quyền booking tự tạo. `prepare-reference-pack.py` chuyển JSON sang gzip JSONL cho `vinhomes_api.knowledge load --file ...`; nạp thủ công với scope đúng site, giữ trạng thái `reference`. Không bật auto-load để ghi đè review của chủ dữ liệu.

**Database hoặc kho S3 có sẵn ở nơi khác.** Bỏ dấu `#` ở cuối `deployment.env`: `MIGRATION_DATABASE_URL` (chủ database, dạng `postgresql://`), `VINHOMES_API_DATABASE_URL` (vai trò `vinhomes_api` với `API_DB_PASSWORD`, dạng `postgresql+asyncpg://`), `S3_ENDPOINT`. Với S3 riêng, khóa `S3_ACCESS_KEY`/`S3_SECRET_KEY` phải có sẵn ở đó và đặt `MINIO_ROOT_USER=` (trống). PostgreSQL ở nơi khác phải có pgvector: người quản trị ở đó chạy `create extension vector` trong database **trước** lần khởi động đầu tiên (chỉ superuser tạo được extension này; dịch vụ PostgreSQL thuê ngoài gọi nó là `vector`), nếu không `init` dừng ở `0013_knowledge.sql`. Hai container `postgres` và `minio` vẫn khởi động nhưng không được dùng. Cách này mới được kiểm tra ở mức cấu hình, chưa chạy thật.

## Đưa lên server

Domain dùng Nginx gateway hiện có; Caddy đã bỏ khỏi Compose. Xem [HTTPS.md](HTTPS.md) để cấp chứng chỉ, render TLS và cấu hình gia hạn. Chỉ bật Secure cookie sau khi HTTPS public hoạt động. Với một gateway trực tiếp tới API, giữ `TRUSTED_PROXY_HOPS=1`.

Không chạy new-env hoặc seed/reset lên server đã có dữ liệu. Backup trước khi áp migration mới; chạy migration và cấp role bằng image API mới, sau đó recreate riêng dịch vụ thay đổi. Không dùng `down -v`.

MCP cung cấp 7 tool xử lý ticket đã bàn giao. `/mcp` thiếu/sai Bearer trả 401; catalog có key hoạt động độc lập với outbound bridge. Cấu hình platform kết nối sau theo [platform/README.md](platform/README.md).

### Khôi phục mật khẩu

Điền `VINHOMES_PUBLIC_URL` là HTTPS origin và các biến `VINHOMES_SMTP_*` trong env riêng; `VINHOMES_SMTP_SECURITY` chỉ nhận starttls hoặc ssl. Chưa có SMTP thì API báo chưa cấu hình, không giả báo đã gửi email. Link khôi phục có hiệu lực 15 phút, dùng một lần; token nằm trong URL fragment để tránh access log và chỉ lưu hash trong database.

Đợt maintain kiểm thử bằng hộp thư giả, không gửi email thật. Cấu hình SMTP sau rồi recreate API; không cần thay provider Reception. Không in credential hoặc link reset ra log/báo cáo.

## Phát hành qua registry

Mặc định server tự build từ mã nguồn. Để build một nơi rồi kéo image về, đặt tiền tố có địa chỉ registry và một nhãn phiên bản (trong `deployment.env` hoặc biến môi trường):

```
VINHOMES_IMAGE_PREFIX=ghcr.io/<tổ chức>/vinhomes
VINHOMES_IMAGE_TAG=2026-10-12
```

Trên máy build (đã `docker login` vào registry): `dc build` rồi `dc push api reception resident operations backup`.

Chỉ phát hành landing page/app cư dân: đặt `VINHOMES_RESIDENT_IMAGE_TAG=<nhãn frontend mới>`, giữ `VINHOMES_IMAGE_TAG` cho các dịch vụ còn lại. Build/push riêng `resident`, rồi trên server `dc pull resident` và `dc up -d --no-deps --no-build resident`. Bỏ giá trị riêng này để `resident` dùng lại nhãn chung; khi rollback frontend cần đổi chính `VINHOMES_RESIDENT_IMAGE_TAG`.

Trên server chỉ cần các tệp `deploy/compose.yml`, các overlay TLS nếu dùng, `deploy/nginx/*.template` và `deploy/deployment.env` (cùng hai giá trị trên), không cần mã nguồn: `dc pull api reception resident operations backup` rồi `dc up -d --no-build`.

Quay về bản trước: đổi `VINHOMES_IMAGE_TAG` về nhãn cũ rồi `dc up -d --no-build`. Migration database không tự lùi: bản cũ vẫn chạy trên database đã thêm bảng, nhưng muốn về đúng dữ liệu cũ thì phải khôi phục từ bản sao lưu.

Đã thử thật (12/10) với một registry chạy tạm trên máy: đẩy năm image, xóa bản trên máy, kéo về và khởi động trong một thư mục chỉ có các tệp nêu trên.

## Đồng bộ dữ liệu theo lịch

Dịch vụ `data-sync` (chỉ chạy khi bật `--profile sync`) cứ `DATA_SYNC_SECONDS` giây (mặc định 300) xem thư mục `DATA_SYNC_DIR` và nạp các tệp xuất trong đó bằng đúng lệnh `import`. Cách dùng, quy ước tệp `READY` và điều gì xảy ra với người không còn trong tệp: xem `docs/domain/NAP_DU_LIEU.md`, mục "Đồng bộ theo lịch".

```powershell
dc --profile sync up -d data-sync
dc logs data-sync
```

Dịch vụ này không gọi hệ thống nào ở ngoài. Nối thẳng vào hệ thống quản lý cư dân thật cần thêm một bước lấy dữ liệu về thành các tệp này; bước đó chưa có.

## Chưa có trong gói

- **Thanh toán thật.** Chưa nối với cổng thanh toán nào.
- **Đăng nhập bằng số điện thoại trên trang đăng nhập** (API đã nhận, giao diện chưa).
- **Gửi ảnh thẳng từ trình duyệt tới kho ảnh.** Cần một địa chỉ `https` công khai cho kho (`S3_PUBLIC_ENDPOINT`); mặc định ảnh đi qua API.

## Một địa chỉ, một lần đăng nhập

Sau khi đăng nhập, `GET /auth/session` cho biết người đó dùng không gian nào (`audiences`) và vai trò vận hành (`operationsRole`): cư dân vào `/resident`, quản lý vào `/operations/kanban`, nhân viên hiện trường vào `/operations/my-tasks`, quản trị viên vào `/operations/accounts`. `/` là landing công khai. Cả ba nơi dùng chung một cookie `vinhomes_session`.

- `gateway` không gửi `X-Vinhomes-Surface` tới API (và bỏ giá trị trình duyệt tự gửi), nên API dùng một cookie duy nhất.
- Quyền vẫn do vai trò trong API quyết định, không do địa chỉ truy cập; app nhân viên chỉ hiện trang hợp với vai trò.
- Tài nguyên của app nhân viên nằm ở `/staff-assets/` để không đè `/assets/` của app cư dân.

## Build riêng từng image

```powershell
docker build -f deploy/Dockerfile.web --build-arg APP=resident-web -t vinhomes-domain-resident .
docker build -f deploy/Dockerfile.web --build-arg APP=staff-web    -t vinhomes-domain-operations .
docker build -t vinhomes-domain-api       services/vinhomes-api
docker build -t vinhomes-domain-reception agents/reception
```

Lệnh `docker build` của hai app web chạy từ thư mục gốc `vinhome_Recident` (context cần thấy `package-lock.json` và `packages/`). Image web cài dependency bằng `npm ci` theo workspace nên chỉ tải gói của app đang build; cần mạng để tải `node:24-alpine` lần đầu.

### VPS không tải được base image

Đợt maintain dùng image API đang triển khai làm nền vì Docker Hub timeout. `deploy/Dockerfile.api-update` chỉ dùng khi base là API Python 3.12 đáng tin cậy và dependency trong `pyproject.toml` không thay đổi; recipe chép module/schema mới và chạy `pip check`. Nếu đổi dependency hoặc Python, phải build bằng Dockerfile chuẩn.

Web có thể build trên máy phát triển bằng `npm ci`, `npm run typecheck`, `npm run build`, rồi đóng gói dist qua `deploy/Dockerfile.web-artifact`, truyền `BASE_WEB_IMAGE` là image Nginx đang có và `APP=resident-web` hoặc `staff-web`. File ignore riêng của recipe chỉ gửi dist và template Nginx vào build context. Giữ `VITE_ALLOW_DEMO_BACKEND=false`, `VITE_ENABLE_UI_PREVIEW=false` khi build.

Không dùng tag `latest` để xác nhận phiên bản. Ghi SHA source/commit, image ID và kiểm tra HTML/assets thực tế sau recreate. `VINHOMES_API_IMAGE_TAG` áp dụng đồng thời cho API/init/scheduler/platform-sync; `VINHOMES_OPERATIONS_IMAGE_TAG` và `VINHOMES_RESIDENT_IMAGE_TAG` cho hai frontend.
