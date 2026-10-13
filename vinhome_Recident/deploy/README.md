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
- Việc duy nhất phải tự làm là dán `OPENAI_API_KEY`. Thiếu thì compose dừng ngay và nêu tên biến.
- Mở `http://localhost:8080`. Lần đầu cần tải image và build hai app web nên mất vài phút; bước chuẩn bị dữ liệu mất khoảng nửa phút.
- Đổi cổng: sửa `GATEWAY_PORT` **và** `VINHOMES_ALLOWED_ORIGINS` cùng lúc (đăng nhập kiểm tra địa chỉ trình duyệt đang dùng). Nếu máy đã có chương trình khác dùng cổng 8000, sửa `VINHOMES_API_PORT`; cổng này chỉ để gọi thẳng API khi cần, người dùng không đi qua nó.

## Những gì được khởi động

| Dịch vụ | Việc | Mở ra máy chủ |
|---|---|---|
| `postgres` | Toàn bộ dữ liệu nghiệp vụ và kho tri thức (image `pgvector/pgvector:pg17`: PostgreSQL có sẵn pgvector, dùng để tìm tri thức theo nghĩa). Volume `postgres-data`. | không |
| `minio` | Ảnh và tệp, trong một bucket riêng tư. Volume `minio-data`. | không |
| `init` | Chạy một lần mỗi khi khởi động rồi dừng: tạo/nâng schema, nạp tổ chức gốc, dựng thế giới mẫu, tạo vai trò database của API, tạo bucket và khóa riêng của API, tạo tài khoản đăng nhập đầu tiên, nạp tri thức. Chạy lại không thêm, không ghi đè gì. | không |
| `api` | Backend nghiệp vụ; chờ `init` xong. | `127.0.0.1:8000` |
| `scheduler` | Mỗi phút: cảnh báo và báo quá hạn xử lý, cho đặt chỗ chưa thanh toán và lượt khách không tới hết hạn. | không |
| `platform-sync` | Cầu nối với platform AI: gửi lệnh và sự kiện tiến độ, ghi lời của agent điều phối vào chat. Chưa khai báo platform thì chỉ chờ. | không |
| `reception` | Agent lễ tân; gọi `api`, tìm tri thức qua `api`. | không |
| `resident` | Landing page `/`, ứng dụng cư dân `/resident` và trang đăng nhập chung `/login`. | không |
| `operations` | Ban quản lý, quản trị viên, nhân viên hiện trường. | không |
| `gateway` | Địa chỉ duy nhất: `/` là landing page, `/resident` là app cư dân, `/login` là đăng nhập, `/operations` là app nhân viên, `/api/business` là API. | `127.0.0.1:8080` |

Database và kho ảnh không mở cổng ra ngoài. Ảnh do trình duyệt gửi đi qua API (qua `gateway`, tối đa 25 MB), API lưu vào MinIO và cũng là nơi duy nhất trả ảnh ra, sau khi kiểm tra người hỏi.

API chạy bằng vai trò database `vinhomes_api`: không phải chủ database, không vượt được phân quyền theo dòng. Chỉ `init` dùng vai trò chủ.

## Đăng nhập thế giới mẫu

Mật khẩu của mọi tài khoản dưới đây là giá trị `DEMO_PASSWORD` trong `deploy/deployment.env`. Tên đăng nhập là email:

| Tên đăng nhập | Người | Vào đâu |
|---|---|---|
| `local-v3-admin@example.invalid` | Quản trị viên | Quản lý tài khoản |
| `mock-minh@example.invalid` | Quản lý Minh (Ban quản lý) | Bảng công việc |
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

**Đặt lại thế giới mẫu** (xóa toàn bộ dữ liệu và ảnh, dựng lại từ đầu; bí mật giữ nguyên):

```powershell
dc down -v
dc up -d
```

**Hệ thống dựng trước tối 11/10/2026** phải làm đúng bước đặt lại này một lần. Tệp `0013_knowledge.sql` đã đổi (vector chuyển sang cột pgvector); database đã chạy bản cũ sẽ làm `init` dừng với câu "0013_knowledge.sql was changed after it was applied" và `api` không khởi động. `dc down -v` xóa mọi dữ liệu đã nhập tay trong database mẫu (ví dụ ca trực thêm cho nhân viên) và ảnh đã tải lên; cần giữ thì sao lưu trước (ngay dưới). Các khóa platform trong `deployment.env` vẫn dùng được, không phải khai báo lại với platform.

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

1. Trong `deploy/deployment.env` đặt `VINHOMES_SAMPLE_WORLD=0` **trước lần chạy đầu tiên** (hoặc `dc down -v` rồi chạy lại). Khi đó `init` không dựng thế giới mẫu và không tạo tài khoản mẫu.
2. `dc up -d --build`.
3. Tạo quản trị viên đầu tiên. Mật khẩu (12 đến 128 ký tự) đưa qua biến môi trường để không nằm trong lịch sử lệnh:

```powershell
$env:ADMIN_PASSWORD = '...'
dc run --rm -e ADMIN_PASSWORD init python -m vinhomes_api.database accounts --create-admin ten@congty.vn --password-env ADMIN_PASSWORD
```

4. Nạp dữ liệu của khu đô thị theo [docs/domain/NAP_DU_LIEU.md](../docs/domain/NAP_DU_LIEU.md): đặt các tệp CSV vào một thư mục rồi

```powershell
dc run --rm -v ${PWD}/du-lieu:/data:ro init python -m vinhomes_api.database import --dir /data --dry-run
dc run --rm -v ${PWD}/du-lieu:/data:ro init python -m vinhomes_api.database import --dir /data
```

5. Cho người đã nạp mật khẩu đầu tiên (theo mã người dùng hoặc email, cách nhau dấu phẩy). Người đã có mật khẩu được giữ nguyên; một tên không tồn tại thì lệnh dừng và không đổi gì:

```powershell
dc run --rm -e FIRST_PASSWORD init python -m vinhomes_api.database accounts --users a@congty.vn,b@congty.vn --password-env FIRST_PASSWORD
```

Lưu ý: bước nạp tổ chức gốc (`seed`) luôn chạy vì lệnh `import` xây trên nó (khu Ocean Park 1, các phân khu, Ban quản lý). Nó hiện mang theo vài người và yêu cầu mẫu (`local-v3-*`, `faker-resident-*`); những người này không có mật khẩu nên không đăng nhập được, nhưng yêu cầu mẫu vẫn hiện ở màn hình Ban quản lý. Tách tổ chức gốc khỏi dữ liệu mẫu là việc chưa làm.

**Database hoặc kho S3 có sẵn ở nơi khác.** Bỏ dấu `#` ở cuối `deployment.env`: `MIGRATION_DATABASE_URL` (chủ database, dạng `postgresql://`), `VINHOMES_API_DATABASE_URL` (vai trò `vinhomes_api` với `API_DB_PASSWORD`, dạng `postgresql+asyncpg://`), `S3_ENDPOINT`. Với S3 riêng, khóa `S3_ACCESS_KEY`/`S3_SECRET_KEY` phải có sẵn ở đó và đặt `MINIO_ROOT_USER=` (trống). PostgreSQL ở nơi khác phải có pgvector: người quản trị ở đó chạy `create extension vector` trong database **trước** lần khởi động đầu tiên (chỉ superuser tạo được extension này; dịch vụ PostgreSQL thuê ngoài gọi nó là `vector`), nếu không `init` dừng ở `0013_knowledge.sql`. Hai container `postgres` và `minio` vẫn khởi động nhưng không được dùng. Cách này mới được kiểm tra ở mức cấu hình, chưa chạy thật.

## Đưa lên server

Dùng khi Vinhomes chạy trên một server riêng và platform AI chạy trên server khác. Thêm dịch vụ `caddy` (profile `public`): nó là cửa duy nhất mở ra internet, tự xin và gia hạn chứng chỉ HTTPS, đưa người dùng vào các app và đưa platform vào `/mcp`. PostgreSQL, MinIO, API và Reception vẫn không có cổng ra ngoài.

Cần có: server có địa chỉ IP công khai, mở cổng 80 và 443, và một tên trỏ về IP đó. Chưa có tên miền thì dùng tạm tên miễn phí theo IP, ví dụ IP `203.0.113.5` thành `203-0-113-5.sslip.io`.

1. Trên server: lấy mã về, chạy `deploy/new-env.sh`, điền `OPENAI_API_KEY`.
2. Trong `deploy/deployment.env` đặt:

   ```
   VINHOMES_DOMAIN=<tên của server>
   VINHOMES_ALLOWED_ORIGINS=https://<tên của server>
   SECURE_COOKIES=1
   PLATFORM_IPS=<IP của server platform>
   TRUSTED_PROXY_HOPS=2
   ```

   `TRUSTED_PROXY_HOPS=2` cho API biết phía trước nó có hai lớp proxy của mình (Caddy và cổng chung), để giới hạn 60 lần đăng nhập trong 5 phút tính theo địa chỉ thật của từng người. Không có Caddy thì giữ mặc định 1. Đặt sai số này thì mọi người bị tính chung một địa chỉ, hoặc người gọi tự khai được địa chỉ.

   `PLATFORM_IPS` để trống thì `/mcp` chỉ được bảo vệ bằng token.
3. Khởi động: `docker compose --env-file deploy/deployment.env -f deploy/compose.yml --profile public up -d --build`.
4. Kiểm tra từ một máy khác: `https://<tên>/login` mở được; `curl -i https://<tên>/mcp` trả 401 (từ IP của platform) hoặc 403 (từ nơi khác).
5. Nối platform theo [platform/README.md](platform/README.md), với địa chỉ công cụ là `https://<tên>/mcp`. `VINHOMES_API_PLATFORM_URL` là địa chỉ công khai của platform.

Đã kiểm tra trên máy phát triển với chứng chỉ nội bộ của Caddy: app, `/mcp` có và không có token, chặn theo IP. Chưa kiểm tra trên server thật: việc xin chứng chỉ Let's Encrypt và tên `sslip.io`.

## Phát hành qua registry

Mặc định server tự build từ mã nguồn. Để build một nơi rồi kéo image về, đặt tiền tố có địa chỉ registry và một nhãn phiên bản (trong `deployment.env` hoặc biến môi trường):

```
VINHOMES_IMAGE_PREFIX=ghcr.io/<tổ chức>/vinhomes
VINHOMES_IMAGE_TAG=2026-10-12
```

Trên máy build (đã `docker login` vào registry): `dc build` rồi `dc push api reception resident operations backup`.

Chỉ phát hành landing page/app cư dân: đặt `VINHOMES_RESIDENT_IMAGE_TAG=<nhãn frontend mới>`, giữ `VINHOMES_IMAGE_TAG` cho các dịch vụ còn lại. Build/push riêng `resident`, rồi trên server `dc pull resident` và `dc up -d --no-deps --no-build resident`. Bỏ giá trị riêng này để `resident` dùng lại nhãn chung; khi rollback frontend cần đổi chính `VINHOMES_RESIDENT_IMAGE_TAG`.

Trên server chỉ cần các tệp `deploy/compose.yml`, `deploy/Caddyfile`, `deploy/nginx/*.template` và `deploy/deployment.env` (cùng hai giá trị trên), không cần mã nguồn: `dc pull api reception resident operations backup` rồi `dc up -d --no-build`.

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

Sau khi đăng nhập, `GET /auth/session` cho biết người đó dùng không gian nào (`audiences`) và vai trò vận hành (`operationsRole`): cư dân vào `/`, quản lý vào `/operations/kanban`, nhân viên hiện trường vào `/operations/my-tasks`, quản trị viên vào `/operations/accounts`. Cả ba nơi dùng chung một cookie `vinhomes_session`.

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
