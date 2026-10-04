"""Schema catalog for runtime registration; schemas do not grant permissions."""

from . import contracts as c

MODELS = {
    "get_report_filter_options": c.FilterInput,
    "get_employee_performance_summary": c.EmployeeInput,
    "get_employee_feedback_details": c.FeedbackInput,
    "get_repair_revenue_summary": c.RevenueInput,
    "get_incident_frequency_summary": c.FrequencyInput,
    "get_report_supporting_records": c.SupportingInput,
    "create_report_export": c.ExportInput,
    "get_report_export_status": c.ExportStatusInput,
}

DESCRIPTIONS = {
    "get_report_filter_options": "Lấy tòa, nhóm dịch vụ và nhân viên được backend cho phép.",
    "get_employee_performance_summary": "Hiệu suất theo kỳ phân công; đúng hạn, xử lý, rework và đánh giá.",
    "get_employee_feedback_details": "Phản hồi một nhân viên trong tòa; phân trang, API chưa lọc kỳ.",
    "get_repair_revenue_summary": "Tính phí, thực thu và còn phải thu theo tiền tệ; không cộng khác tiền tệ.",
    "get_incident_frequency_summary": "Đếm ticket incident theo ngày/tuần/tháng; loại service_request.",
    "get_report_supporting_records": "Bản ghi theo kỳ của loại được chọn; không phải toàn bộ nguồn của KPI.",
    "create_report_export": "Xuất DOCX tần suất toàn tòa hoặc hóa đơn issued. Giữ nguyên key khi thử lại.",
    "get_report_export_status": "Đọc trạng thái export; backend kiểm tra người tạo và quyền hiện tại.",
}


def tool_descriptors():
    return [
        {
            "ref": "reporting/" + name.replace("_", "-"),
            "name": name,
            "version": "1.0.1",
            "displayName": name,
            "description": DESCRIPTIONS[name],
            "category": "reporting",
            "source": "first-party",
            "visibility": "builder",
            "allowedAgentTypes": ["report"],
            "requiredPermissions": [
                "reports:write" if name == "create_report_export" else "reports:read"
            ],
            "effect": "write" if name == "create_report_export" else "read",
            "destructive": False,
            "timeoutMs": 60000,
            # Retries for GET are bounded inside the client. No outer retries.
            "retry": {"maxRetries": 0, "backoffMs": 0},
            "requiresIdempotencyKey": name == "create_report_export",
            "execution": {"kind": "first-party", "handler": "reporting." + name},
            "inputSchema": model.model_json_schema(),
            "outputSchema": {
                "type": "object",
                "required": ["outcome"],
                "properties": {
                    "outcome": {"enum": ["success", "partial", "empty", "failure"]}
                },
            },
        }
        for name, model in MODELS.items()
    ]
