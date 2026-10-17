"""Real local browser/HTTP roundtrip, scripted model only, with owned Docker fixture.

python tests/vin_platform_browser_roundtrip.py --output <runner artifact directory>
Never points at an arbitrary deployment. No HTTP response is mocked.
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.sync_api import sync_playwright, expect

from vin_platform_local_fixture import PASSWORD, SECRET

PLATFORM = "http://127.0.0.1:18104"
DOMAIN = "http://127.0.0.1:18101"
STAFF = "http://127.0.0.1:18105"


def call(client, method, path, *, status=200, **kwargs):
    response = client.request(method, path, timeout=30, **kwargs)
    if response.status_code != status:
        raise AssertionError(f"{method} {path}: {response.status_code} {response.text[:1500]}")
    return response.json() if response.content else None


def login_platform(identity):
    client = httpx.Client(base_url=PLATFORM + "/api", trust_env=False)
    token = call(client, "POST", "/auth/login", json={"tenant_id": "default", "identity": identity, "password": PASSWORD})
    client.headers["Authorization"] = "Bearer " + token["access_token"]
    return client


def main(output):
    from run_vin_platform_docker_e2e import wait_ready
    wait_ready(DOMAIN + "/ready")
    wait_ready(PLATFORM + "/api/health")
    state = json.loads((output / "state.json").read_text(encoding="utf-8"))
    if not state["prefix"].startswith("vin-n1-r04-e2e-"):
        raise RuntimeError("Owned disposable Docker fixture required")
    evidence = {"status": "RUNNING", "steps": [], "paid_model_calls": 0, "http_mocking": False}
    def step(name, **data):
        evidence["steps"].append({"name": name, **data})
        (output / "roundtrip.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        print(name, flush=True)
    admin = login_platform("fixtureadmin")
    model_policy = {"daily_tokens": 200000, "monthly_tokens": 1000000, "max_output_tokens": 512,
        "max_concurrency": 2, "models": ["scripted-vin"], "enabled": True}
    call(admin, "PUT", "/admin/vin/quota-policies/role:VIN_USER", json=model_policy)
    existing = call(admin, "GET", "/admin/vin/catalog?kind=credential")["items"]
    version = max([item["version"] for item in existing if item["resource_id"] == "vin-platform-openai"] + [0]) + 1
    catalog = call(admin, "POST", "/admin/vin/catalog", status=201, json={"kind": "credential",
        "resource_id": "vin-platform-openai", "owner_id": state["platform_seed"]["admin"],
        "name": "Local scripted provider", "version": version, "model_names": ["scripted-vin"]})
    call(admin, "POST", "/admin/vin/grants", status=201, json={"catalog_id": catalog["id"],
        "subject_kind": "role", "subject_id": "VIN_USER", "permissions": ["view", "bind", "execute"]})
    secret = call(admin, "POST", "/admin/vin/secrets", status=201, json={"purpose": "domain-client", "value": SECRET})
    call(admin, "PUT", "/admin/vin/domain-providers/vinhomes", json={"id": "vinhomes", "issuer": DOMAIN,
        "client_id": "local-e2e", "authorization_url": DOMAIN + "/platform/link/authorize",
        "token_url": DOMAIN + "/platform/link/token", "api_base_url": DOMAIN + "/platform/customer",
        "redirect_uri": PLATFORM + "/connections/callback/vinhomes", "client_secret_ref": secret["secret_ref"], "active": True})
    identity = "resident" + uuid4().hex[:8]
    external = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 1000}, reduced_motion="reduce")
        def local_only(route):
            from urllib.parse import urlsplit
            if urlsplit(route.request.url).hostname not in {"127.0.0.1", "localhost"}:
                external.append(route.request.url)
                route.abort()
            else:
                route.continue_()
        context.route("**/*", local_only)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(PLATFORM + "/register")
            page.locator("#email").fill(identity + "@fixture.invalid")
            page.locator("#username").fill(identity)
            page.locator("#password").fill(PASSWORD)
            with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/auth/register-personal")) as registered:
                page.locator("button[type=submit]").click()
            assert registered.value.status == 201
            user = registered.value.json()
            call(admin, "PUT", f'/admin/vin/accounts/{user["id"]}/eligibility', json={"eligible": True})
            customer = login_platform(identity)
            step("register_platform", user_id=user["id"], role=user["role"])
            page.goto(PLATFORM + "/connections")
            page.get_by_role("button", name="Liên kết Vinhomes", exact=True).click()
            page.wait_for_url(DOMAIN + "/platform/link/authorize**", wait_until="domcontentloaded")
            expect(page.get_by_role("heading", name="Đăng nhập Vinhomes để liên kết")).to_be_visible(timeout=15000)
            page.locator('[name="identifier"]').fill(state["domain_users"]["local-v3-resident"])
            page.locator('[name="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            expect(page.get_by_role("heading", name="Liên kết tài khoản Vinhomes")).to_be_visible()
            page.screenshot(path=str(output / "domain-consent.png"), full_page=True)
            with page.expect_response(lambda response: response.request.method == "POST" and "/platform/link/authorize" in response.url) as consent:
                page.get_by_role("button", name="Đồng ý", exact=True).click()
            assert consent.value.status == 303, str(consent.value.status) + consent.value.text()
            page.get_by_role("button", name="Hoàn tất liên kết", exact=True).click()
            expect(page.get_by_text("Đã liên kết", exact=True)).to_be_visible()
            step("domain_password_and_real_consent")
            page.goto(PLATFORM + "/workforce/leader")
            page.wait_for_timeout(1000)
            (output / "leader-before.txt").write_text(page.locator("body").inner_text(), encoding="utf-8")
            page.locator("textarea").last.fill("Vòi nước bếp rò rỉ, tôi yêu cầu gửi nhân viên kỹ thuật kiểm tra. Vị trí dưới bồn rửa bếp.")
            page.locator("textarea").last.press("Enter")
            cases = []
            for _ in range(60):
                cases = call(customer, "GET", "/service-cases")["items"]
                if cases:
                    detail = call(customer, "GET", f'/service-cases/{cases[0]["id"]}?refresh=true')
                    if detail["data"]["domain"].get("tickets"):
                        break
                page.wait_for_timeout(1000)
            else:
                raise AssertionError("Leader did not create and materialize a case through scripted CustomerService")
            case_id = cases[0]["id"]
            ticket_id = detail["data"]["domain"]["tickets"][0]["id"]
            step("leader_creates_case", case_id=case_id, ticket_id=ticket_id)
            page.screenshot(path=str(output / "leader-created.png"), full_page=True)
            def domain_login(actor):
                client = httpx.Client(base_url=DOMAIN, trust_env=False)
                call(client, "POST", "/auth/login", json={"identifier": state["domain_users"]["local-v3-" + actor], "password": PASSWORD})
                return client
            manager = domain_login("admin")
            technical = domain_login("technical")
            ticket = call(manager, "GET", f"/tickets/{ticket_id}")["ticket"]
            category = ticket["category_id"]
            order = call(manager, "POST", f"/tickets/{ticket_id}/work-orders", status=201, json={"category_id": category,
                "required_specialty_id": category, "description": "Kiểm tra và xử lý vòi nước", "ticket_version": ticket["version"]})
            catalog = call(manager, "GET", "/catalogs")
            person = next(item for item in catalog["staff"] if item["user_id"] == "local-v3-technical")
            assignment = call(manager, "POST", f'/work-orders/{order["id"]}/assignments', status=201,
                json={"staff_id": person["id"], "work_order_version": order["version"],
                    "offer_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()})
            step("domain_dispatch", order_id=order["id"], assignment_id=assignment["id"], actor="Domain administrator/dispatcher")
            staff_context = browser.new_context(viewport={"width": 1280, "height": 1000})
            staff_context.route("**/*", local_only)
            signed = staff_context.request.post(STAFF + "/api/business/auth/login", data={
                "identifier": state["domain_users"]["local-v3-technical"], "password": PASSWORD})
            assert signed.status == 200, signed.text()
            worker = staff_context.new_page()
            worker.goto(STAFF + f'/operations/my-tasks?ticket={ticket_id}&order={order["id"]}')
            expect(worker.get_by_role("button", name="Nhận việc", exact=True)).to_be_visible(timeout=15000)
            worker.get_by_role("button", name="Nhận việc", exact=True).click()
            expect(worker.get_by_role("button", name="Nhận việc", exact=True)).to_have_count(0)
            received = next(item for item in call(technical, "GET", "/my-work-orders")["items"] if item["id"] == order["id"])
            assert received["assignment_status"] == "accepted" or received.get("status") == "accepted"
            worker.screenshot(path=str(output / "staff-accepted.png"), full_page=True)
            step("staff_accepts_in_domain_app")
            progress = call(customer, "GET", f"/service-cases/{case_id}?refresh=true")["data"]["domain"]
            assert any(item["id"] == order["id"] for item in progress["work_orders"])
            feed = call(customer, "GET", f"/service-cases/{case_id}/events")
            assert any(event["event_type"] == "resident.case.progress" for event in feed["items"])
            step("progress_returns_to_platform", sync_status=feed["sync_status"], applied_sequence=feed["applied_sequence"])
            for status in ("en_route", "arrived"):
                current = call(technical, "GET", f'/work-orders/{order["id"]}')["workOrder"]
                call(technical, "PATCH", f'/work-orders/{order["id"]}/status', json={"version": current["version"], "status": status, "note": status})
            current = call(technical, "GET", f'/work-orders/{order["id"]}')["workOrder"]
            call(technical, "POST", f'/work-orders/{order["id"]}/repair-proposal', status=201,
                json={"version": current["version"], "note": "Kiểm tra và thay gioăng vòi nước bị hỏng.", "labor_cost": 0,
                    "warranty_months": 1, "lines": [{"name": "Gioăng vòi nước", "quantity": "1", "unit": "cái", "unit_price": 0}]})

            def customer_click():
                page.reload()
                toggle = page.get_by_text("Yêu cầu dịch vụ của bạn (1)", exact=True)
                expect(toggle).to_be_visible(timeout=15000)
                toggle.click()
                page.get_by_role("button", name="Đồng ý", exact=True).first.click()
                dialog = page.get_by_role("dialog")
                expect(dialog).to_be_visible()
                if dialog.locator("textarea").count():
                    dialog.locator("textarea").fill("Tôi đã kiểm tra và đồng ý kết quả hiện hành.")
                with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/decisions")) as decided:
                    page.get_by_role("button", name="Xác nhận gửi quyết định", exact=True).click()
                assert decided.value.status == 200, str(decided.value.status) + decided.value.text()
                receipt = decided.value.json()
                exact = decided.value.request.post_data_json
                assert call(customer, "POST", f"/service-cases/{case_id}/decisions", json=exact) == receipt
                return receipt
            customer_click()
            step("resident_approves_repair_on_platform")
            current = call(technical, "GET", f'/work-orders/{order["id"]}')["workOrder"]
            call(technical, "PATCH", f'/work-orders/{order["id"]}/status', json={"version": current["version"], "status": "in_progress", "note": "Bắt đầu sửa vòi nước"})
            import struct
            import zlib
            def chunk(kind, body):
                return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
            image = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            image += chunk(b"IDAT", zlib.compress((b"\0" + b"\x55\x77\x99" * 8) * 8)) + chunk(b"IEND", b"")
            for purpose in ("before", "after"):
                file = call(technical, "POST", f"/tickets/{ticket_id}/files?filename={purpose}.png&mimeType=image/png&purpose={purpose}",
                    status=201, content=image, headers={"Content-Type": "application/octet-stream"})
                call(technical, "POST", f"/tickets/{ticket_id}/evidence", status=201, json={"file_id": file["fileId"],
                    "work_order_id": order["id"], "assignment_id": assignment["id"], "purpose": purpose})
            current = call(technical, "GET", f'/work-orders/{order["id"]}')["workOrder"]
            call(technical, "PATCH", f'/work-orders/{order["id"]}/status', json={"version": current["version"], "status": "completed", "note": "Đã thay gioăng và kiểm tra hết rò nước"})
            call(manager, "POST", f'/work-orders/{order["id"]}/qc', status=201,
                json={"outcome": "pass", "criteria": [{"name": "Vòi nước không rò", "passed": True}]})
            step("staff_evidence_completed_and_domain_qc")
            receipt = customer_click()
            worker.screenshot(path=str(output / "staff-finished.png"), full_page=True)
            final = call(customer, "GET", f"/service-cases/{case_id}?refresh=true")["data"]["domain"]
            assert final["service_status"] == "closed", final
            assert final["status"] == "completed", final
            assert all(item["status"] == "closed" for item in final["tickets"])
            assert final["resolution"]["photos"], final
            page.screenshot(path=str(output / "platform-closed.png"), full_page=True)
            step("resident_final_click_and_case_closed", service_status=final["service_status"], receipt_status=receipt.get("status"))
            model = httpx.get("http://127.0.0.1:18103/evidence", trust_env=False).json()
            assert any(item["operation"] == "create" for item in model["calls"])
            assert external == []
            usage = call(customer, "GET", "/me/usage")
            assert usage["pending_reconciliation"] == 0 and any(item["used"] > 0 for item in usage["effective_limits"])
            from run_vin_platform_docker_e2e import docker
            from uuid import UUID
            container = state["prefix"] + "-postgres"
            assert docker("inspect", "--format", '{{index .Config.Labels "vin.fixture"}}', container) == state["prefix"]
            commands = docker("exec", container, "psql", "-U", "vinfixture", "-d", "domain_e2e", "-Atc",
                "SELECT count(*) FROM platform_commands WHERE ticket_id='" + str(UUID(ticket_id)) + "'")
            assert commands == "0"
            evidence["bql_commands"] = int(commands)
            evidence["canonical_case_status"] = final["status"]
            evidence["decision_replay_matches"] = True
            evidence["model_calls"] = len(model["calls"])
            evidence["status"] = "PASS"
            step("roundtrip_complete")
            staff_context.close()
        except BaseException as exc:
            evidence["status"] = "FAIL"
            evidence["error"] = type(exc).__name__ + ": " + str(exc)[:1500]
            evidence["failure_url_path"] = page.url.split("?")[0]
            evidence["page_errors"] = errors
            page.screenshot(path=str(output / "failure.png"), full_page=True)
            (output / "failure-body.txt").write_text(page.locator("body").inner_text(), encoding="utf-8")
            step("failed")
            raise
        finally:
            evidence["external_browser_requests"] = external
            (output / "roundtrip.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
            context.close()
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output.resolve())
