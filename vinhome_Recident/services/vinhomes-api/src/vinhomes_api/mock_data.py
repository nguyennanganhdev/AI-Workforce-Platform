"""A believable Vinhomes-style world for the golden scenarios (docs/domain/KICH_BAN_VANG.md section 3).

    python -m vinhomes_api.database mock --url URL [--profile test|standard] [--seed 42]

Ids are derived from names, so running it twice adds nothing. Everything that has a life cycle (statements, passes,
cards, bookings, permits, requests) is created in its first status and moved along by updates, so the database's own
rules judge the data. Dates are relative to the day it runs. It needs the base sample (`database seed`) first and a role
that is not held to row level security, like `seed`.
"""

import json
import random
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import asyncpg

TENANT = uuid.UUID("11111111-1111-5111-a111-111111111111")
SITE = uuid.UUID("66666666-6666-5666-a666-666666666666")
DOMAIN = uuid.UUID("22222222-2222-5222-a222-222222222222")
MANAGEMENT = uuid.UUID("88888888-8888-5888-a888-888888888888")
CAT_TECH = uuid.UUID("33333333-3333-5333-a333-333333333333")
CAT_SEC = uuid.UUID("33333333-3333-5333-a333-333333333334")
NS = uuid.UUID("5d0f1c7e-0000-4000-8000-00000000f1f1")


def uid(*parts) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(str(p) for p in parts))


@dataclass(frozen=True)
class Profile:
    extra_towers: int
    townhouses: int
    months: int
    history_tickets: int
    staff: int
    handbook_variants: bool


PROFILES = {
    "test": Profile(extra_towers=0, townhouses=0, months=3, history_tickets=40, staff=6, handbook_variants=False),
    "standard": Profile(extra_towers=3, townhouses=50, months=6, history_tickets=900, staff=24, handbook_variants=True),
}

FAMILY = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
MIDDLE = ["Văn", "Thị", "Minh", "Quốc", "Thanh", "Ngọc", "Hữu", "Đức", "Anh", "Gia", "Bảo", "Thu"]
GIVEN = ["An", "Bình", "Châu", "Dũng", "Em", "Giang", "Hà", "Hải", "Hoa", "Hùng", "Khoa", "Lan", "Linh", "Long", "Mai", "Nam", "Phúc", "Quang", "Sơn", "Thảo", "Trang", "Tuấn", "Vy", "Yến"]
ISSUES = [
    ("Rò nước vòi bếp", "Vòi bếp nhà tôi rò nước, nhỏ giọt cả ngày.", CAT_TECH, "normal"),
    ("Mất điện một phòng ngủ", "Phòng ngủ chính không có điện, các phòng khác bình thường.", CAT_TECH, "high"),
    ("Điều hòa kêu to", "Điều hòa phòng khách chạy kêu to và không mát.", CAT_TECH, "normal"),
    ("Ống thoát nước nhà tắm chậm", "Nước thoát rất chậm ở sàn nhà tắm.", CAT_TECH, "normal"),
    ("Đèn hành lang tầng không sáng", "Đèn hành lang trước cửa nhà đã hỏng hai ngày.", CAT_TECH, "low"),
    ("Thang máy dừng sai tầng", "Thang máy B thỉnh thoảng dừng lệch tầng.", CAT_TECH, "high"),
    ("Nghe tiếng ồn khoan đục ngoài giờ", "Căn bên cạnh khoan đục sau 18 giờ.", CAT_SEC, "normal"),
    ("Người lạ ở sảnh", "Có người lạ ngồi lâu ở sảnh tòa nhà.", CAT_SEC, "high"),
    ("Cửa chống cháy bị chèn", "Cửa thoát hiểm tầng bị để đồ chèn lối đi.", CAT_SEC, "high"),
    ("Thấm tường phòng khách", "Tường phòng khách xuất hiện vết thấm sau mưa.", CAT_TECH, "normal"),
]
ISSUE_STATES = [("closed", 55), ("resolved", 10), ("in_progress", 10), ("assigned", 8), ("triaging", 5), ("open", 7), ("cancelled", 5)]
HANDBOOK = [
    ("Giờ thi công cải tạo căn hộ", "Thi công được phép từ 08:00 đến 17:00 các ngày trong tuần. Việc gây ồn (khoan, đục, cắt) chỉ trong khung 09:00 đến 16:00. Không thi công vào Chủ nhật và ngày lễ. Đăng ký thi công với Ban quản lý trước ít nhất 7 ngày. (Dữ liệu mẫu.)", ["resident"]),
    ("Đăng ký thẻ xe và hạn mức", "Mỗi căn hộ được đăng ký tối đa 4 thẻ xe và 6 thẻ cư dân. Mất thẻ cần báo ngay để khóa; thẻ mới được cấp sau khi Ban quản lý duyệt đơn. (Dữ liệu mẫu.)", ["resident"]),
    ("Đăng ký khách đến thăm", "Cư dân đăng ký khách qua ứng dụng, tối đa 10 lượt đang chờ. Khách quét mã QR tại cổng trong khung giờ đã đăng ký. (Dữ liệu mẫu.)", ["resident"]),
    ("Đặt tiện ích nội khu", "Khu BBQ, sân thể thao và phòng sinh hoạt có thể đặt trước tối đa 7 ngày. Hủy trước giờ bắt đầu ít nhất 2 giờ. (Dữ liệu mẫu.)", ["resident"]),
    ("Phí quản lý và cách tính", "Phí quản lý tính theo diện tích sử dụng; phí gửi xe theo số xe đăng ký; nước theo chỉ số đồng hồ. Thông báo phí phát hành đầu tháng, hạn đóng sau 20 ngày. (Dữ liệu mẫu.)", ["resident"]),
    ("Báo sự cố trong căn hộ", "Mô tả sự cố và gửi ảnh qua ứng dụng. Ban quản lý đề xuất phương án và giờ hẹn; bạn đồng ý rồi kỹ thuật viên mới đến. Sự cố khẩn cấp (rò gas, cháy, ngập) gọi ngay hotline. (Dữ liệu mẫu.)", ["resident"]),
    ("Chuyển đồ ra vào tòa nhà", "Chuyển đồ cần đăng ký trước 24 giờ, dùng thang hàng, trong khung 08:00 đến 17:00. (Dữ liệu mẫu.)", ["resident"]),
    ("Quy định thú cưng", "Thú cưng phải được dắt bằng dây, không vào khu hồ bơi và sảnh thang máy khách. (Dữ liệu mẫu.)", ["resident"]),
    ("Rác thải sinh hoạt", "Phân loại rác tại tầng, bỏ rác đúng giờ thu gom 07:00 và 19:00. (Dữ liệu mẫu.)", ["resident"]),
    ("Thông tin liên hệ", "Hotline Ban quản lý 1900 0000 (24/7). Lễ tân tầng 1 mỗi ngày 07:00 đến 21:00. Khẩn cấp an ninh: bấm nút SOS trong ứng dụng. (Dữ liệu mẫu.)", ["resident"]),
    ("Cắt nước, cắt điện theo kế hoạch", "Ban quản lý thông báo trước ít nhất 24 giờ, nêu rõ tòa và khung giờ. Mọi thay đổi sẽ được thông báo lại. (Dữ liệu mẫu.)", ["resident"]),
    ("Hồ sơ cư trú", "Chủ sở hữu và người thuê đăng ký thành viên trong căn hộ với giấy tờ tùy thân. Thành viên hộ chỉ xem và dùng dịch vụ, không thao tác tài chính. (Dữ liệu mẫu.)", ["resident"]),
    ("Gửi xe điện và sạc", "Khu sạc xe điện có hạn; đăng ký tại lễ tân. (Dữ liệu mẫu.)", ["resident"]),
    ("Nội quy sử dụng thang máy", "Không chở vật liệu xây dựng bằng thang khách; dùng thang hàng khi chuyển đồ. (Dữ liệu mẫu.)", ["resident"]),
]
STAFF_SOP = [
    ("Quy trình tiếp nhận và phân loại yêu cầu (nội bộ)", "Tiếp nhận trong 15 phút với mức khẩn; phân loại theo nhóm dịch vụ; gán đơn vị phụ trách; ghi lý do khi từ chối. (Dữ liệu mẫu.)", ["staff", "management"]),
    ("Quy trình lập phương án xử lý (nội bộ)", "Mỗi phương án có 3 đến 4 bước, người thực hiện đúng chuyên môn và đang trong ca, giờ hẹn ở tương lai, chi phí dự kiến và bên chịu chi phí. Phương án chờ duyệt rồi chờ cư dân đồng ý. (Dữ liệu mẫu.)", ["staff", "management"]),
    ("Quy trình nghiệm thu và đóng yêu cầu (nội bộ)", "Kỹ thuật viên hoàn thành kèm ảnh bằng chứng; cư dân xác nhận hoặc yêu cầu làm lại; Ban quản lý nghiệm thu rồi đóng. (Dữ liệu mẫu.)", ["staff", "management"]),
    ("Quy trình sự cố khẩn cấp (nội bộ)", "Sự cố khẩn được báo cho Ban quản lý của tòa ngay; bảo vệ xác nhận cảnh báo trong 60 giây, không xác nhận thì leo thang. Điều động hoặc hủy điều động bảo vệ cần Ban quản lý duyệt. (Dữ liệu mẫu.)", ["staff", "management"]),
    ("Quy trình phát hành thông báo (nội bộ)", "Thông báo được soạn ở dạng nháp; Ban quản lý duyệt nội dung, chọn tòa nhận rồi phát hành. Thông báo cắt dịch vụ phải gửi trước 24 giờ. (Dữ liệu mẫu.)", ["management"]),
    ("Quy trình xử lý nợ phí quá hạn (nội bộ)", "Nhắc lần 1 sau hạn 1 ngày, lần 2 sau 15 ngày, lần 3 cảnh báo ngừng dịch vụ sau 30 ngày. (Dữ liệu mẫu.)", ["management"]),
]
POLICIES = [
    ("building-rules", "Nội quy tòa nhà", "building_rules", "Nội quy chung của cư dân: giữ yên tĩnh sau 22:00, không để đồ ngoài hành lang, không hút thuốc ở khu vực chung. (Dữ liệu mẫu.)", ["resident"]),
    ("construction-rules", "Quy định thi công cải tạo", "construction_rules", "Hồ sơ gồm bản vẽ, cam kết, hợp đồng nhà thầu; đặt cọc theo quy định phân khu; hoàn cọc sau nghiệm thu. (Dữ liệu mẫu.)", ["resident"]),
    ("amenity-rules", "Quy định sử dụng tiện ích", "amenity_rules", "Đặt trước trong hạn mức tuần; đến muộn quá 15 phút lượt đặt bị hủy. (Dữ liệu mẫu.)", ["resident"]),
    ("fees", "Biểu phí dịch vụ", "fee_table", "Phí quản lý 12.000 đ/m²/tháng; gửi xe máy 100.000 đ/tháng; ô tô 1.200.000 đ/tháng; nước 15.000 đ/m³. (Dữ liệu mẫu.)", ["resident", "staff", "management"]),
    ("terms", "Điều khoản sử dụng ứng dụng", "terms_of_use", "Cư dân chịu trách nhiệm về thông tin đã khai. (Dữ liệu mẫu.)", ["resident"]),
    ("faq", "Câu hỏi thường gặp", "faq", "Quên mật khẩu: dùng OTP qua số điện thoại đã đăng ký. Đổi chủ hộ: nộp hồ sơ tại lễ tân. (Dữ liệu mẫu.)", ["resident", "staff"]),
]


class World:
    def __init__(self, conn: asyncpg.Connection, profile: Profile, seed: int):
        self.c = conn
        self.p = profile
        self.rng = random.Random(seed)
        self.today = date.today()
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.towers: list[str] = []
        self.units: dict[str, dict] = {}       # code -> row info
        self.residents: dict[str, list[tuple[str, str]]] = {}  # unit code -> [(user_id, relation)]
        self.users: dict[str, str] = {}        # user id -> display name
        self.counts: dict[str, int] = {}
        self.workers: list[dict] = []          # staff who can take work: id, user, category, places left
        self.phones: set[str] = {"0901000001", "0901000002", "0901000003", "0901000004", "0901000005", "0902000001"}

    def count(self, name: str, n: int = 1):
        self.counts[name] = self.counts.get(name, 0) + n

    def person(self) -> str:
        return f"{self.rng.choice(FAMILY)} {self.rng.choice(MIDDLE)} {self.rng.choice(GIVEN)}"

    def phone(self) -> str:
        while True:
            number = "09" + "".join(str(self.rng.randrange(10)) for _ in range(8))
            if number not in self.phones:
                self.phones.add(number)
                return number

    async def user(self, user_id: str, name: str | None = None, phone: str | None = None):
        name = name or self.person()
        phone = phone or self.phone()
        await self.c.execute("insert into users(id,email,name,status,phone_e164) values($1,$2,$3,'active',$4) on conflict(id) do nothing",
                             user_id, f"{user_id}@example.invalid", name, "+84" + phone[1:])
        await self.c.execute("insert into tenant_memberships(id,tenant_id,user_id,status,joined_at) values($1,$2,$3,'active',now()) on conflict(id) do nothing",
                             uid("membership", user_id), TENANT, user_id)
        self.users[user_id] = name

    def holder(self, code: str) -> str | None:
        """The verified owner or tenant of a home: the person who answers for it."""
        return next((u for u, r in self.residents.get(code, []) if r in ("owner", "tenant")), None)

    # ---------- places ----------

    async def places(self):
        """Uses the Ocean Park buildings the base sample already has, and adds a villa and a townhouse cluster."""
        self.zone = {}
        for key, code in (("PK1", "sapphire"), ("PK2", "hai-au"), ("PK3", "sao-bien"), ("ZEN", "zenpark")):
            self.zone[key] = await self.c.fetchval("select id from zones where site_id=$1 and code=$2", SITE, code)
            if self.zone[key] is None:
                raise SystemExit(f"The base sample has no zone {code}; run `database seed` first.")
        towers = [("S1.01", "PK1"), ("S1.02", "PK1"), ("S2.01", "PK1"), ("S2.05", "PK1"), ("R1.02", "ZEN")][:2 + self.p.extra_towers]
        clusters = [("HA2", "PK2", "Khu villa Hải Âu HA2")] + ([("SB1", "PK3", "Khu nhà phố Sao Biển SB1")] if self.p.townhouses else [])
        self.buildings: dict[str, str] = {}
        self.building_id: dict[str, uuid.UUID] = {}
        self.scope_id: dict[str, uuid.UUID] = {}
        for code, zone in towers:
            row = await self.c.fetchrow("select id,zone_id from buildings where site_id=$1 and code=$2", SITE, code)
            if row is None:
                raise SystemExit(f"The base sample has no building {code}; run `database seed` first.")
            self.building_id[code], self.buildings[code] = row["id"], zone
            self.zone[zone] = row["zone_id"]
        for code, zone, name in clusters:
            self.building_id[code], self.buildings[code] = uid("building", code), zone
            await self.c.execute("insert into buildings(id,tenant_id,site_id,zone_id,code,name,status) values($1,$2,$3,$4,$5,$6,'active') on conflict(id) do nothing",
                                 uid("building", code), TENANT, SITE, self.zone[zone], code, name)
        for code in self.buildings:
            scope = await self.c.fetchval("select id from access_scopes where kind='building' and building_id=$1 and tenant_id=$2 limit 1", self.building_id[code], TENANT)
            if scope is None:
                scope = uid("scope", code)
                await self.c.execute("insert into access_scopes(id,tenant_id,kind,building_id) values($1,$2,'building',$3) on conflict(id) do nothing", scope, TENANT, self.building_id[code])
            self.scope_id[code] = scope
            for category in (CAT_TECH, CAT_SEC):
                if not await self.c.fetchval("select 1 from management_coverage where scope_id=$1 and service_category_id=$2 and tenant_id=$3 and valid_to is null", scope, category, TENANT):
                    await self.c.execute("insert into management_coverage(id,tenant_id,management_unit_id,scope_id,service_category_id,valid_from) values($1,$2,$3,$4,$5,'2026-01-01T00:00:00Z') on conflict(id) do nothing",
                                         uid("coverage", code, category), TENANT, MANAGEMENT, scope, category)
        self.towers = [code for code, _ in towers]
        rows = []
        for code in self.towers:
            for floor in range(1, 16):
                for n in range(1, 5):
                    rows.append((code, f"{code}-{floor:02d}{n:02d}", "apartment", str(floor), round(self.rng.uniform(45, 120), 1)))
        for n in range(1, 11):
            rows.append(("HA2", f"HA2.{n:02d}", "villa", "1", round(self.rng.uniform(180, 320), 1)))
        for n in range(1, self.p.townhouses + 1):
            rows.append(("SB1", f"SB1.{n:02d}", "townhouse", "1", round(self.rng.uniform(80, 140), 1)))
        for building, code, kind, floor, area in rows:
            await self.c.execute("insert into units(id,tenant_id,site_id,zone_id,building_id,code,unit_kind,floor,status) values($1,$2,$3,$4,$5,$6,$7,$8,'active') on conflict(id) do nothing",
                                 uid("unit", code), TENANT, SITE, self.zone[self.buildings[building]], self.building_id[building], code, kind, floor)
            self.units[code] = {"id": uid("unit", code), "building": building, "zone": self.zone[self.buildings[building]], "kind": kind, "area": area}
        self.count("units", len(rows))
        # The villa zone sets its own rules; the towers keep the standard ones (table zone_settings).
        await self.c.execute("""insert into zone_settings(tenant_id,zone_id,visit_max_waiting,visit_max_hours,visit_auto_approve_max_guests,card_limit_resident,card_limit_vehicle,note)
            values($1,$2,20,96,8,8,6,'Khu villa có hạn mức rộng hơn khu căn hộ (dữ liệu mẫu)') on conflict do nothing""", TENANT, self.zone["PK2"])

    # ---------- people ----------

    async def people(self):
        named = {"an": ("Nguyễn Văn An", "0901000001"), "chau": ("Lê Minh Châu", "0901000002"), "binh": ("Trần Thị Bình", "0901000003"),
                 "dung": ("Phạm Quốc Dũng", "0901000004"), "em": ("Hoàng Thị Em", "0901000005")}
        for key, (name, phone) in named.items():
            await self.user(f"mock-{key}", name, phone)
        links = [("mock-an", "S1.01-1201", "owner", "verified"), ("mock-chau", "S1.01-1201", "household", "verified"),
                 ("mock-binh", "S1.02-0803", "tenant", "verified"), ("mock-dung", "S1.01-1502", "owner", "verified"),
                 ("mock-dung", "HA2.05", "owner", "verified"), ("mock-em", "S1.01-0402", "household", "pending")]
        taken = {code for _, code, _, _ in links}
        for key, code in (("0803", "S1.02-0803"), ("0402", "S1.01-0402")):  # homes whose named person is not the owner
            await self.user(f"mock-owner-{key}")
            links.append((f"mock-owner-{key}", code, "owner", "verified"))
        index = 0
        for code in self.units:
            if code in taken:
                continue
            if self.rng.random() < 0.12:
                continue  # vacant
            index += 1
            owner = f"mock-r-{index:04d}"
            await self.user(owner)
            if self.rng.random() < 0.25:
                links.append((owner, code, "owner", "verified"))
                tenant = f"mock-t-{index:04d}"
                await self.user(tenant)
                links.append((tenant, code, "tenant", "verified"))
            else:
                links.append((owner, code, "owner", "verified"))
            for k in range(self.rng.choice([0, 0, 1, 2])):
                member = f"mock-h-{index:04d}-{k}"
                await self.user(member)
                links.append((member, code, "household", "verified"))
        for user, code, relation, status in links:
            await self.c.execute("""insert into unit_residents(id,tenant_id,unit_id,user_id,relation,verification_status,valid_from,verified_by,verified_at)
                values($1,$2,$3,$4,$5,$6,'2026-01-01T00:00:00Z',$7,$8) on conflict(id) do nothing""",
                                 uid("link", user, code, relation), TENANT, self.units[code]["id"], user, relation, status,
                                 "local-v3-admin" if status == "verified" else None, self.now if status == "verified" else None)
            self.residents.setdefault(code, []).append((user, relation))
        self.count("residents", len(self.users))

    async def staff(self):
        fixed = [("hoa", "Kỹ thuật viên Hoa", CAT_TECH, "available"), ("khoa", "Kỹ thuật viên Khoa", CAT_TECH, "on_leave"), ("giang", "Bảo vệ Giang", CAT_SEC, "available")]
        people = list(fixed)
        for n in range(self.p.staff - len(fixed)):
            people.append((f"s{n + 1:02d}", self.person(), CAT_TECH if n % 3 else CAT_SEC, "available"))
        await self.user("mock-minh", "Quản lý Minh", "0902000001")
        await self.c.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values($1,$2,$3,$4,'management','local-v3-admin','2026-01-01T00:00:00Z') on conflict(id) do nothing",
                             uid("role", "mock-minh"), TENANT, uid("membership", "mock-minh"), uuid.UUID("99999999-9999-5999-a999-999999999998"))
        for key, name, category, availability in people:
            user = f"mock-{key}"
            await self.user(user, name)
            staff_id = uid("staff", key)
            await self.c.execute("insert into staff_profiles(id,tenant_id,user_id,management_unit_id,employee_code,availability,max_concurrent_jobs) values($1,$2,$3,$4,$5,$6,3) on conflict(id) do nothing",
                                 staff_id, TENANT, user, MANAGEMENT, f"MOCK-{key.upper()}", availability)
            await self.c.execute("insert into staff_specialties(tenant_id,staff_id,category_id,proficiency) values($1,$2,$3,'standard') on conflict do nothing", TENANT, staff_id, category)
            for building in self.buildings:
                await self.c.execute("insert into scoped_user_roles(id,tenant_id,membership_id,scope_id,role_code,granted_by,valid_from) values($1,$2,$3,$4,'staff','local-v3-admin','2026-01-01T00:00:00Z') on conflict(id) do nothing",
                                     uid("role", user, building), TENANT, uid("membership", user), self.scope_id[building])
            if availability == "available":
                self.workers.append({"id": staff_id, "user": user, "category": category, "left": 3})
                night = key == "giang" or (category == CAT_SEC)
                for d in range(-30, 31):
                    day = datetime.combine(self.today + timedelta(days=d), time(0), tzinfo=timezone.utc)
                    start, end = (day + timedelta(hours=13), day + timedelta(hours=23, minutes=59)) if night else (day + timedelta(hours=1), day + timedelta(hours=10))
                    await self.c.execute("insert into staff_shifts(id,tenant_id,staff_id,starts_at,ends_at,status) values($1,$2,$3,$4,$5,'available') on conflict(id) do nothing",
                                         uid("shift", key, d), TENANT, staff_id, start, end)
        self.count("staff", len(people) + 1)

    # ---------- money ----------

    async def statements(self):
        first_this = self.today.replace(day=1)
        months = []
        month = first_this
        for _ in range(self.p.months):
            months.append(month)
            month = (month - timedelta(days=1)).replace(day=1)
        months.reverse()  # oldest first
        notes, lines = [], []
        plan: dict[uuid.UUID, str] = {}
        for code, unit in self.units.items():
            if code not in self.residents:
                continue
            owner = self.holder(code)
            cars = 1 if self.rng.random() < 0.25 else 0
            bikes = 1 if self.rng.random() < 0.7 else 0
            for i, m in enumerate(months):
                nid = uid("dn", code, m.isoformat())
                age = len(months) - 1 - i  # 0 = this month
                issue = m + timedelta(days=4)
                due = issue + timedelta(days=20)
                items = [("management", f"Phí quản lý {m:%m/%Y}", unit["area"], 12000, round(unit["area"] * 12000))]
                if bikes:
                    items.append(("parking", "Gửi xe máy", 1, 100000, 100000))
                if cars:
                    items.append(("parking", "Gửi ô tô", 1, 1200000, 1200000))
                m3 = self.rng.randint(8, 32)
                items.append(("water", f"Nước {m3} m³", m3, 15000, m3 * 15000))
                subtotal = sum(x[4] for x in items)
                vat = round(items[0][4] * 0.1)
                roll = self.rng.random()
                if code == "S1.01-1201":
                    status = "overdue" if age == 1 else "issued" if age == 0 else "paid"
                elif code == "S1.02-0803" or age >= 2:
                    status = "paid" if roll < 0.94 else "overdue"
                elif age == 1:
                    status = "paid" if roll < 0.75 else "partially_paid" if roll < 0.82 else "overdue"
                else:
                    status = "paid" if roll < 0.3 else "issued"
                plan[nid] = status
                notes.append((nid, TENANT, f"DN{m:%Y%m}-{code}", unit["id"], m, issue, due, subtotal, vat, subtotal + vat, owner))
                for n, (kind, desc, qty, price, amount) in enumerate(items, 1):
                    lines.append((uid("dnl", nid, n), TENANT, nid, n, kind, desc, qty, price, amount, m, (m + timedelta(days=31)).replace(day=1) - timedelta(days=1)))
        await self.c.executemany("""insert into debit_notes(id,tenant_id,doc_no,unit_id,period_month,kind,issue_date,due_date,subtotal,vat_amount,total_amount,paid_amount,status,payer_user_id)
            values($1,$2,$3,$4,$5,'monthly',$6,$7,$8,$9,$10,0,'draft',$11) on conflict(id) do nothing""", notes)
        await self.c.executemany("""insert into debit_note_lines(id,tenant_id,debit_note_id,line_no,fee_kind,description,quantity,unit_price,amount,service_from,service_to)
            values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) on conflict(id) do nothing""", lines)
        await self.c.executemany("update debit_notes set status='issued' where id=$1 and status='draft'", [(n[0],) for n in notes])
        by_status: dict[str, list[uuid.UUID]] = {}
        for nid, status in plan.items():
            by_status.setdefault(status, []).append(nid)
        await self.c.executemany("update debit_notes set status='paid',paid_amount=total_amount where id=$1 and status='issued'", [(n,) for n in by_status.get("paid", [])])
        await self.c.executemany("update debit_notes set status='partially_paid',paid_amount=total_amount/2 where id=$1 and status='issued'", [(n,) for n in by_status.get("partially_paid", [])])
        await self.c.executemany("update debit_notes set status='overdue' where id=$1 and status='issued'", [(n,) for n in by_status.get("overdue", [])])
        self.count("debit_notes", len(notes))

    # ---------- vehicles and cards ----------

    async def cards(self):
        n_cards = 0
        for code, unit in self.units.items():
            if code not in self.residents:
                continue
            holder = self.holder(code)
            named = code == "S1.01-1201"
            for k in range(self.rng.choice([1, 2, 2, 3]) if not named else 2):
                number = f"C-MOCK-AN-R{k + 1}" if named else f"C-{uid('card', code, 'r', k).hex[:10].upper()}"
                await self.card(code, unit, number, "resident", holder, None)
                n_cards += 1
            vehicles = []
            if named:
                vehicles = [("motorbike", "29A1-" + "000.01", "C-MOCK-AN-V1")]
            else:
                if self.rng.random() < 0.7:
                    vehicles.append(("motorbike", f"{self.rng.randint(10, 99)}{self.rng.choice('ABCDEFGH')}1-{self.rng.randint(100, 999)}.{self.rng.randint(10, 99)}", None))
                if self.rng.random() < 0.25:
                    vehicles.append(("car", f"{self.rng.randint(10, 99)}A-{self.rng.randint(100, 999)}.{self.rng.randint(10, 99)}", None))
            for k, (kind, plate, number) in enumerate(vehicles):
                vid = uid("vehicle", code, k)
                await self.c.execute("insert into vehicles(id,tenant_id,unit_id,owner_user_id,owner_name,kind,plate_no,status) values($1,$2,$3,$4,$5,$6,$7,'active') on conflict(id) do nothing",
                                     vid, TENANT, unit["id"], holder, self.users.get(holder, holder), kind, plate)
                await self.card(code, unit, number or f"C-{uid('card', code, 'v', k).hex[:10].upper()}", "vehicle", holder, vid, fee=100000 if kind == "motorbike" else 1200000)
                n_cards += 1
        self.count("cards", n_cards)

    async def card(self, code, unit, number, kind, holder, vehicle_id, fee=None):
        cid = uid("card", number)
        await self.c.execute("""insert into access_cards(id,tenant_id,card_no,kind,holder_user_id,holder_name,unit_id,vehicle_id,status,monthly_fee)
            values($1,$2,$3,$4,$5,$6,$7,$8,'pending_issue',$9) on conflict(id) do nothing""", cid, TENANT, number, kind, holder, self.users.get(holder), unit["id"], vehicle_id, fee)
        await self.c.execute("update access_cards set status='active',issued_at=$2,valid_from=$3 where id=$1 and status='pending_issue'", cid, self.now - timedelta(days=200), self.today - timedelta(days=200))
        if not number.startswith("C-MOCK-AN") and self.rng.random() < 0.04:
            await self.c.execute("update access_cards set status='lost' where id=$1 and status='active'", cid)
        elif not number.startswith("C-MOCK-AN") and self.rng.random() < 0.03:
            await self.c.execute("update access_cards set status='suspended' where id=$1 and status='active'", cid)

    # ---------- visitors ----------

    async def visitors(self):
        n = 0
        for code, unit in self.units.items():
            if code not in self.residents:
                continue
            host = self.holder(code)
            for k in range(self.rng.choice([0, 1, 1, 2])):
                when = self.now + timedelta(days=self.rng.randint(-50, 6), hours=self.rng.randint(-5, 5))
                await self.visitor(code, unit, host, f"{code}-{k}", when)
                n += 1
        # the characters of the scenarios
        await self.visitor("S1.01-1201", self.units["S1.01-1201"], "mock-an", "an-future", self.now + timedelta(days=1, hours=2), name="Bạn của anh An")
        self.count("visitor_passes", n + 1)

    async def visitor(self, code, unit, host, key, when, name=None):
        pid = uid("visitor", key)
        past = when < self.now
        auto = self.rng.random() < 0.8
        await self.c.execute("""insert into visitor_passes(id,tenant_id,code,unit_id,host_user_id,guest_name,guest_phone,guest_count,purpose,visit_from,visit_to,status)
            values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'pending_approval') on conflict(id) do nothing""",
                             pid, TENANT, f"VP-{pid.hex[:8].upper()}", unit["id"], host, name or self.person(), self.phone(), self.rng.randint(1, 4),
                             self.rng.choice(["family_visit", "family_visit", "delivery", "service_provider"]), when, when + timedelta(hours=3))
        if not auto and past:
            await self.c.execute("update visitor_passes set status='rejected' where id=$1 and status='pending_approval'", pid)
            return
        await self.c.execute("update visitor_passes set status='approved',qr_token=$2 where id=$1 and status='pending_approval'", pid, secrets.token_urlsafe(24))
        if not past:
            return
        roll = self.rng.random()
        if roll < 0.7:
            await self.c.execute("update visitor_passes set status='checked_in' where id=$1 and status='approved'", pid)
            await self.c.execute("update visitor_passes set status='checked_out' where id=$1 and status='checked_in'", pid)
        elif roll < 0.85:
            await self.c.execute("update visitor_passes set status='expired' where id=$1 and status='approved'", pid)
        else:
            await self.c.execute("update visitor_passes set status='cancelled' where id=$1 and status='approved'", pid)

    # ---------- amenities ----------

    async def amenities(self):
        defs = [
            ("BBQ-S1", "Khu BBQ Sapphire", "bbq", "PK1", ["pit1", "pit2", "pit3", "pit4"], 0, 120, "17:00", "22:00", 2, 10, "Tối đa 10 người mỗi lượt."),
            ("TENNIS-S1", "Sân tennis Sapphire", "sport", "PK1", ["court1", "court2"], 80000, 60, "06:00", "22:00", 3, 4, "Mang giày đế mềm."),
            ("GYM-S1", "Phòng gym Sapphire", "gym", "PK1", ["main"], 0, 60, "05:00", "22:00", None, 1, ""),
            ("POOL-V2", "Hồ bơi khu Villa", "pool", "PK2", ["main"], 0, 60, "06:00", "21:00", 3, 6, "Trẻ em cần người lớn đi cùng."),
            ("HALL-S1", "Phòng sinh hoạt cộng đồng", "community_room", "PK1", ["main"], 300000, 120, "08:00", "21:00", 1, 30, "Dọn dẹp sau khi sử dụng."),
        ]
        bookings = 0
        for code, name, category, zone, areas, price, slot, open_at, close_at, quota, guests, note in defs:
            aid = uid("amenity", code)
            await self.c.execute("""insert into amenities(id,tenant_id,code,zone_id,name,category,areas,price,slot_minutes,open_time,close_time,max_advance_days,cancel_before_hours,weekly_quota_per_unit,max_guests,rules_note)
                values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,7,2,$12,$13,$14) on conflict(id) do nothing""",
                                 aid, TENANT, code, self.zone[zone], name, category, areas, price, slot, time.fromisoformat(open_at), time.fromisoformat(close_at), quota, guests, note or None)
            taken: set[tuple[str, datetime]] = set()
            owners = [(c, u) for c, u in self.units.items() if c in self.residents and u["zone"] == self.zone[zone]]
            if not owners:
                continue
            for _ in range(60 if price == 0 else 25):
                code_unit, unit = self.rng.choice(owners)
                day = self.today + timedelta(days=self.rng.randint(-40, 7))
                slots = max(int((int(close_at[:2]) - int(open_at[:2])) * 60 / slot), 1)
                start = datetime.combine(day, time.fromisoformat(open_at), tzinfo=timezone(timedelta(hours=7))) + timedelta(minutes=slot * self.rng.randrange(slots))
                area = self.rng.choice(areas)
                if (area, start) in taken:
                    continue
                taken.add((area, start))
                user = self.holder(code_unit)
                bid = uid("booking", code, area, start.isoformat())
                total = price * 1
                await self.c.execute("""insert into amenity_bookings(id,tenant_id,code,amenity_id,area_code,unit_id,booked_by_user_id,start_at,end_at,guests,status,total_amount,qr_token)
                    values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) on conflict(id) do nothing""",
                                     bid, TENANT, f"AB-{bid.hex[:8].upper()}", aid, area, unit["id"], user, start, start + timedelta(minutes=slot), self.rng.randint(1, guests),
                                     "confirmed" if total == 0 else "pending_payment", total, secrets.token_urlsafe(18) if total == 0 else None)
                if total:
                    await self.c.execute("update amenity_bookings set status='confirmed',qr_token=$2 where id=$1 and status='pending_payment'", bid, secrets.token_urlsafe(18))
                past = start < self.now
                roll = self.rng.random()
                if past and roll < 0.8:
                    await self.c.execute("update amenity_bookings set status='checked_in' where id=$1 and status='confirmed'", bid)
                    await self.c.execute("update amenity_bookings set status='completed' where id=$1 and status='checked_in'", bid)
                elif past and roll < 0.88:
                    await self.c.execute("update amenity_bookings set status='no_show' where id=$1 and status='confirmed'", bid)
                elif roll > 0.85:
                    await self.c.execute("update amenity_bookings set status='cancelled',cancelled_at=$2,cancelled_by='resident',cancel_reason='Đổi lịch' where id=$1 and status='confirmed'", bid, start - timedelta(hours=6))
                bookings += 1
            await self.c.execute("insert into amenity_closures(id,tenant_id,amenity_id,from_ts,to_ts,reason) values($1,$2,$3,$4,$5,'Bảo trì định kỳ') on conflict(id) do nothing",
                                 uid("closure", code), TENANT, aid, self.now - timedelta(days=60), self.now - timedelta(days=59))
        self.count("amenity_bookings", bookings)

    # ---------- renovation ----------

    async def renovation(self):
        for zone, kind, deposit, workers, days, off in ((None, "apartment", 8_000_000, 6, 45, [7]), ("PK1", "apartment", 10_000_000, 8, 60, []),
                                                       ("PK2", "villa", 30_000_000, 15, 120, [7]), ("PK3", "townhouse", 20_000_000, 12, 90, [7])):
            await self.c.execute("""insert into construction_policies(id,tenant_id,zone_id,applies_to_unit_kind,work_time_from,work_time_to,noisy_time_from,noisy_time_to,no_work_weekdays,deposit_amount,overtime_fee_per_hour,max_workers,max_duration_days,effective_from,note)
                values($1,$2,$3,$4,'08:00','17:00','09:00','16:00',$5,$6,300000,$7,$8,'2026-01-01','Quy định mẫu.') on conflict(id) do nothing""",
                                 uid("policy", zone, kind), TENANT, self.zone[zone] if zone else None, kind, off, deposit, workers, days)
        path = {"submitted": ["submitted"], "appraised": ["submitted", "appraised"], "approved": ["submitted", "appraised", "approved"],
                "rejected": ["submitted", "rejected"], "in_progress": ["submitted", "appraised", "approved", "awaiting_deposit", "in_progress"],
                "completed": ["submitted", "appraised", "approved", "awaiting_deposit", "in_progress", "awaiting_acceptance", "completed"],
                "cancelled": ["cancelled"], "draft": []}
        owners = [(c, u) for c, u in self.units.items() if c in self.residents]
        n = 0
        for k in range(25):
            code, unit = ("S1.01-1201", self.units["S1.01-1201"]) if k == 0 else self.rng.choice(owners)
            final = "in_progress" if k == 0 else self.rng.choice(list(path))
            owner = self.holder(code)
            pid = uid("permit", k)
            start = self.today - timedelta(days=self.rng.randint(0, 50))
            await self.c.execute("""insert into construction_permits(id,tenant_id,code,unit_id,requester_user_id,contractor_name,category,scope_description,planned_start,planned_end,status,deposit_amount,deposit_status)
                values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'draft',$11,'none') on conflict(id) do nothing""",
                                 pid, TENANT, f"TC-{pid.hex[:8].upper()}", unit["id"], owner, "Công ty Nội thất Hòa Bình" if k % 2 else None,
                                 self.rng.choice(["minor_repair", "interior_fitout", "renovation"]), self.rng.choice(["Sơn lại và thay sàn gỗ", "Cải tạo nhà bếp", "Thay cửa và lát nền"]),
                                 start, start + timedelta(days=self.rng.randint(14, 50)), 10_000_000)
            previous = "draft"
            for step in path[final]:
                extra = ""
                if step == "rejected":
                    extra = ",reject_reason='Thiếu bản vẽ kết cấu'"
                if step == "awaiting_deposit":
                    extra = ",deposit_status='pending'"
                if step == "in_progress":
                    extra = ",deposit_status='held',actual_start=planned_start"
                await self.c.execute(f"update construction_permits set status=$2{extra} where id=$1 and status=$3", pid, step, previous)
                previous = step
            n += 1
        self.count("construction_permits", n)

    # ---------- the front desk ----------

    async def desk(self):
        paths = {"draft": [], "submitted": ["submitted"], "in_review": ["submitted", "in_review"], "need_more_info": ["submitted", "in_review", "need_more_info"],
                 "approved": ["submitted", "in_review", "approved"], "rejected": ["submitted", "in_review", "rejected"], "fulfilled": ["submitted", "in_review", "approved", "fulfilled"], "cancelled": ["submitted", "cancelled"]}
        owners = [(c, u) for c, u in self.units.items() if c in self.residents]
        n = 0
        for k in range(150 if self.p.history_tickets > 100 else 20):
            code, unit = self.rng.choice(owners)
            user = self.holder(code)
            final = self.rng.choice(list(paths))
            kind = self.rng.choice(["card_issue", "goods_move", "resident_register", "card_reissue"])
            rid = uid("request", k)
            await self.c.execute("""insert into service_requests(id,tenant_id,code,kind,unit_id,requester_user_id,channel,status,details)
                values($1,$2,$3,$4,$5,$6,'app','draft',$7) on conflict(id) do nothing""",
                                 rid, TENANT, f"SR-{rid.hex[:8].upper()}", kind, unit["id"], user, json.dumps({"mock": True}))
            previous = "draft"
            for step in paths[final]:
                extra = ",decision_note='Thiếu giấy tờ'" if step == "rejected" else ",submitted_at=now()-interval '3 days',sla_due_at=now()-interval '1 day'" if step == "submitted" else ""
                await self.c.execute(f"update service_requests set status=$2{extra} where id=$1 and status=$3", rid, step, previous)
                previous = step
            n += 1
        self.count("service_requests", n)

    # ---------- what people are told ----------

    async def knowledge(self):
        n = 0
        for i, (title, body, audience) in enumerate(HANDBOOK):
            for zone in (("PK1", "PK2") if self.p.handbook_variants else ("PK1",)):
                await self.c.execute("insert into handbook_articles(id,tenant_id,zone_id,seq,title,body_md,audience) values($1,$2,$3,$4,$5,$6,$7) on conflict(id) do nothing",
                                     uid("handbook", i, zone), TENANT, self.zone[zone], i, title, f"# {title}\n\n{body}" + (f"\n\nÁp dụng cho {zone}." if self.p.handbook_variants else ""), audience)
                n += 1
        for i, (title, body, audience) in enumerate(STAFF_SOP):
            await self.c.execute("insert into handbook_articles(id,tenant_id,seq,title,body_md,audience) values($1,$2,$3,$4,$5,$6) on conflict(id) do nothing",
                                 uid("handbook-sop", i), TENANT, 100 + i, title, f"# {title}\n\n{body}", audience)
            n += 1
        for code, title, kind, body, audience in POLICIES:
            await self.c.execute("insert into policy_documents(id,tenant_id,code,title,kind,version,body_md,audience,effective_from) values($1,$2,$3,$4,$5,'1.0',$6,$7,'2026-01-01') on conflict(id) do nothing",
                                 uid("policy-doc", code), TENANT, code, title, kind, f"# {title}\n\n{body}", audience)
            n += 1
        buildings = [self.building_id[c] for c in self.towers[:2]]
        for k in range(30):
            aid = uid("announcement", k)
            kind = ["news", "bulletin", "event_notice", "urgent_notice", "fee_notice"][k % 5]
            await self.c.execute("""insert into announcements(id,tenant_id,code,kind,title,summary,body_md,status,building_ids,zone_ids,author_user_id)
                values($1,$2,$3,$4,$5,$6,$7,'draft',$8,'{}','mock-minh') on conflict(id) do nothing""",
                                 aid, TENANT, f"AN-{aid.hex[:8].upper()}", kind, f"Thông báo mẫu số {k + 1}", "Nội dung tóm tắt (mẫu).", f"Nội dung thông báo mẫu số {k + 1}.", buildings if k % 3 == 0 else [])
            if k < 25:
                await self.c.execute("update announcements set status='published',published_at=$2 where id=$1 and status='draft'", aid, self.now - timedelta(days=k * 3))
        n += 30
        self.count("knowledge_documents", n)

    # ---------- the history of requests ----------

    async def tickets(self):
        """900 requests with the history each would have: the chat, the routing, the plan, the job and who did it.

        A request moves only as far as the staff can carry it: nobody holds more than their capacity, so one that
        would be handed to a person with no room waits in triage. Nothing is dated after now.
        """
        owners = [(c, u) for c, u in self.units.items() if c in self.residents]
        channels: set[str] = set()
        states = [s for s, w in ISSUE_STATES for _ in range(w)]
        manager = "mock-minh"
        n = 0
        timeline: dict[uuid.UUID, list[tuple[str, datetime]]] = {}
        for k in range(self.p.history_tickets):
            code, unit = self.rng.choice(owners)
            user = self.holder(code)
            title, text_, category, priority = self.rng.choice(ISSUES)
            status = self.rng.choice(states)
            created = self.now - timedelta(days=self.rng.randint(0, 180), hours=self.rng.randint(0, 23))
            # How long each step took, drawn in a fixed order so a seed gives the same history.
            gaps = [timedelta(minutes=self.rng.randint(5, 300)), timedelta(minutes=self.rng.randint(30, 120)),
                    timedelta(minutes=self.rng.randint(10, 60)), timedelta(minutes=self.rng.randint(5, 90)),
                    timedelta(minutes=self.rng.randint(5, 60)), timedelta(hours=self.rng.randint(2, 24)),
                    timedelta(minutes=self.rng.randint(10, 40)), timedelta(hours=self.rng.randint(1, 8))]
            responded_gap, plan_gap, manager_gap, resident_gap, accept_gap, eta_gap, start_gap, work_gap = gaps
            amount = self.rng.choice([0, 150000, 300000, 450000])
            worker = None
            if status in ("assigned", "in_progress"):
                free = [w for w in self.workers if w["category"] == category and w["left"] > 0]
                if free:
                    worker = self.rng.choice(free)
                    worker["left"] -= 1
                else:
                    status = "triaging"          # nobody has room: it waits for someone
            elif status in ("resolved", "closed"):
                worker = self.rng.choice([w for w in self.workers if w["category"] == category])
            worked = worker is not None
            responded = created + responded_gap
            planned = responded + plan_gap
            approved = planned + manager_gap
            agreed = approved + resident_gap
            accepted = agreed + timedelta(minutes=1) + accept_gap
            started = accepted + start_gap
            eta = accepted + eta_gap if status == "assigned" else started
            completed = started + work_gap
            last = {"open": created, "cancelled": created + timedelta(minutes=20), "triaging": responded, "assigned": accepted,
                    "in_progress": started, "resolved": completed, "closed": completed + timedelta(hours=6)}[status]
            if last > self.now - timedelta(hours=1):
                # The story must end before now: it started earlier than first drawn.
                shift = last - (self.now - timedelta(hours=1))
                created, responded, planned, approved, agreed, accepted, started, completed = (
                    t - shift for t in (created, responded, planned, approved, agreed, accepted, started, completed))
                eta = accepted + eta_gap if status == "assigned" else started
            done = status in ("resolved", "closed")
            left, arrived = accepted + (started - accepted) / 3, accepted + (started - accepted) * 2 / 3    # set off, got there
            channel = f"mock-chat-{user}-{k}"
            if channel not in channels:
                channels.add(channel)
                await self.c.execute("insert into channels(id,tenant_id,name,description,kind,created_by) values($1,$2,'Hội thoại mẫu','Dữ liệu mẫu','reception',$3) on conflict(id) do nothing", channel, TENANT, user)
                await self.c.execute("insert into channel_memberships(tenant_id,channel_id,user_id) values($1,$2,$3) on conflict do nothing", TENANT, channel, user)
            tid = uid("ticket", k)
            await self.c.execute("""insert into tickets(id,tenant_id,code,requester_user_id,channel_id,unit_id,site_id,zone_id,building_id,management_unit_id,domain_id,category_id,
                title,description,priority,status,contact_name,contact_phone,address_snapshot,request_kind,created_at,first_response_at,resolved_at,closed_at)
                values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,'{}','incident',$19,$20,$21,$22) on conflict(id) do nothing""",
                                 tid, TENANT, f"MOCK-{k + 1:04d}", user, channel, unit["id"], SITE, unit["zone"], self.building_id[unit["building"]], MANAGEMENT, DOMAIN, category,
                                 title, text_, priority, status, self.users[user], "0900000000", created, responded if status not in ("open", "cancelled") else None,
                                 completed if done else None, completed + timedelta(hours=6) if status == "closed" else None)
            n += 1
            wo, plan, assignment = uid("workorder", k), uid("plan", k), uid("assignment", k)
            # What happened, in order. The status each step moves from is worked out from the steps before it.
            steps: list[tuple[datetime, str, str | None, str | None, dict]] = [
                (created, "ticket.created", user, "open", {"source": "resident_chat", "requiresPlan": True})]
            if status == "cancelled":
                steps.append((created + timedelta(minutes=20), "ticket.status_changed", user, "cancelled", {"reason": "Cư dân hủy yêu cầu"}))
            elif status != "open":
                steps.append((responded, "ticket.routing_accepted", manager, None, {"routingId": str(uid("routing", k))}))
                steps.append((responded + timedelta(minutes=1), "ticket.status_changed", manager, "triaging", {"reason": "Đã tiếp nhận"}))
            if worked:
                crew = worker["user"]
                steps += [(planned, "plan.proposed", manager, None, {"planId": str(plan)}),
                          (approved, "plan.management_decided", manager, None, {"planId": str(plan), "decision": "approve"}),
                          (agreed, "plan.resident_decided", user, None, {"planId": str(plan), "decision": "approve"}),
                          (agreed + timedelta(minutes=1), "work_order.offered", manager, None, {"assignmentId": str(assignment), "offeredBy": "management"}),
                          (accepted, "work_assignment.responded", crew, None, {"assignmentId": str(assignment), "status": "accepted"}),
                          (accepted + timedelta(seconds=1), "ticket.status_changed", crew, "assigned", {"reason": "Nhân viên đã nhận việc"})]
                if status in ("in_progress", "resolved", "closed"):
                    steps += [(left, "work_order.status_changed", crew, None, {"workOrderId": str(wo), "status": "en_route"}),
                              (arrived, "work_order.status_changed", crew, None, {"workOrderId": str(wo), "status": "arrived"}),
                              (started, "work_order.status_changed", crew, None, {"workOrderId": str(wo), "status": "in_progress"}),
                              (started + timedelta(seconds=1), "ticket.status_changed", crew, "in_progress", {"reason": "Bắt đầu xử lý"})]
                if done:
                    steps += [(completed, "work_order.status_changed", crew, None, {"workOrderId": str(wo), "status": "completed"}),
                              (completed + timedelta(seconds=1), "ticket.status_changed", crew, "resolved", {"reason": "Đã xử lý xong"})]
                if status == "closed":
                    steps.append((completed + timedelta(hours=6), "ticket.status_changed", manager, "closed", {"reason": "Cư dân đã xác nhận"}))
            steps.sort(key=lambda step: step[0])
            current = None
            rows, shown = [], []
            for seq, (at, kind, actor, moves_to, payload) in enumerate(steps, 1):
                rows.append((uid("event", k, seq), TENANT, tid, seq, kind, current, moves_to, "human", actor, f"mock:{k}:{seq}", uid("correlation", k, seq),
                             json.dumps(payload), at))
                current = moves_to or current
                shown.append((kind, at))
            await self.c.executemany("""insert into ticket_events(id,tenant_id,ticket_id,seq,event_type,from_status,to_status,actor_kind,actor_user_id,idempotency_key,correlation_id,payload,occurred_at)
                values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,cast($12 as jsonb),$13) on conflict do nothing""", rows)
            await self.c.execute("update tickets set last_event_seq=$2,version=$2 where id=$1", tid, len(rows))
            self.count("ticket events", len(rows))
            timeline[tid] = shown
            if status != "cancelled":
                routed = status != "open"
                await self.c.execute("""insert into ticket_routing_history(id,tenant_id,ticket_id,to_management_id,status,reason,ack_event_id,requested_at,acknowledged_at)
                    values($1,$2,$3,$4,$5,'initial_reception_handoff',$6,$7,$8) on conflict(id) do nothing""",
                                     uid("routing", k), TENANT, tid, MANAGEMENT, "accepted" if routed else "requested",
                                     uid("event", k, 2) if routed else None, created, responded if routed else None)
            if worked:
                await self.c.execute("""insert into vh_ticket_plans(id,tenant_id,ticket_id,proposed_by,title,steps,estimated_amount,status,version,idempotency_key,request_hash,
                    management_by,management_note,management_at,resident_by,resident_note,resident_at,created_at,updated_at)
                    values($1,$2,$3,$4,$5,cast($6 as jsonb),$7,'approved',2,$8,$9,$4,'Đồng ý phương án.',$10,$11,'Đồng ý',$12,$13,$12) on conflict(id) do nothing""",
                                     plan, TENANT, tid, manager, f"Xử lý: {title}", json.dumps([{"category_id": str(category), "description": title, "work_order_id": str(wo)}]),
                                     amount, f"mock-plan-{k}", uuid.uuid5(NS, f"plan-hash|{k}").hex, approved, user, agreed, planned)
                await self.c.execute("""insert into work_orders(id,tenant_id,ticket_id,category_id,description,status,required_specialty_id,scheduled_at,arrived_at,started_at,completed_at,created_at)
                    values($1,$2,$3,$4,$5,$6,$4,$7,$8,$9,$10,$11) on conflict(id) do nothing""",
                                     wo, TENANT, tid, category, title,
                                     {"assigned": "accepted", "in_progress": "in_progress", "resolved": "completed", "closed": "completed"}[status], eta,
                                     arrived if status != "assigned" else None, started if status != "assigned" else None, completed if done else None, agreed)
                await self.c.execute("""insert into work_assignments(id,tenant_id,work_order_id,staff_id,assigned_by_user_id,status,offered_at,accepted_at,eta_at,ended_at,offer_expires_at,created_at)
                    values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$7) on conflict(id) do nothing""",
                                     assignment, TENANT, wo, worker["id"], manager, "completed" if done else "accepted", agreed + timedelta(minutes=1), accepted, eta,
                                     completed if done else None, agreed + timedelta(days=1))
                self.count("work orders")
            # The chat the request came from: what the resident wrote and the receipt Reception gave.
            first = uid("message", k, 1)
            await self.c.executemany("""insert into messages(id,tenant_id,channel_id,seq,sender_kind,sender_user_id,sender_client_id,visibility,body,client_message_id,reply_to_id,created_at)
                values($1,$2,$3,$4,$5,$6,$7,'customer',cast($8 as jsonb),$9,$10,$11) on conflict do nothing""",
                                     [(first, TENANT, channel, 1, "user", user, None, json.dumps({"text": text_}), f"mock-{k}-1", None, created),
                                      (uid("message", k, 2), TENANT, channel, 2, "agent", None, "demo-reception",
                                       json.dumps({"text": "Em đã ghi nhận và chuyển yêu cầu của anh/chị tới Ban quản lý. Em sẽ báo khi có phương án xử lý."}), None, first,
                                       created + timedelta(seconds=20))])
            await self.c.execute("update channels set next_message_seq=3,last_message=$2,last_message_at=$3 where id=$1 and tenant_id=$4 and next_message_seq<3",
                                 channel, "Em đã ghi nhận và chuyển yêu cầu của anh/chị tới Ban quản lý.", created + timedelta(seconds=20), TENANT)
            self.count("messages", 2)
        self.count("tickets", n)
        # The resident app follows a request through its case; the history gets the cases the app would have made,
        # with the public lines the app writes as the request moves (once: a second run adds nothing).
        from .resident_cases import PUBLIC_LABELS
        cases = 0
        for tid, shown in timeline.items():
            case = await self.c.fetchval("select app_ensure_case($1)", tid)
            if case is None:
                continue
            cases += 1
            if await self.c.fetchval("select exists(select 1 from vh_resident_public_events where case_id=$1 and label=any($2))", case, list(PUBLIC_LABELS.values())):
                continue
            for kind, at in shown:
                if kind in PUBLIC_LABELS:
                    await self.c.execute("select app_case_event($1,$2,$3,'resident.case.progress',$4)", TENANT, case, PUBLIC_LABELS[kind], at)
        self.count("resident cases", cases)

async def build(url: str, profile: str = "standard", seed: int = 42) -> dict[str, int]:
    if profile not in PROFILES:
        raise SystemExit(f"Unknown profile {profile}; choose {', '.join(PROFILES)}")
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg:", "postgresql:", 1))
    try:
        if not await conn.fetchval("select 1 from tenants where id=$1", TENANT):
            raise SystemExit("Run `database seed` first: the world is built on the base sample.")
        async with conn.transaction():
            await conn.execute("select set_config('app.tenant_id',$1,true)", str(TENANT))
            world = World(conn, PROFILES[profile], seed)
            for step in (world.places, world.people, world.staff, world.statements, world.cards, world.visitors, world.amenities,
                         world.renovation, world.desk, world.knowledge, world.tickets):
                await step()
            return world.counts
    finally:
        await conn.close()
