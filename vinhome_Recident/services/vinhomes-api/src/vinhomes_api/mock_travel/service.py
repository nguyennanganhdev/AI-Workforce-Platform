"""Business rules for the in-memory travel booking demo."""

from __future__ import annotations

import unicodedata
from copy import deepcopy
from datetime import UTC, date, datetime
from threading import Lock

from .data import (
    BUS_BOOKINGS,
    BUS_TRIPS,
    HOTEL_BOOKINGS,
    HOTELS,
    RESTAURANT_BOOKINGS,
    RESTAURANTS,
)

_booking_lock = Lock()


def _ok(**payload: object) -> dict:
    return {"success": True, **payload}


def _error(code: str, message: str, **details: object) -> dict:
    result = {"success": False, "error": {"code": code, "message": message}}
    if details:
        result["error"]["details"] = details
    return result


def _normalize(value: str) -> str:
    value = value.strip().lower().replace("đ", "d")
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value)
        if unicodedata.category(character) != "Mn"
    )


def _parse_date(value: str, field: str) -> date | dict:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return _error("INVALID_DATE", f"{field} phải theo định dạng YYYY-MM-DD.")


def _validate_future_date(value: str, field: str) -> date | dict:
    parsed = _parse_date(value, field)
    if isinstance(parsed, dict):
        return parsed
    if parsed < date.today():
        return _error("DATE_IN_PAST", f"{field} không được nằm trong quá khứ.")
    return parsed


def _find(items: list[dict], key: str, value: str) -> dict | None:
    return next((item for item in items if item[key] == value), None)


def _new_booking_code(prefix: str, bookings: list[dict]) -> str:
    return f"{prefix}-{len(bookings) + 1:06d}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _find_idempotent(bookings: list[dict], client_reference: str) -> dict | None:
    if not client_reference:
        return None
    return next(
        (
            booking
            for booking in bookings
            if booking.get("client_reference") == client_reference
        ),
        None,
    )


def get_service_catalog() -> dict:
    """Return the values an agent can use to formulate searches."""
    return _ok(
        hotel_cities=sorted({hotel["city"] for hotel in HOTELS}),
        hotel_amenities=sorted(
            {amenity for hotel in HOTELS for amenity in hotel["amenities"]},
        ),
        bus_routes=[
            {
                "origin": trip["origin"],
                "destination": trip["destination"],
                "trip_id": trip["trip_id"],
                "departure_time": trip["departure_time"],
            }
            for trip in BUS_TRIPS
        ],
        restaurant_cities=sorted(
            {restaurant["city"] for restaurant in RESTAURANTS},
        ),
        restaurant_cuisines=sorted(
            {
                cuisine
                for restaurant in RESTAURANTS
                for cuisine in restaurant["cuisines"]
            },
        ),
        currency="VND",
    )


def _hotel_room_availability(
    hotel_id: str,
    room_type_id: str,
    check_in: date,
    check_out: date,
) -> int:
    hotel = _find(HOTELS, "hotel_id", hotel_id)
    if hotel is None:
        return 0
    room = _find(hotel["room_types"], "room_type_id", room_type_id)
    if room is None:
        return 0
    reserved = sum(
        booking["rooms"]
        for booking in HOTEL_BOOKINGS
        if booking["hotel_id"] == hotel_id
        and booking["room_type_id"] == room_type_id
        and booking["status"] == "confirmed"
        and date.fromisoformat(booking["check_in"]) < check_out
        and date.fromisoformat(booking["check_out"]) > check_in
    )
    return max(0, room["total_rooms"] - reserved)


def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    rooms: int = 1,
    max_price_per_night: int = 0,
    min_stars: int = 0,
    required_amenities: list[str] | None = None,
) -> dict:
    """Search available hotels and room types for a date range."""
    arrival = _validate_future_date(check_in, "check_in")
    departure = _parse_date(check_out, "check_out")
    if isinstance(arrival, dict):
        return arrival
    if isinstance(departure, dict):
        return departure
    if departure <= arrival:
        return _error("INVALID_DATE_RANGE", "check_out phải sau check_in.")
    if guests < 1 or rooms < 1:
        return _error("INVALID_OCCUPANCY", "guests và rooms phải lớn hơn 0.")
    if min_stars < 0 or min_stars > 5:
        return _error("INVALID_FILTER", "min_stars phải nằm trong khoảng 0 đến 5.")

    city_key = _normalize(city)
    amenities = {_normalize(value) for value in (required_amenities or [])}
    items = []
    nights = (departure - arrival).days
    for hotel in HOTELS:
        if city_key not in _normalize(hotel["city"]):
            continue
        if hotel["stars"] < min_stars:
            continue
        if not amenities.issubset({_normalize(value) for value in hotel["amenities"]}):
            continue

        room_options = []
        for room_type in hotel["room_types"]:
            available = _hotel_room_availability(
                hotel["hotel_id"],
                room_type["room_type_id"],
                arrival,
                departure,
            )
            if available < rooms or room_type["max_guests"] * rooms < guests:
                continue
            if (
                max_price_per_night
                and room_type["price_per_night"] > max_price_per_night
            ):
                continue
            room_options.append(
                {
                    **deepcopy(room_type),
                    "available_rooms": available,
                    "total_price": room_type["price_per_night"] * rooms * nights,
                },
            )
        if room_options:
            items.append(
                {
                    "hotel_id": hotel["hotel_id"],
                    "name": hotel["name"],
                    "city": hotel["city"],
                    "district": hotel["district"],
                    "address": hotel["address"],
                    "stars": hotel["stars"],
                    "rating": hotel["rating"],
                    "amenities": deepcopy(hotel["amenities"]),
                    "available_room_types": room_options,
                },
            )
    items.sort(key=lambda item: (-item["rating"], item["name"]))
    return _ok(
        query={
            "city": city,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "rooms": rooms,
        },
        currency="VND",
        count=len(items),
        items=items,
    )


def get_hotel_details(hotel_id: str) -> dict:
    """Get the full static profile and room catalog of one hotel."""
    hotel = _find(HOTELS, "hotel_id", hotel_id)
    if hotel is None:
        return _error("HOTEL_NOT_FOUND", f"Không tìm thấy khách sạn {hotel_id}.")
    return _ok(hotel=deepcopy(hotel), currency="VND")


def check_hotel_availability(
    hotel_id: str,
    room_type_id: str,
    check_in: str,
    check_out: str,
    rooms: int = 1,
) -> dict:
    """Check exact room inventory before creating a hotel booking."""
    arrival = _validate_future_date(check_in, "check_in")
    departure = _parse_date(check_out, "check_out")
    if isinstance(arrival, dict):
        return arrival
    if isinstance(departure, dict):
        return departure
    if departure <= arrival:
        return _error("INVALID_DATE_RANGE", "check_out phải sau check_in.")
    if rooms < 1:
        return _error("INVALID_ROOMS", "rooms phải lớn hơn 0.")
    hotel = _find(HOTELS, "hotel_id", hotel_id)
    if hotel is None:
        return _error("HOTEL_NOT_FOUND", f"Không tìm thấy khách sạn {hotel_id}.")
    room = _find(hotel["room_types"], "room_type_id", room_type_id)
    if room is None:
        return _error(
            "ROOM_TYPE_NOT_FOUND", f"Không tìm thấy loại phòng {room_type_id}."
        )
    available = _hotel_room_availability(hotel_id, room_type_id, arrival, departure)
    nights = (departure - arrival).days
    return _ok(
        hotel_id=hotel_id,
        hotel_name=hotel["name"],
        room_type=deepcopy(room),
        check_in=check_in,
        check_out=check_out,
        requested_rooms=rooms,
        available_rooms=available,
        is_available=available >= rooms,
        total_price=room["price_per_night"] * rooms * nights,
        currency="VND",
    )


def book_hotel(
    hotel_id: str,
    room_type_id: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    customer_name: str,
    customer_phone: str,
    customer_email: str = "",
    special_requests: str = "",
    client_reference: str = "",
) -> dict:
    """Create a confirmed mock hotel booking."""
    with _booking_lock:
        replay = _find_idempotent(HOTEL_BOOKINGS, client_reference)
        if replay:
            return _ok(booking=deepcopy(replay), idempotent_replay=True)
        if not customer_name.strip() or not customer_phone.strip():
            return _error(
                "MISSING_CUSTOMER", "customer_name và customer_phone là bắt buộc."
            )
        if guests < 1 or rooms < 1:
            return _error("INVALID_OCCUPANCY", "guests và rooms phải lớn hơn 0.")
        availability = check_hotel_availability(
            hotel_id,
            room_type_id,
            check_in,
            check_out,
            rooms,
        )
        if not availability["success"]:
            return availability
        room = availability["room_type"]
        if guests > room["max_guests"] * rooms:
            return _error(
                "CAPACITY_EXCEEDED",
                "Số khách vượt sức chứa của số phòng đã chọn.",
                max_guests=room["max_guests"] * rooms,
            )
        if not availability["is_available"]:
            return _error(
                "SOLD_OUT",
                "Không còn đủ phòng cho khoảng ngày đã chọn.",
                available_rooms=availability["available_rooms"],
            )
        hotel = _find(HOTELS, "hotel_id", hotel_id)
        booking = {
            "booking_id": _new_booking_code("HB", HOTEL_BOOKINGS),
            "booking_type": "hotel",
            "status": "confirmed",
            "hotel_id": hotel_id,
            "hotel_name": hotel["name"],
            "room_type_id": room_type_id,
            "room_type_name": room["name"],
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "rooms": rooms,
            "customer_name": customer_name.strip(),
            "customer_phone": customer_phone.strip(),
            "customer_email": customer_email.strip(),
            "special_requests": special_requests.strip(),
            "total_price": availability["total_price"],
            "currency": "VND",
            "payment_status": "pay_at_property",
            "cancellation_policy": hotel["cancellation_policy"],
            "client_reference": client_reference,
            "created_at": _now(),
        }
        HOTEL_BOOKINGS.append(booking)
        return _ok(booking=deepcopy(booking), idempotent_replay=False)


def get_hotel_booking(booking_id: str) -> dict:
    """Get a mock hotel booking by booking ID."""
    booking = _find(HOTEL_BOOKINGS, "booking_id", booking_id)
    if booking is None:
        return _error("BOOKING_NOT_FOUND", f"Không tìm thấy booking {booking_id}.")
    return _ok(booking=deepcopy(booking))


def cancel_hotel_booking(booking_id: str, reason: str = "") -> dict:
    """Cancel a hotel booking and release its room inventory."""
    with _booking_lock:
        booking = _find(HOTEL_BOOKINGS, "booking_id", booking_id)
        if booking is None:
            return _error("BOOKING_NOT_FOUND", f"Không tìm thấy booking {booking_id}.")
        if booking["status"] == "cancelled":
            return _ok(booking=deepcopy(booking), already_cancelled=True)
        booking.update(
            status="cancelled", cancellation_reason=reason, cancelled_at=_now()
        )
        return _ok(booking=deepcopy(booking), already_cancelled=False)


def _bus_available_seats(trip_id: str, travel_date: str) -> int:
    trip = _find(BUS_TRIPS, "trip_id", trip_id)
    if trip is None:
        return 0
    reserved = sum(
        booking["seats"]
        for booking in BUS_BOOKINGS
        if booking["trip_id"] == trip_id
        and booking["travel_date"] == travel_date
        and booking["status"] == "confirmed"
    )
    return max(0, trip["total_seats"] - reserved)


def search_bus_trips(
    origin: str,
    destination: str,
    travel_date: str,
    passengers: int = 1,
    max_price_per_seat: int = 0,
    seat_type: str = "",
) -> dict:
    """Search daily mock bus schedules with live in-memory seat counts."""
    parsed = _validate_future_date(travel_date, "travel_date")
    if isinstance(parsed, dict):
        return parsed
    if passengers < 1:
        return _error("INVALID_PASSENGERS", "passengers phải lớn hơn 0.")
    origin_key = _normalize(origin)
    destination_key = _normalize(destination)
    seat_key = _normalize(seat_type)
    items = []
    for trip in BUS_TRIPS:
        if origin_key not in _normalize(trip["origin"]):
            continue
        if destination_key not in _normalize(trip["destination"]):
            continue
        if max_price_per_seat and trip["price_per_seat"] > max_price_per_seat:
            continue
        if seat_key and seat_key != _normalize(trip["seat_type"]):
            continue
        available = _bus_available_seats(trip["trip_id"], travel_date)
        if available >= passengers:
            items.append(
                {
                    **deepcopy(trip),
                    "travel_date": travel_date,
                    "available_seats": available,
                    "total_price": trip["price_per_seat"] * passengers,
                },
            )
    items.sort(key=lambda item: (item["departure_time"], item["price_per_seat"]))
    return _ok(
        query={
            "origin": origin,
            "destination": destination,
            "travel_date": travel_date,
            "passengers": passengers,
        },
        currency="VND",
        count=len(items),
        items=items,
    )


def get_bus_trip_details(trip_id: str, travel_date: str = "") -> dict:
    """Get one bus schedule, optionally including inventory for a date."""
    trip = _find(BUS_TRIPS, "trip_id", trip_id)
    if trip is None:
        return _error("TRIP_NOT_FOUND", f"Không tìm thấy chuyến xe {trip_id}.")
    result = deepcopy(trip)
    if travel_date:
        parsed = _validate_future_date(travel_date, "travel_date")
        if isinstance(parsed, dict):
            return parsed
        result["travel_date"] = travel_date
        result["available_seats"] = _bus_available_seats(trip_id, travel_date)
    return _ok(trip=result, currency="VND")


def check_bus_availability(trip_id: str, travel_date: str, seats: int = 1) -> dict:
    """Check exact seat inventory before creating a bus booking."""
    parsed = _validate_future_date(travel_date, "travel_date")
    if isinstance(parsed, dict):
        return parsed
    if seats < 1:
        return _error("INVALID_SEATS", "seats phải lớn hơn 0.")
    trip = _find(BUS_TRIPS, "trip_id", trip_id)
    if trip is None:
        return _error("TRIP_NOT_FOUND", f"Không tìm thấy chuyến xe {trip_id}.")
    available = _bus_available_seats(trip_id, travel_date)
    return _ok(
        trip_id=trip_id,
        operator=trip["operator"],
        travel_date=travel_date,
        requested_seats=seats,
        available_seats=available,
        is_available=available >= seats,
        total_price=trip["price_per_seat"] * seats,
        currency="VND",
    )


def book_bus_trip(
    trip_id: str,
    travel_date: str,
    seats: int,
    customer_name: str,
    customer_phone: str,
    passenger_names: list[str] | None = None,
    pickup_point: str = "",
    dropoff_point: str = "",
    client_reference: str = "",
) -> dict:
    """Create a confirmed mock bus booking."""
    with _booking_lock:
        replay = _find_idempotent(BUS_BOOKINGS, client_reference)
        if replay:
            return _ok(booking=deepcopy(replay), idempotent_replay=True)
        if not customer_name.strip() or not customer_phone.strip():
            return _error(
                "MISSING_CUSTOMER", "customer_name và customer_phone là bắt buộc."
            )
        if seats < 1 or seats > 10:
            return _error("INVALID_SEATS", "seats phải nằm trong khoảng 1 đến 10.")
        names = passenger_names or []
        if names and len(names) != seats:
            return _error(
                "PASSENGER_MISMATCH",
                "Nếu có passenger_names thì số tên phải bằng seats.",
            )
        availability = check_bus_availability(trip_id, travel_date, seats)
        if not availability["success"]:
            return availability
        if not availability["is_available"]:
            return _error(
                "SOLD_OUT",
                "Không còn đủ ghế trên chuyến đã chọn.",
                available_seats=availability["available_seats"],
            )
        trip = _find(BUS_TRIPS, "trip_id", trip_id)
        selected_pickup = pickup_point or trip["pickup_points"][0]
        selected_dropoff = dropoff_point or trip["dropoff_points"][0]
        if selected_pickup not in trip["pickup_points"]:
            return _error("INVALID_PICKUP", "Điểm đón không thuộc chuyến xe.")
        if selected_dropoff not in trip["dropoff_points"]:
            return _error("INVALID_DROPOFF", "Điểm trả không thuộc chuyến xe.")
        booking = {
            "booking_id": _new_booking_code("BB", BUS_BOOKINGS),
            "booking_type": "bus",
            "status": "confirmed",
            "trip_id": trip_id,
            "operator": trip["operator"],
            "origin": trip["origin"],
            "destination": trip["destination"],
            "travel_date": travel_date,
            "departure_time": trip["departure_time"],
            "arrival_time": trip["arrival_time"],
            "seats": seats,
            "passenger_names": names,
            "pickup_point": selected_pickup,
            "dropoff_point": selected_dropoff,
            "customer_name": customer_name.strip(),
            "customer_phone": customer_phone.strip(),
            "total_price": availability["total_price"],
            "currency": "VND",
            "payment_status": "unpaid_demo",
            "cancellation_policy": trip["cancellation_policy"],
            "client_reference": client_reference,
            "created_at": _now(),
        }
        BUS_BOOKINGS.append(booking)
        return _ok(booking=deepcopy(booking), idempotent_replay=False)


def get_bus_booking(booking_id: str) -> dict:
    """Get a mock bus booking by booking ID."""
    booking = _find(BUS_BOOKINGS, "booking_id", booking_id)
    if booking is None:
        return _error("BOOKING_NOT_FOUND", f"Không tìm thấy booking {booking_id}.")
    return _ok(booking=deepcopy(booking))


def cancel_bus_booking(booking_id: str, reason: str = "") -> dict:
    """Cancel a bus booking and release its seat inventory."""
    with _booking_lock:
        booking = _find(BUS_BOOKINGS, "booking_id", booking_id)
        if booking is None:
            return _error("BOOKING_NOT_FOUND", f"Không tìm thấy booking {booking_id}.")
        if booking["status"] == "cancelled":
            return _ok(booking=deepcopy(booking), already_cancelled=True)
        booking.update(
            status="cancelled", cancellation_reason=reason, cancelled_at=_now()
        )
        return _ok(booking=deepcopy(booking), already_cancelled=False)


def _restaurant_available_capacity(
    restaurant_id: str,
    reservation_date: str,
    reservation_time: str,
) -> int:
    restaurant = _find(RESTAURANTS, "restaurant_id", restaurant_id)
    if restaurant is None:
        return 0
    reserved = sum(
        booking["party_size"]
        for booking in RESTAURANT_BOOKINGS
        if booking["restaurant_id"] == restaurant_id
        and booking["reservation_date"] == reservation_date
        and booking["reservation_time"] == reservation_time
        and booking["status"] == "confirmed"
    )
    return max(0, restaurant["capacity_per_slot"] - reserved)


def search_restaurants(
    city: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int = 2,
    cuisine: str = "",
    min_rating: float = 0,
    max_average_price_per_person: int = 0,
) -> dict:
    """Search restaurants with enough capacity at an exact mock time slot."""
    parsed = _validate_future_date(reservation_date, "reservation_date")
    if isinstance(parsed, dict):
        return parsed
    if party_size < 1:
        return _error("INVALID_PARTY_SIZE", "party_size phải lớn hơn 0.")
    if min_rating < 0 or min_rating > 5:
        return _error("INVALID_FILTER", "min_rating phải nằm trong khoảng 0 đến 5.")
    city_key = _normalize(city)
    cuisine_key = _normalize(cuisine)
    items = []
    for restaurant in RESTAURANTS:
        if city_key not in _normalize(restaurant["city"]):
            continue
        if reservation_time not in restaurant["opening_slots"]:
            continue
        if restaurant["rating"] < min_rating:
            continue
        if max_average_price_per_person and (
            restaurant["average_price_per_person"] > max_average_price_per_person
        ):
            continue
        if cuisine_key and not any(
            cuisine_key in _normalize(value) for value in restaurant["cuisines"]
        ):
            continue
        available = _restaurant_available_capacity(
            restaurant["restaurant_id"],
            reservation_date,
            reservation_time,
        )
        if available >= party_size:
            items.append(
                {
                    **deepcopy(restaurant),
                    "reservation_date": reservation_date,
                    "reservation_time": reservation_time,
                    "available_capacity": available,
                    "estimated_total": restaurant["average_price_per_person"]
                    * party_size,
                },
            )
    items.sort(key=lambda item: (-item["rating"], item["average_price_per_person"]))
    return _ok(
        query={
            "city": city,
            "reservation_date": reservation_date,
            "reservation_time": reservation_time,
            "party_size": party_size,
        },
        currency="VND",
        count=len(items),
        items=items,
    )


def get_restaurant_details(restaurant_id: str) -> dict:
    """Get the full static profile of one restaurant."""
    restaurant = _find(RESTAURANTS, "restaurant_id", restaurant_id)
    if restaurant is None:
        return _error(
            "RESTAURANT_NOT_FOUND",
            f"Không tìm thấy nhà hàng {restaurant_id}.",
        )
    return _ok(restaurant=deepcopy(restaurant), currency="VND")


def check_restaurant_availability(
    restaurant_id: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
) -> dict:
    """Check restaurant capacity for an exact date and time slot."""
    parsed = _validate_future_date(reservation_date, "reservation_date")
    if isinstance(parsed, dict):
        return parsed
    if party_size < 1:
        return _error("INVALID_PARTY_SIZE", "party_size phải lớn hơn 0.")
    restaurant = _find(RESTAURANTS, "restaurant_id", restaurant_id)
    if restaurant is None:
        return _error(
            "RESTAURANT_NOT_FOUND",
            f"Không tìm thấy nhà hàng {restaurant_id}.",
        )
    if reservation_time not in restaurant["opening_slots"]:
        return _error(
            "INVALID_TIME_SLOT",
            "Nhà hàng không nhận đặt bàn tại giờ này.",
            available_slots=restaurant["opening_slots"],
        )
    available = _restaurant_available_capacity(
        restaurant_id,
        reservation_date,
        reservation_time,
    )
    return _ok(
        restaurant_id=restaurant_id,
        restaurant_name=restaurant["name"],
        reservation_date=reservation_date,
        reservation_time=reservation_time,
        party_size=party_size,
        available_capacity=available,
        is_available=available >= party_size,
        estimated_total=restaurant["average_price_per_person"] * party_size,
        currency="VND",
    )


def book_restaurant(
    restaurant_id: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    customer_name: str,
    customer_phone: str,
    special_requests: str = "",
    client_reference: str = "",
) -> dict:
    """Create a confirmed mock restaurant reservation."""
    with _booking_lock:
        replay = _find_idempotent(RESTAURANT_BOOKINGS, client_reference)
        if replay:
            return _ok(booking=deepcopy(replay), idempotent_replay=True)
        if not customer_name.strip() or not customer_phone.strip():
            return _error(
                "MISSING_CUSTOMER", "customer_name và customer_phone là bắt buộc."
            )
        availability = check_restaurant_availability(
            restaurant_id,
            reservation_date,
            reservation_time,
            party_size,
        )
        if not availability["success"]:
            return availability
        if not availability["is_available"]:
            return _error(
                "SOLD_OUT",
                "Nhà hàng không còn đủ sức chứa tại khung giờ đã chọn.",
                available_capacity=availability["available_capacity"],
            )
        restaurant = _find(RESTAURANTS, "restaurant_id", restaurant_id)
        booking = {
            "booking_id": _new_booking_code("RB", RESTAURANT_BOOKINGS),
            "booking_type": "restaurant",
            "status": "confirmed",
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant["name"],
            "address": restaurant["address"],
            "reservation_date": reservation_date,
            "reservation_time": reservation_time,
            "party_size": party_size,
            "customer_name": customer_name.strip(),
            "customer_phone": customer_phone.strip(),
            "special_requests": special_requests.strip(),
            "estimated_total": availability["estimated_total"],
            "currency": "VND",
            "payment_status": "pay_at_restaurant",
            "cancellation_policy": restaurant["cancellation_policy"],
            "client_reference": client_reference,
            "created_at": _now(),
        }
        RESTAURANT_BOOKINGS.append(booking)
        return _ok(booking=deepcopy(booking), idempotent_replay=False)


def get_restaurant_booking(booking_id: str) -> dict:
    """Get a mock restaurant reservation by booking ID."""
    booking = _find(RESTAURANT_BOOKINGS, "booking_id", booking_id)
    if booking is None:
        return _error("BOOKING_NOT_FOUND", f"Không tìm thấy booking {booking_id}.")
    return _ok(booking=deepcopy(booking))


def cancel_restaurant_booking(booking_id: str, reason: str = "") -> dict:
    """Cancel a restaurant reservation and release its capacity."""
    with _booking_lock:
        booking = _find(RESTAURANT_BOOKINGS, "booking_id", booking_id)
        if booking is None:
            return _error("BOOKING_NOT_FOUND", f"Không tìm thấy booking {booking_id}.")
        if booking["status"] == "cancelled":
            return _ok(booking=deepcopy(booking), already_cancelled=True)
        booking.update(
            status="cancelled", cancellation_reason=reason, cancelled_at=_now()
        )
        return _ok(booking=deepcopy(booking), already_cancelled=False)


def list_customer_bookings(
    customer_phone: str,
    booking_type: str = "all",
    include_cancelled: bool = True,
) -> dict:
    """List bookings across all three services for one customer phone."""
    allowed_types = {"all", "hotel", "bus", "restaurant"}
    if booking_type not in allowed_types:
        return _error(
            "INVALID_BOOKING_TYPE",
            "booking_type phải là all, hotel, bus hoặc restaurant.",
        )
    phone_key = _normalize(customer_phone).replace(" ", "")
    sources = {
        "hotel": HOTEL_BOOKINGS,
        "bus": BUS_BOOKINGS,
        "restaurant": RESTAURANT_BOOKINGS,
    }
    items = []
    for current_type, bookings in sources.items():
        if booking_type not in {"all", current_type}:
            continue
        items.extend(
            deepcopy(booking)
            for booking in bookings
            if _normalize(booking["customer_phone"]).replace(" ", "") == phone_key
            and (include_cancelled or booking["status"] != "cancelled")
        )
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return _ok(customer_phone=customer_phone, count=len(items), items=items)
