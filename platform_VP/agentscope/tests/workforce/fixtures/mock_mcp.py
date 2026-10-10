"""TEST ONLY MCP Hotel/Car/Technical server. Run with Python over stdio."""

from mcp.server.fastmcp import FastMCP

server = FastMCP("FAKE Workforce providers")
inventory = {"hotel": 2, "car": 2}
transactions = {}


@server.tool()
def hotel_search(location: str) -> dict:
    """Return explicitly fictional inventory and integer VND prices."""
    return {
        "fixture": True,
        "location": location,
        "rooms": inventory["hotel"],
        "price_minor": 5000000,
        "currency": "VND",
        "amenities": ["FAKE pool", "FAKE wifi"],
    }


def book(kind, idempotency_key, fault):
    key = (kind, idempotency_key)
    if key in transactions:
        return transactions[key]
    if fault == "network":
        raise RuntimeError("FAKE network failure")
    if inventory[kind] <= 0:
        return {"fixture": True, "status": "no_availability"}
    inventory[kind] -= 1
    result = {
        "fixture": True,
        "status": "confirmed",
        "external_transaction_id": f"FAKE-{kind}-{len(transactions) + 1}",
    }
    transactions[key] = result
    if fault == "after_write":
        raise RuntimeError("FAKE lost response after provider write")
    return result


@server.tool()
def hotel_book(room: str, idempotency_key: str, fault: str = "none") -> dict:
    """Book fictional finite inventory, with optional failure after writing."""
    return book("hotel", idempotency_key, fault)


@server.tool()
def car_book(route: str, idempotency_key: str, fault: str = "none") -> dict:
    """Book a fictional car; no real provider or payment is contacted."""
    return book("car", idempotency_key, fault)


@server.tool()
def technical_create(client_reference: str, idempotency_key: str) -> dict:
    """Create a fictional pending job correlated before the tool call."""
    key = ("technical", idempotency_key)
    if key not in transactions:
        transactions[key] = {
            "fixture": True,
            "status": "pending",
            "external_job_id": f"FAKE-job-{len(transactions) + 1}",
            "client_reference": client_reference,
        }
    return transactions[key]


if __name__ == "__main__":
    server.run(transport="stdio")
