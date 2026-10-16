"""The connector API of the old design is gone (decision D1, phase P4): nothing of it answers, is stored or is read.

These tests fail if a piece of it comes back: the endpoints, the tables, the settings, the modules, the tools
and any source line that still names them."""
from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

import pytest
from conftest import ADM, OLD_SVC

import awp
from awp.app import build_app
from awp.casefile.store import PREFIX
from awp.config import Settings
from awp.protocol.tools import CASE_TOOLS

SRC = Path(awp.__file__).parent


def test_the_old_endpoints_do_not_exist(env):
    for headers in (ADM, OLD_SVC, {}):
        assert env.http.post("/platform/v1/intake", json={"message_id": "m", "external_ref": "x", "summary": "s"},
                             headers=headers).status_code in (401, 404, 405)
    assert env.http.post("/platform/v1/intake", json={}, headers=ADM).status_code == 404
    assert env.http.post("/platform/v1/cases/by-ref/x/messages", json={"message_id": "m"}, headers=ADM).status_code == 404
    assert env.http.post("/workforce/v1/partner/requests", json={}).status_code == 401  # the partner API is what is left


def test_the_old_tables_and_column_are_not_created(env):
    con = env.raw()
    tables, columns = con.tables(), con.columns("awp_cases")
    con.close()
    assert "awp_outbox" not in tables and "awp_inbound" not in tables
    assert {"awp_cases", "awp_case_items", "wf_workflows", "wf_requests"} <= tables
    assert "meta" in columns and "intake" not in columns


def test_the_old_settings_and_keys_are_gone():
    fields = set(Settings.__dataclass_fields__)
    assert not {"service_keys", "callback_secret", "callback_allow_private"} & fields
    s = Settings.from_env({"AWP_SERVICE_KEYS": "k:t:d", "AWP_CALLBACK_SECRET": "x", "AWP_ADMIN_KEYS": "a:t"})
    assert s.admin_keys == {"a": "t"} and not hasattr(s, "service_keys")


def test_the_server_needs_admin_keys_and_no_longer_loads_packs(monkeypatch):
    from awp import __main__ as main

    for name in ("AWP_ADMIN_KEYS", "AWP_SERVICE_KEYS", "AWP_DEV_OPEN", "AWP_SECRET_KEY", "AWP_PACKS"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="AWP_ADMIN_KEYS"):
        main.main()
    assert not hasattr(main, "load_packs")
    assert "packs" not in inspect.signature(build_app).parameters


def test_the_old_modules_and_tools_are_gone():
    for name in ("awp.intake", "awp.packs", "awp.requests"):
        assert importlib.util.find_spec(name) is None, name
    assert "CaseRequest" not in {c.name for c in CASE_TOOLS}
    assert "request" not in PREFIX and "reply" not in PREFIX  # no item of the case file is a request out or a reply in


FORBIDDEN = re.compile(
    r"CaseRequest|DomainPack|install_pack|AWP_PACKS|service_keys|ServiceKey|IntakeService|CaseIntake|FollowUp|"
    r"CaseResult|check_callback_url|callback_url|callback_secret|webhook|deliver_pending|expire_stalled|"
    r"awp_outbox|awp_inbound|queue_outbox|remember_inbound|is_workflow_case|LeaderWatchdog|request_kinds|"
    r"rules_by_domain|reply_to|expects_reply|confirm_with|open_requests|X-AWP-Domain|\bintake\b", re.I)


def test_no_source_line_names_the_old_design():
    hits = []
    for path in SRC.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(SRC)}:{n}: {line.strip()[:100]}")
    assert not hits, "\n".join(hits)
