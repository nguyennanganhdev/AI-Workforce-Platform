# -*- coding: utf-8 -*-
"""Turn an OpenAPI spec into tools, and call the API behind them.

Many partners have a REST API and no MCP. An import keeps one
:class:`OpenAPIOperation` per selected operation; the app then serves them
as an HTTP MCP (see ``_router/_openapi.py``), so sync, Agent Builder and
agent runs need nothing new. No code from the partner runs here: a tool
call becomes one HTTP request built from the operation.

Every URL the app fetches or calls on a user's behalf must resolve to a
public address, so an import cannot reach the app's own network
(``OPENAPI_ALLOW_PRIVATE=true`` lifts this for a trusted host).
"""
import asyncio
import ipaddress
import json
import os
import re
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx
import yaml

from ..storage._model._mcp import OpenAPIBridge, OpenAPIOperation

MAX_OPERATIONS = 100
_MAX_SPEC_BYTES = 5 * 1024 * 1024
_MAX_RESPONSE_BYTES = 512 * 1024
_MAX_RESULT_CHARS = 100_000
_MAX_SCHEMA_CHARS = 20_000
_METHODS = ("get", "post", "put", "patch", "delete")
_NAME = re.compile(r"[^A-Za-z0-9_-]+")


class OpenAPIError(ValueError):
    """A spec, URL or call the bridge cannot use, worded for the user."""


# ── addresses ────────────────────────────────────────────────────────


def _private_allowed() -> bool:
    return os.getenv("OPENAPI_ALLOW_PRIVATE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


async def ensure_public_url(url: str) -> None:
    """Refuse a URL that is not http(s) or resolves to a non-public IP."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise OpenAPIError(f"URL không hợp lệ: {url!r}. Cần http(s)://…")
    if _private_allowed():
        return
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname,
            parts.port or (443 if parts.scheme == "https" else 80),
        )
    except OSError as exc:
        raise OpenAPIError(f"Không phân giải được tên miền {parts.hostname}.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise OpenAPIError(
                f"{parts.hostname} trỏ vào địa chỉ nội bộ ({address}); "
                "platform chỉ gọi API công khai.",
            )


async def _get(url: str, limit: int) -> tuple[int, str]:
    """GET a public URL, checking every redirect hop and capping the body."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        for _ in range(4):
            await ensure_public_url(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect and "location" in response.headers:
                    url = urljoin(url, response.headers["location"])
                    continue
                raw = b""
                async for chunk in response.aiter_bytes():
                    raw += chunk
                    if len(raw) > limit:
                        raise OpenAPIError("Tệp spec quá lớn (tối đa 5 MB).")
                return response.status_code, raw.decode(
                    response.encoding or "utf-8",
                    errors="replace",
                )
    raise OpenAPIError("Spec chuyển hướng quá nhiều lần.")


# ── spec ─────────────────────────────────────────────────────────────


def load_spec_text(text: str) -> dict:
    """Parse a JSON or YAML spec."""
    try:
        spec = json.loads(text)
    except ValueError:
        try:
            spec = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise OpenAPIError("Spec không phải JSON hoặc YAML hợp lệ.") from exc
    if not isinstance(spec, dict):
        raise OpenAPIError("Spec không phải JSON hoặc YAML hợp lệ.")
    return spec


async def fetch_spec(url: str) -> dict:
    """Download and parse a spec from a public URL."""
    status, text = await _get(url, _MAX_SPEC_BYTES)
    if status >= 400:
        raise OpenAPIError(f"Không tải được spec (HTTP {status}).")
    return load_spec_text(text)


def _resolve(spec: dict, node: Any, depth: int = 0, seen: tuple = ()) -> Any:
    """Inline local ``$ref``s; a cycle or deep nesting becomes an object."""
    if isinstance(node, list):
        return [_resolve(spec, item, depth, seen) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        if not ref.startswith("#/") or ref in seen or depth > 8:
            return {"type": "object"}
        target: Any = spec
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            target = target.get(part) if isinstance(target, dict) else None
        if not isinstance(target, dict):
            return {"type": "object"}
        return _resolve(spec, target, depth + 1, (*seen, ref))
    return {
        key: _resolve(spec, value, depth + 1, seen)
        for key, value in node.items()
        if key not in ("example", "examples", "xml")
    }


def _bounded(schema: dict, note: str) -> dict:
    """Keep a tool schema small enough for a model's context."""
    if len(json.dumps(schema, ensure_ascii=False)) <= _MAX_SCHEMA_CHARS:
        return schema
    return {"type": "object", "description": note}


def _base_urls(spec: dict, spec_url: str | None) -> list[str]:
    urls: list[str] = []
    if "swagger" in spec:
        host = spec.get("host") or (urlsplit(spec_url).netloc if spec_url else "")
        if host:
            scheme = (spec.get("schemes") or ["https"])[0]
            urls.append(f"{scheme}://{host}{spec.get('basePath') or ''}")
    for server in spec.get("servers") or []:
        url = str((server or {}).get("url") or "")
        for name, var in ((server or {}).get("variables") or {}).items():
            url = url.replace("{" + name + "}", str((var or {}).get("default", "")))
        if url and spec_url:
            url = urljoin(spec_url, url)
        if url.startswith(("http://", "https://")):
            urls.append(url.rstrip("/"))
    return list(dict.fromkeys(urls))


def _tool_name(raw: str, taken: set[str]) -> str:
    base = re.sub(r"_+", "_", _NAME.sub("_", raw)).strip("_")[:60] or "call"
    name, index = base, 2
    while name in taken:
        name = f"{base[:56]}_{index}"
        index += 1
    taken.add(name)
    return name


def parse_spec(spec: dict, spec_url: str | None = None) -> dict:
    """Read a spec into ``{title, base_urls, operations, skipped}``.

    ``operations`` are :class:`OpenAPIOperation` objects; ``skipped``
    names operations whose body the bridge cannot send (e.g. multipart).
    """
    if not (str(spec.get("openapi", "")).startswith("3") or spec.get("swagger") == "2.0"):
        raise OpenAPIError("Chỉ hỗ trợ OpenAPI 3.x và Swagger 2.0.")
    swagger = "swagger" in spec
    info = spec.get("info") or {}
    operations: list[OpenAPIOperation] = []
    skipped: list[str] = []
    taken: set[str] = set()

    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        shared = item.get("parameters") or []
        for method in _METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            label = f"{method.upper()} {path}"
            params = [_resolve(spec, p) for p in [*shared, *(op.get("parameters") or [])]]
            properties: dict[str, Any] = {}
            required: list[str] = []
            placed: list[dict] = []
            body = "none"
            form: dict[str, Any] = {}

            for param in params:
                where, name = param.get("in"), str(param.get("name") or "")
                if not name:
                    continue
                schema = param.get("schema") or {
                    k: param[k] for k in ("type", "format", "enum", "items") if k in param
                } or {"type": "string"}
                if where == "body":
                    body = "json"
                    properties["body"] = _bounded(schema, "JSON body")
                    if param.get("required"):
                        required.append("body")
                    continue
                if where == "formData":
                    form[name] = schema
                    continue
                if where not in ("path", "query", "header"):
                    continue
                arg = name if name not in properties else f"{where}_{name}"
                properties[arg] = {**schema, "description": str(param.get("description") or "")[:300]}
                if param.get("required") or where == "path":
                    required.append(arg)
                placed.append({"name": name, "in": where, "arg": arg})

            if form:
                body = "form"
                properties["body"] = {"type": "object", "properties": form}

            request = _resolve(spec, op.get("requestBody")) if not swagger else None
            if isinstance(request, dict):
                content = request.get("content") or {}
                kind = next((k for k in content if k == "application/json" or k.endswith("+json")), None)
                if kind is not None:
                    body = "json"
                    properties["body"] = _bounded(content[kind].get("schema") or {"type": "object"}, "JSON body")
                elif "application/x-www-form-urlencoded" in content:
                    body = "form"
                    properties["body"] = _bounded(
                        content["application/x-www-form-urlencoded"].get("schema") or {"type": "object"},
                        "Form fields",
                    )
                elif content:
                    skipped.append(f"{label} (body {', '.join(content)})")
                    continue
                if body != "none" and request.get("required"):
                    required.append("body")

            text = ". ".join(
                part.strip()
                for part in (str(op.get("summary") or ""), str(op.get("description") or ""))
                if part and part.strip()
            )
            operations.append(
                OpenAPIOperation(
                    name=_tool_name(str(op.get("operationId") or f"{method}_{path}"), taken),
                    method=method.upper(),
                    path=path,
                    description=f"{label}. {text}"[:1024] if text else label,
                    params=placed,
                    body=body,
                    input_schema={
                        "type": "object",
                        "properties": properties,
                        **({"required": list(dict.fromkeys(required))} if required else {}),
                    },
                ),
            )

    return {
        "title": str(info.get("title") or ""),
        "description": str(info.get("description") or "")[:500],
        "base_urls": _base_urls(spec, spec_url),
        "operations": operations,
        "skipped": skipped,
    }


def tool_snapshot(operation: OpenAPIOperation) -> dict:
    """The secret-free catalog entry sync would capture for ``operation``."""
    return {
        "name": operation.name,
        "description": operation.description,
        "input_schema": operation.input_schema,
    }


# ── calls ────────────────────────────────────────────────────────────


async def call_operation(
    bridge: OpenAPIBridge,
    operation: OpenAPIOperation,
    args: dict,
) -> tuple[str, bool]:
    """Send one request for ``operation``; return ``(text, is_error)``."""
    path = operation.path
    query: dict[str, Any] = {}
    headers: dict[str, str] = {}
    for param in operation.params:
        value = args.get(param["arg"])
        if value is None:
            if param["in"] == "path":
                return f"Thiếu tham số bắt buộc: {param['arg']}", True
            continue
        if param["in"] == "path":
            path = path.replace("{" + param["name"] + "}", quote(str(value), safe=""))
        elif param["in"] == "query":
            query[param["name"]] = value
        else:
            headers[param["name"]] = str(value)

    if bridge.auth_value:
        if bridge.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {bridge.auth_value}"
        elif bridge.auth_type == "header" and bridge.auth_name:
            headers[bridge.auth_name] = bridge.auth_value
        elif bridge.auth_type == "query" and bridge.auth_name:
            query[bridge.auth_name] = bridge.auth_value

    url = bridge.base_url.rstrip("/") + path
    try:
        await ensure_public_url(url)
    except OpenAPIError as exc:
        return str(exc), True

    body = args.get("body")
    request: dict[str, Any] = {"params": query, "headers": headers}
    if operation.body == "json" and body is not None:
        request["json"] = body
    elif operation.body == "form" and isinstance(body, dict):
        request["data"] = body

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            async with client.stream(operation.method, url, **request) as response:
                raw = b""
                async for chunk in response.aiter_bytes():
                    raw += chunk
                    if len(raw) > _MAX_RESPONSE_BYTES:
                        break
    except httpx.TimeoutException:
        return "API không phản hồi trong 30 giây.", True
    except httpx.HTTPError as exc:
        return f"Không gọi được API: {type(exc).__name__}", True

    text = raw[:_MAX_RESPONSE_BYTES].decode(response.encoding or "utf-8", errors="replace")
    if len(text) > _MAX_RESULT_CHARS:
        text = text[:_MAX_RESULT_CHARS] + "\n…(đã cắt bớt)"
    return f"HTTP {response.status_code}\n{text}", response.status_code >= 400
