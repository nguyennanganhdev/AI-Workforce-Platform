import pytest
from fastapi.testclient import TestClient
import sys
import os

# Đưa thư mục src vào PATH để import module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from main import app

# Khởi tạo TestClient sẽ được thực hiện trong thân hàm để kích hoạt startup event

def test_ticket_flow_mock():
    """
    Kiểm tra luồng E2E giả lập:
    Lễ tân gửi Ticket vào -> Điều phối xử lý (Mock) -> Trả kết quả về
    """
    # 1. Chuẩn bị payload đúng chuẩn Contract (Giao việc và file ownership.md)
    payload = {
        "version": 1,
        "ticket_id": "TK-123",
        "report": {
            "text": "Trần căn hộ bị rò nước gần ổ điện",
            "facts": {
                "mo_ta": "Rò nước gần ổ điện",
                "vi_tri": "Trong căn hộ"
            },
            "attachments": [
                {"file_id": "F-001", "type": "image"}
            ]
        }
    }

    # 2. Bắn Request HTTP POST giả lập (Dùng with block để kích hoạt startup_event)
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/tickets", json=payload)
    
    # 3. Kiểm tra HTTP Status
    assert response.status_code == 200, f"Lỗi HTTP, mã trả về: {response.status_code}"
    
    data = response.json()
    
    # 4. Kiểm tra Schema Contract chốt với DEV-3 (Lễ tân chiều ra)
    assert data["version"] == 1
    assert data["ticket_id"] == "TK-123"
    assert "status" in data
    assert data["status"] in ["need_info", "in_progress", "waiting_approval", "resolved"]
    
    assert "resident_brief" in data
    assert "facts" in data["resident_brief"]
    assert isinstance(data["resident_brief"]["facts"], list)

    print("\n[SUCCESS] Luồng Ticket (Mock) hoạt động chính xác! Contract được tuân thủ nghiêm ngặt.")
