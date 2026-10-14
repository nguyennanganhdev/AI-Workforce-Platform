"""DEMO-ONLY MCP server for Workforce evaluation and live demos.

Every record is fictional and labelled ``"demo": true``. Nothing here contacts
a real provider, takes a payment or books anything. Two domains are served so
the same platform can be shown working outside travel:

* travel: hotels, cars and a deterministic trip-cost calculator;
* resident services (building management): incident triage, technician
  availability, service fees, cleaning schedule and work orders.

Run (streamable HTTP, default http://127.0.0.1:8765/mcp)::

    python scripts/workforce/demo_mcp_server.py --port 8765

Then register the URL on the platform's MCP page and build agents from its
tools with Agent Builder. ``scripts/workforce/eval`` scenarios assume these
exact records.
"""

from __future__ import annotations

import argparse
import itertools
import unicodedata

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

server = FastMCP("DEMO Workforce services")
READ_ONLY = ToolAnnotations(readOnlyHint=True)
WRITES = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold()).replace("đ", "d")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip()


# ---------------------------------------------------------------------------
# Travel
# ---------------------------------------------------------------------------

HOTELS = [
    {
        "hotel_id": "DN-01",
        "city": "Đà Nẵng",
        "name": "DEMO Sông Hàn Riverside",
        "area": "Hải Châu",
        "stars": 4,
        "rating": 8.7,
        "price_per_night_vnd": 1_200_000,
        "rooms_available": 3,
        "max_guests_per_room": 2,
        "amenities": ["hồ bơi", "bữa sáng", "wifi"],
        "check_in_time": "14:00",
    },
    {
        "hotel_id": "DN-02",
        "city": "Đà Nẵng",
        "name": "DEMO Mỹ Khê Beach Stay",
        "area": "Sơn Trà",
        "stars": 3,
        "rating": 8.1,
        "price_per_night_vnd": 750_000,
        "rooms_available": 5,
        "max_guests_per_room": 2,
        "amenities": ["gần biển", "wifi"],
        "check_in_time": "13:00",
    },
    {
        "hotel_id": "DN-03",
        "city": "Đà Nẵng",
        "name": "DEMO Ngũ Hành Sơn Resort",
        "area": "Ngũ Hành Sơn",
        "stars": 5,
        "rating": 9.2,
        "price_per_night_vnd": 2_600_000,
        "rooms_available": 1,
        "max_guests_per_room": 3,
        "amenities": ["hồ bơi", "spa", "bữa sáng", "đưa đón sân bay"],
        "check_in_time": "15:00",
    },
    {
        "hotel_id": "NT-01",
        "city": "Nha Trang",
        "name": "DEMO Trần Phú Ocean",
        "area": "Lộc Thọ",
        "stars": 4,
        "rating": 8.4,
        "price_per_night_vnd": 1_050_000,
        "rooms_available": 4,
        "max_guests_per_room": 2,
        "amenities": ["hồ bơi", "bữa sáng"],
        "check_in_time": "14:00",
    },
    {
        "hotel_id": "DL-01",
        "city": "Đà Lạt",
        "name": "DEMO Đồi Thông Lodge",
        "area": "Phường 3",
        "stars": 3,
        "rating": 8.9,
        "price_per_night_vnd": 900_000,
        "rooms_available": 0,
        "max_guests_per_room": 4,
        "amenities": ["lò sưởi", "bữa sáng"],
        "check_in_time": "14:00",
    },
]

CARS = [
    {
        "car_id": "CAR-DN-4",
        "route": "Sân bay Đà Nẵng → trung tâm Đà Nẵng",
        "from": "Sân bay Đà Nẵng",
        "to": "Đà Nẵng",
        "seats": 4,
        "price_vnd": 250_000,
        "pickup_window": "theo giờ hạ cánh",
    },
    {
        "car_id": "CAR-DN-7",
        "route": "Sân bay Đà Nẵng → trung tâm Đà Nẵng",
        "from": "Sân bay Đà Nẵng",
        "to": "Đà Nẵng",
        "seats": 7,
        "price_vnd": 380_000,
        "pickup_window": "theo giờ hạ cánh",
    },
    {
        "car_id": "CAR-DN-HA-7",
        "route": "Đà Nẵng → Hội An (khứ hồi trong ngày)",
        "from": "Đà Nẵng",
        "to": "Hội An",
        "seats": 7,
        "price_vnd": 900_000,
        "pickup_window": "08:00–20:00",
    },
    {
        "car_id": "CAR-NT-4",
        "route": "Sân bay Cam Ranh → trung tâm Nha Trang",
        "from": "Sân bay Cam Ranh",
        "to": "Nha Trang",
        "seats": 4,
        "price_vnd": 420_000,
        "pickup_window": "theo giờ hạ cánh",
    },
]

_booking_ids = itertools.count(1)
BOOKINGS: dict[str, dict] = {}


@server.tool(annotations=READ_ONLY)
def search_hotels(
    city: str,
    guests: int,
    nights: int,
    max_price_per_night_vnd: int | None = None,
) -> dict:
    """Search DEMO hotels in a city for a party size and number of nights.

    Leave ``max_price_per_night_vnd`` empty unless the customer explicitly set
    a nightly cap. Returns only rooms that are available.
    """
    wanted = _fold(city)
    results = []
    for hotel in HOTELS:
        if _fold(hotel["city"]) != wanted or hotel["rooms_available"] <= 0:
            continue
        if max_price_per_night_vnd and hotel["price_per_night_vnd"] > max_price_per_night_vnd:
            continue
        rooms_needed = -(-max(1, guests) // hotel["max_guests_per_room"])
        if rooms_needed > hotel["rooms_available"]:
            continue
        results.append(
            {
                **hotel,
                "demo": True,
                "rooms_needed": rooms_needed,
                "total_price_vnd": hotel["price_per_night_vnd"] * rooms_needed * nights,
            }
        )
    return {"demo": True, "city": city, "nights": nights, "guests": guests, "hotels": results}


@server.tool(annotations=READ_ONLY)
def get_hotel_detail(hotel_id: str) -> dict:
    """Return the full DEMO record of one hotel by its hotel_id."""
    for hotel in HOTELS:
        if hotel["hotel_id"] == hotel_id:
            return {"demo": True, **hotel}
    return {"demo": True, "error": "hotel_not_found", "hotel_id": hotel_id}


@server.tool(annotations=READ_ONLY)
def search_cars(origin: str, destination: str, passengers: int) -> dict:
    """Search DEMO car transfers between two places for a passenger count."""
    origin_f, destination_f = _fold(origin), _fold(destination)
    results = [
        {**car, "demo": True}
        for car in CARS
        if origin_f in _fold(car["from"])
        and destination_f in _fold(car["to"])
        and car["seats"] >= passengers
    ]
    return {"demo": True, "cars": results}


@server.tool(annotations=READ_ONLY)
def calculate_trip_cost(
    items: list[dict],
    budget_vnd: int,
    reserve_vnd: int = 0,
) -> dict:
    """Add priced items (each ``{"label": str, "amount_vnd": int}``) and check
    them against a total budget minus a required reserve."""
    total = sum(int(item.get("amount_vnd", 0)) for item in items)
    ceiling = budget_vnd - reserve_vnd
    return {
        "demo": True,
        "items": items,
        "total_vnd": total,
        "budget_vnd": budget_vnd,
        "reserve_vnd": reserve_vnd,
        "spend_ceiling_vnd": ceiling,
        "within_ceiling": total <= ceiling,
        "remaining_from_budget_vnd": budget_vnd - total,
        "margin_against_ceiling_vnd": ceiling - total,
    }


@server.tool(annotations=WRITES)
def book_hotel(hotel_id: str, nights: int, guests: int, customer_name: str) -> dict:
    """Create a DEMO hotel booking (writes demo state; needs customer consent)."""
    hotel = next((h for h in HOTELS if h["hotel_id"] == hotel_id), None)
    if hotel is None:
        return {"demo": True, "status": "failed", "reason": "hotel_not_found"}
    if hotel["rooms_available"] <= 0:
        return {"demo": True, "status": "failed", "reason": "no_availability"}
    hotel["rooms_available"] -= 1
    booking_id = f"DEMO-BK-{next(_booking_ids):04d}"
    BOOKINGS[booking_id] = {
        "hotel_id": hotel_id,
        "nights": nights,
        "guests": guests,
        "customer_name": customer_name,
    }
    return {
        "demo": True,
        "status": "confirmed",
        "booking_id": booking_id,
        "amount_vnd": hotel["price_per_night_vnd"] * nights,
    }


# ---------------------------------------------------------------------------
# Resident services (building management)
# ---------------------------------------------------------------------------

INCIDENT_TYPES = [
    {
        "code": "PLB-LEAK",
        "keywords": ["ro ri", "ri nuoc", "vo ong", "ong nuoc", "nuoc tran", "leak"],
        "category": "plumbing",
        "label": "Rò rỉ / vỡ ống nước",
        "priority": "khẩn cấp",
        "sla_hours": 2,
        "skill": "plumber",
        "first_aid": "Khoá van tổng nước của căn hộ, ngắt điện khu vực bị nước.",
    },
    {
        "code": "ELC-OUT",
        "keywords": ["mat dien", "chap dien", "aptomat", "cau dao", "power"],
        "category": "electric",
        "label": "Mất điện / chập điện trong căn hộ",
        "priority": "cao",
        "sla_hours": 4,
        "skill": "electrician",
        "first_aid": "Ngắt cầu dao tổng, không chạm vào thiết bị ướt.",
    },
    {
        "code": "AC-NOCOOL",
        "keywords": ["dieu hoa", "may lanh", "khong mat", "air"],
        "category": "hvac",
        "label": "Điều hoà không làm mát",
        "priority": "thường",
        "sla_hours": 24,
        "skill": "hvac",
        "first_aid": "Tắt điều hoà, vệ sinh lưới lọc nếu có thể.",
    },
    {
        "code": "CLN-SPILL",
        "keywords": ["rac", "ban", "do vo", "nuoc dong hanh lang", "ve sinh"],
        "category": "cleaning",
        "label": "Vệ sinh khu vực chung / xử lý rác, nước đọng",
        "priority": "thường",
        "sla_hours": 6,
        "skill": "cleaner",
        "first_aid": "Đặt biển cảnh báo trơn trượt nếu có nước.",
    },
]

TECHNICIANS = {
    "plumber": [
        {"name": "DEMO Thợ nước Trần An", "slots": ["09:00", "13:30", "16:00"]},
        {"name": "DEMO Thợ nước Lê Bình", "slots": ["10:30"]},
    ],
    "electrician": [{"name": "DEMO Thợ điện Phạm Cường", "slots": ["08:30", "14:00"]}],
    "hvac": [{"name": "DEMO Kỹ thuật lạnh Võ Dũng", "slots": ["15:00"]}],
    "cleaner": [{"name": "DEMO Tổ vệ sinh ca sáng", "slots": ["07:00", "11:00"]}],
}

SERVICE_FEES = {
    "PLB-LEAK": {"inspection_vnd": 0, "labour_per_hour_vnd": 150_000, "note": "Miễn phí kiểm tra trong 2 giờ đầu nếu lỗi thuộc hệ thống chung."},
    "ELC-OUT": {"inspection_vnd": 100_000, "labour_per_hour_vnd": 180_000, "note": "Vật tư tính riêng theo hoá đơn."},
    "AC-NOCOOL": {"inspection_vnd": 150_000, "labour_per_hour_vnd": 200_000, "note": "Nạp gas tính riêng."},
    "CLN-SPILL": {"inspection_vnd": 0, "labour_per_hour_vnd": 0, "note": "Khu vực chung: miễn phí."},
}

CLEANING_SCHEDULE = {
    "S1": ["06:30 hành lang tầng 1–10", "14:00 sảnh và thang máy", "20:00 thu gom rác"],
    "S2": ["07:00 hành lang tầng 1–12", "15:00 sảnh", "20:30 thu gom rác"],
}

_work_order_ids = itertools.count(1)
WORK_ORDERS: dict[str, dict] = {}


@server.tool(annotations=READ_ONLY)
def lookup_incident_type(description: str) -> dict:
    """Classify a resident's reported issue into a DEMO incident type with
    priority, SLA (hours), required technician skill and first-aid advice."""
    folded = _fold(description)
    for incident in INCIDENT_TYPES:
        if any(keyword in folded for keyword in incident["keywords"]):
            return {"demo": True, **{k: v for k, v in incident.items() if k != "keywords"}}
    return {"demo": True, "code": "UNKNOWN", "label": "Chưa phân loại được", "priority": "cần BQL xem xét"}


@server.tool(annotations=READ_ONLY)
def check_technician_availability(skill: str, date: str) -> dict:
    """List DEMO technicians with free slots for a skill (plumber, electrician,
    hvac, cleaner) on a date (YYYY-MM-DD)."""
    return {"demo": True, "skill": skill, "date": date, "technicians": TECHNICIANS.get(skill, [])}


@server.tool(annotations=READ_ONLY)
def get_service_fee(incident_code: str) -> dict:
    """Return the DEMO fee policy for an incident code."""
    fee = SERVICE_FEES.get(incident_code)
    if fee is None:
        return {"demo": True, "error": "fee_not_found", "incident_code": incident_code}
    return {"demo": True, "incident_code": incident_code, **fee}


@server.tool(annotations=READ_ONLY)
def get_cleaning_schedule(building: str) -> dict:
    """Return the DEMO daily cleaning schedule of a building (S1 or S2)."""
    key = building.strip().upper()
    return {"demo": True, "building": key, "schedule": CLEANING_SCHEDULE.get(key, [])}


@server.tool(annotations=WRITES)
def create_work_order(
    apartment: str,
    incident_code: str,
    description: str,
    technician: str,
    slot: str,
) -> dict:
    """Create a DEMO work order (writes demo state; needs resident consent)."""
    order_id = f"DEMO-WO-{next(_work_order_ids):04d}"
    WORK_ORDERS[order_id] = {
        "apartment": apartment,
        "incident_code": incident_code,
        "description": description,
        "technician": technician,
        "slot": slot,
    }
    return {"demo": True, "status": "created", "work_order_id": order_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server.settings.host = args.host
    server.settings.port = args.port
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
