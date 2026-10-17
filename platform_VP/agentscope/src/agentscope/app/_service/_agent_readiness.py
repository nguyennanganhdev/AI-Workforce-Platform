"""Side-effect-free publication/resource readiness shared by console and chat."""
from datetime import datetime, timezone
from fastapi import HTTPException
from ..storage import AgentRecord


def publication_issue(agent: AgentRecord) -> str | None:
    data = agent.data
    if data.system_role == "leader":
        return None
    # Unstructured legacy agents retain their existing API contract. Studio
    # and Builder agents always carry a spec and must have a publication.
    if data.spec and (data.lifecycle_state != "published" or data.published_version < 1):
        return f"{data.name}: chưa có phiên bản đã phát hành sẵn sàng."
    return None


async def resource_manifest(storage, user_id, agent, access=None):
    spec = agent.data.spec or {}
    issues = [issue] if (issue := publication_issue(agent)) else []
    knowledge, tools, skills = [], [], []
    authority_requires_resolver = access is None and getattr(storage, "vin_platform_service", None) is not None
    visible_kbs = {kb.id: kb for kb in await storage.list_knowledge_bases(user_id)} if access is None and not authority_requires_resolver else {}
    if authority_requires_resolver:
        issues.append("Chưa xác minh được quyền tài nguyên; hãy thử lại sau.")
    for item in spec.get("knowledge", []):
        kb_id = item["kb_id"]
        kb = visible_kbs.get(kb_id)
        if access is not None:
            try:
                kb = await access.resolve_knowledge_base(user_id, kb_id)
            except HTTPException as exc:
                if exc.status_code not in (403, 404):
                    raise
                kb = None
        # Shared records retain their service owner. Never read documents from
        # a resident namespace simply because that resident selected the KB.
        docs = await storage.list_knowledge_documents(kb.user_id, kb_id) if kb else []
        today = datetime.now(timezone.utc).date().isoformat()
        ready = sum(doc.status == "ready" and doc.data.review_status == "approved"
                    and (not doc.data.effective_from or doc.data.effective_from <= today)
                    and (not doc.data.effective_until or doc.data.effective_until >= today) for doc in docs)
        knowledge.append({"id": kb_id, "name": item.get("name", ""), "available": kb is not None,
                          "documents": len(docs), "ready_documents": ready})
        if kb is None or not ready:
            issues.append(f"Knowledge {item.get('name') or kb_id}: chưa có tài liệu sẵn sàng hoặc mất quyền.")
    for item in spec.get("tools", []):
        mcp = await storage.get_mcp(user_id, item.get("mcp_id", ""))
        descriptor = next((t for t in mcp.discovered_tools if t.get("name") == item.get("tool_name")), None) if mcp else None
        available = bool(mcp and mcp.enabled and descriptor)
        tools.append({"id": item.get("tool_id"), "name": item.get("tool_name"), "available": available,
                      "read_only": bool(descriptor and descriptor.get("read_only") is True)})
        if not available:
            issues.append(f"Tool {item.get('tool_name')}: connector hoặc công cụ không còn khả dụng.")
    for item in spec.get("skills", []):
        skill = await storage.get_skill(user_id, item["skill_id"])
        available = bool(skill and skill.enabled and getattr(skill, "review_status", "approved") == "approved")
        skills.append({"id": item["skill_id"], "name": item.get("name"), "available": available,
                       "version": getattr(skill, "version", None), "checksum": getattr(skill, "archive_sha256", None)})
        if not available:
            issues.append(f"Skill {item.get('name') or item['skill_id']}: chưa duyệt hoặc không còn khả dụng.")
    return {"agent_id": agent.id, "version": agent.data.published_version,
            "lifecycle_state": agent.data.lifecycle_state, "ready": not issues, "issues": issues,
            "knowledge": knowledge, "tools": tools, "skills": skills,
            "prepared_resources": bool(agent.data.resource_workspace_id)}
