import pytest
from fastapi.testclient import TestClient
import sys
import os
from datetime import datetime, timezone

# Đưa thư mục src vào PATH để import module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from main import app

def get_valid_v2_payload():
    return {
        "schema_version": "2.0",
        "message_id": "MSG-001",
        "correlation_id": "CORR-001",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "message_type": "ticket_submitted",
        "message": "Cư dân báo rò rỉ nước ở khu vực bếp",
        "tenant_id": "TENANT-01",
        "domain_id": "DOMAIN-01",
        "domain_name": "Vinhomes",
        "workspace_id": "WS-01",
        "team_id": "TEAM-01",
        "ticket_id": "TK-123",
        "ticket_code": "TK2026-001",
        "ticket_generation": 1,
        "ticket_version": "v1",
        "resident": {
            "resident_id": "RES-001",
            "resident_name": "Nguyen Van A",
            "phone_number": "0987654321"
        },
        "location": {
            "location_scope_id": "LOC-01",
            "unit_id": "U-01",
            "unit_number": "12A05",
            "building_id": "BLD-01",
            "building_code": "T1",
            "building_name": "Tòa T1"
        },
        "request": {
            "title": "Rò nước",
            "description": "Nước rò rỉ dưới bồn rửa",
            "request_kind": "incident",
            "priority": "high",
            "severity": "moderate",
            "is_emergency": False,
            "handoff_reason": "needs_staff"
        },
        "facts": [
            {
                "key": "vi_tri",
                "value": "bếp",
                "source": "customer_report",
                "source_message_id": "MSG-ORIG-01"
            }
        ],
        "file_ids": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }


# =========================================================================
# TEST 1: Health Check
# =========================================================================
def test_health_check():
    with TestClient(app) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "error"]


# =========================================================================
# TEST 2: Ticket Flow (V2 Schema)
# =========================================================================
def test_ticket_flow_mock_v2():
    """
    Kiểm tra luồng E2E với payload V2 chuẩn xác.
    """
    payload = get_valid_v2_payload()

    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/tickets", json=payload)

    # Vẫn phải trả 202 Accepted
    assert response.status_code == 202, f"Mong đợi 202, nhận: {response.status_code} - {response.text}"
    data = response.json()
    
    assert data["schema_version"] == "2.0"
    assert data["ticket_id"] == "TK-123"
    assert data["status"] == "accepted"


# =========================================================================
# TEST 3: Từ chối payload V1 (hoặc thiếu trường V2)
# =========================================================================
def test_ticket_rejects_v1_payload():
    """
    Chứng minh rằng API trở thành "cửa ải" bất khả xâm phạm.
    Từ chối payload V1 cũ.
    """
    v1_payload = {
        "version": 1,
        "ticket_id": "TK-BAD",
        "report": {
            "text": "Trần căn hộ bị rò nước",
            "facts": {},
            "attachments": []
        }
    }

    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/tickets", json=v1_payload)

    # Schema V2 sẽ văng lỗi vì không có 'version' mà là 'schema_version'
    assert response.status_code == 422


# =========================================================================
# TEST 4: Bắt chặt enum của message_type
# =========================================================================
def test_ticket_rejects_invalid_message_type():
    """
    Từ chối các message_type không hợp lệ (không nằm trong enum cho phép).
    """
    payload = get_valid_v2_payload()
    payload["message_type"] = "fake_message_type"

    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/tickets", json=payload)

    assert response.status_code == 422
