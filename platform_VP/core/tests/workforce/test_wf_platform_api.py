"""The admin surface of the platform core (/platform/v1, /credential): profiles, models, cost, metrics and the cases
of the admin's tenant. Only an admin key opens it; a partner has its own API (P4)."""
from __future__ import annotations

import scripts
from conftest import ADM, ADM_B, OLD_SVC, publish
from enginekit import world

P = "/platform/v1"


def test_profile_lifecycle_and_models(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        http = w.env.http
        body = {"key": "extra", "name": "Extra", "mission": "does extra work."}
        created = http.post(f"{P}/profiles", headers=ADM, json=body).json()
        assert created["status"] == "draft" and created["version"] == 1
        r = http.post(f"{P}/profiles/extra/versions/1/publish", headers=ADM)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED"  # the gate; its own tests: test_wf_b2_release
        publish(w.env, "extra")
        listed = http.get(f"{P}/profiles?status=published", headers=ADM).json()["profiles"]
        assert "extra" in {p["key"] for p in listed}
        assert "extra" not in {p["key"] for p in http.get(f"{P}/profiles?status=published", headers=ADM_B).json()["profiles"]}
        models = http.get(f"{P}/models", headers=ADM).json()["models"]
        assert {m["id"] for m in models} == {"strong", "cheap"} and all(m["priced"] for m in models)
        assert http.post(f"{P}/profiles/extra/retire", headers=ADM).json() == {"retired": "extra"}
        assert http.get(f"{P}/jev", headers=ADM).json()["enabled"] is False


def test_only_an_admin_key_opens_the_platform_api(env):
    for path in (f"{P}/profiles", f"{P}/models", f"{P}/cases", f"{P}/metrics", f"{P}/cost"):
        assert env.http.get(path).status_code == 401, path
        assert env.http.get(path, headers=OLD_SVC).status_code == 401, path  # a connector key: the platform has none
        assert env.http.get(path, headers=ADM).status_code == 200, path
    assert env.http.get(f"{P}/health").json() == {"status": "ok"}


def test_credentials_are_masked_for_the_admin(env):
    cred = env.http.post("/credential/", headers=ADM, json={"data": {
        "type": "openai_credential", "api_key": "sk-supersecretvalue1234", "name": "mine"}})
    assert cred.status_code < 300
    listed = env.http.get("/credential/", headers=ADM)
    assert "sk-supersecretvalue1234" not in listed.text and "1234" in listed.text
    assert env.http.get("/agent/", headers=OLD_SVC).status_code == 401  # the agent API is for the admin only


def test_the_cases_of_a_tenant_are_read_by_that_tenants_admin_only(tmp_path):
    with world(tmp_path, scripts.interactive) as w:
        _, r = w.flow.begin()
        http = w.env.http
        case_id = w.sql("select case_id from wf_workflows where id=?", (r["workflow_id"],))[0][0]
        listed = http.get(f"{P}/cases", headers=ADM).json()["cases"]
        assert [c["id"] for c in listed] == [case_id] and listed[0]["status"] == "open"
        assert http.get(f"{P}/cases?status=closed", headers=ADM).json() == {"cases": []}
        got = http.get(f"{P}/cases/{case_id}", headers=ADM).json()
        assert got["id"] == case_id and got["cost"]["calls"] >= 1
        items = http.get(f"{P}/cases/{case_id}/items", headers=ADM).json()["items"]
        assert items and items[0]["kind"] == "evidence" and items[0]["author"] == "resident"  # what the resident said
        assert http.get(f"{P}/cases/{case_id}/cost", headers=ADM).json()["totals"]["cost_usd"] > 0
        models = http.get(f"{P}/cost", headers=ADM).json()["models"]
        assert {m["model"] for m in models} == {"fake-strong"}
        # the other tenant's admin sees nothing of it
        assert http.get(f"{P}/cases", headers=ADM_B).json() == {"cases": []}
        for tail in ("", "/items", "/cost"):
            assert http.get(f"{P}/cases/{case_id}{tail}", headers=ADM_B).status_code == 404, tail
        assert http.get(f"{P}/cost", headers=ADM_B).json()["models"] == []
        metrics = http.get(f"{P}/metrics", headers=ADM).json()
        assert metrics["model_calls"] >= 1 and metrics["tool_schema_saving"] is not None
