"""Only the four requested capabilities, reading existing business endpoints."""

from pydantic import TypeAdapter

from . import contracts as c

MODELS = {
    "filter_report_scope": c.FilterInput,
    "get_repair_bill_summary": c.SummaryInput,
    "get_ticket_frequency_summary": c.SummaryInput,
    "get_employee_star_summary": c.RatingInput,
}
OUTPUTS = {
    "filter_report_scope": c.FilterResult,
    "get_repair_bill_summary": c.BillResult,
    "get_ticket_frequency_summary": c.TicketResult,
    "get_employee_star_summary": c.RatingResult,
}
DESCRIPTIONS = {
    "filter_report_scope": "Chọn chính xác tòa hoặc toàn phân khu được phép; tên trùng yêu cầu chọn ID.",
    "get_repair_bill_summary": "Đọc đủ các trang hóa đơn issued, kiểm dòng sửa chữa rồi cộng grand_total theo tiền tệ.",
    "get_ticket_frequency_summary": "Đọc ticket và summary từng tòa; tổng ticket và tần suất từng loại incident.",
    "get_employee_star_summary": "Đọc feedback của nhân viên được chọn; lọc ngày gửi UTC và tính phân bố 1–5 sao.",
}


def tool_descriptors():
    return [
        {
            "ref": "reporting/" + name.replace("_", "-"),
            "name": name,
            "version": "2.0.0",
            "displayName": name,
            "description": DESCRIPTIONS[name],
            "category": "reporting",
            "source": "first-party",
            "visibility": "builder",
            "allowedAgentTypes": ["report"],
            "requiredPermissions": ["reports:read"],
            "effect": "read",
            "destructive": False,
            "timeoutMs": 60000,
            "retry": {"maxRetries": 0, "backoffMs": 0},
            "requiresIdempotencyKey": False,
            "execution": {"kind": "first-party", "handler": "reporting." + name},
            "inputSchema": model.model_json_schema(),
            "outputSchema": TypeAdapter(OUTPUTS[name] | c.Failure).json_schema(),
        }
        for name, model in MODELS.items()
    ]
