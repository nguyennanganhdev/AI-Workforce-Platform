"""Bounded travel inputs; customer identity is supplied by the ticket, never by an MCP caller."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["hotel", "bus", "restaurant"]


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_max_length=1000)


class HotelSelection(Inputs):
    hotel_id: str = Field(min_length=1, max_length=120)
    room_type_id: str = Field(min_length=1, max_length=120)
    check_in: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    check_out: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    guests: int = Field(default=1, ge=1, le=100)
    rooms: int = Field(default=1, ge=1, le=30)
    special_requests: str = ""


class BusSelection(Inputs):
    trip_id: str = Field(min_length=1, max_length=120)
    travel_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    seats: int = Field(default=1, ge=1, le=10)
    pickup_point: str = ""
    dropoff_point: str = ""


class RestaurantSelection(Inputs):
    restaurant_id: str = Field(min_length=1, max_length=120)
    reservation_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reservation_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    party_size: int = Field(default=2, ge=1, le=100)
    special_requests: str = ""


class HotelSearch(Inputs):
    city: str = Field(min_length=1, max_length=200)
    check_in: str
    check_out: str
    guests: int = Field(default=1, ge=1, le=100)
    rooms: int = Field(default=1, ge=1, le=30)
    max_price_per_night: int = Field(default=0, ge=0)
    min_stars: int = Field(default=0, ge=0, le=5)
    required_amenities: list[str] | None = Field(default=None, max_length=20)


class BusSearch(Inputs):
    origin: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    travel_date: str
    passengers: int = Field(default=1, ge=1, le=10)
    max_price_per_seat: int = Field(default=0, ge=0)
    seat_type: str = ""


class RestaurantSearch(Inputs):
    city: str = Field(min_length=1, max_length=200)
    reservation_date: str
    reservation_time: str
    party_size: int = Field(default=2, ge=1, le=100)
    cuisine: str = ""
    min_rating: float = Field(default=0, ge=0, le=10)
    max_average_price_per_person: int = Field(default=0, ge=0)


class CancelSelection(Inputs):
    booking_ref: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1)


SELECTION = {
    "hotel": HotelSelection,
    "bus": BusSelection,
    "restaurant": RestaurantSelection,
}
SEARCH = {"hotel": HotelSearch, "bus": BusSearch, "restaurant": RestaurantSearch}
