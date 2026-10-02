"""Semantic DOCX layout and local HTML preview; no renderer or storage default."""

from html import escape

OPERATIONS_LAYOUT = {
    "version": "1.0.0",
    "page": {"size": "A4", "margin_mm": 20},
    "sections": ["title", "period", "summary", "metrics", "limitations", "sources"],
    "metric_table": {
        "columns": ["Chỉ số", "Kết quả", "Nguồn"],
        "widths_percent": [35, 35, 30],
        "repeat_header": True,
    },
    "typography": {"font": "Arial", "body_pt": 11, "title_pt": 20},
    "footer": "Nguồn dữ liệu được kiểm tra quyền qua backend khi xuất và tải báo cáo.",
}


def render_report_preview(document):
    e = escape
    columns = "".join(
        f'<th scope="col">{e(c)}</th>'
        for c in OPERATIONS_LAYOUT["metric_table"]["columns"]
    )
    rows = "".join(
        f'<tr><th scope="row">{e(row["metric"])}</th><td>{e(row["value"])}</td><td>{e(", ".join(row["source_ids"]) or "—")}</td></tr>'
        for row in document["rows"]
    )
    limitations = "".join(f"<li>{e(line)}</li>" for line in document["limitations"])
    sources = "".join(
        f"<li>{e(s['source_id'])} · {e(s['metric_id'])}@{e(s['metric_version'])} · snapshot {e(s['snapshot_id'])} · reference {e(s['reference_id'])}</li>"
        for s in document["sources"]
    )
    period = document["period"]
    return f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{e(document["title"])}</title><style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#182230;line-height:1.6}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd3db;padding:10px;text-align:left}}th{{background:#eef2f6}}caption{{text-align:left;font-weight:bold}}footer{{margin-top:24px;color:#526171}}@media print{{body{{margin:0}}thead{{display:table-header-group}}}}</style></head><body><main><h1>{e(document["title"])}</h1><p>Kỳ [{e(period["from"])}, {e(period["to"])}), múi giờ {e(period["timezone"])}.</p><p>Snapshot as_of: {e(document["as_of"])}</p><p>{e(document["summary"])}</p><table><caption>Chỉ số vận hành</caption><thead><tr>{columns}</tr></thead><tbody>{rows}</tbody></table><h2>Giới hạn dữ liệu</h2><ul>{limitations}</ul><h2>Nguồn</h2><ul>{sources}</ul></main><footer>{e(OPERATIONS_LAYOUT["footer"])}</footer></body></html>'
