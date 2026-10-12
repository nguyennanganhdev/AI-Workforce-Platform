"""The admin console (B3, MVP section 7): a static page served at /console that holds no data and no rules.

What is tested here without a browser: how the files are served (strict headers, no key needed, nothing else under
/console), what is in them (nothing from another origin, no way of turning a string into markup or code, the key only
in the Authorization header), that every endpoint the page calls exists and needs a key, and the two small read
endpoints the page got (`me`, a version's `gate`). The owner's flows are in test_wf_console_flows.py.
"""
from __future__ import annotations

import fnmatch
import re
import tomllib
from pathlib import Path

import evalkit as ek
import pytest
from conftest import ADM, ADM_B, key_headers
from consolekit import DIR, EP, JS, Page

from awp.console import FILES, HEADERS

STATIC = ["/console", "/console/", "/console/app.js", "/console/app.css", "/console/favicon.svg"]
SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'  # a namespace name: the one string shaped like a URL, and nothing fetches it
HTML = (DIR / "index.html").read_text(encoding="utf-8")


# ---- serving ----------------------------------------------------------------------------------------------------------
def test_the_page_and_its_files_are_served_without_a_key_under_strict_headers(env):
    types = {"/console": "text/html", "/console/": "text/html", "/console/app.js": "text/javascript",
             "/console/app.css": "text/css", "/console/favicon.svg": "image/svg+xml"}
    for path in STATIC:
        r = env.http.get(path)  # no key at all
        assert r.status_code == 200, path
        assert r.headers["content-type"].startswith(types[path]), path
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp, path
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp and "*" not in csp and "data:" not in csp, path
        assert not re.search(r"\b(script|style|connect|img)-src\b", csp), "nothing loosens default-src"
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer", path
        assert r.headers["x-frame-options"] == "DENY" and r.headers["cache-control"] == "no-store", path
        assert "set-cookie" not in r.headers, path
    for path, name in (("/console", "index.html"), ("/console/app.js", "app.js"), ("/console/app.css", "app.css")):
        assert env.http.get(path).content == (DIR / name).read_bytes(), path  # the file as it is on disk, byte for byte
    assert env.http.get("/console", headers={"Authorization": "Bearer nobody"}).status_code == 200  # a stale key does not lock the page


def test_nothing_else_lives_under_console(env):
    for path in ("/console/__init__.py", "/console/app.js.map", "/console/..%2fsecurity.py", "/console/index.html/x", "/console/nothing"):
        r = env.http.get(path)
        assert r.status_code == 404, path
        assert "awp" not in r.text and "import" not in r.text, path
    assert env.http.get("/console/nothing").headers["x-content-type-options"] == "nosniff"
    for method in ("post", "put", "delete", "patch"):  # only reading the page is open
        assert getattr(env.http, method)("/console").status_code == 401, method
    assert env.http.get("/consolex").status_code == 401 and env.http.get("/console.js").status_code == 401
    # the files that are served are exactly the files of the package
    shipped = {p.name for p in DIR.iterdir() if p.is_file() and p.suffix != ".py"}
    assert shipped == set(FILES)
    assert set(HEADERS) >= {"Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy"}


def test_the_static_files_are_part_of_the_installed_package():
    data = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    globs = data["tool"]["setuptools"]["package-data"]["awp"]
    for name in FILES:
        assert any(fnmatch.fnmatch(f"console/{name}", g) for g in globs), name


# ---- what is in the files -----------------------------------------------------------------------------------------------
def test_no_console_file_names_another_origin():
    for name in FILES:
        text = (DIR / name).read_text(encoding="utf-8").replace(SVG_NS, "")
        assert not re.search(r"\b(?:https?|wss?|ftp)://", text, re.I), name
        assert not re.search(r"(?<![:\w/])//[\w-]+(\.[\w-]+)+", text), f"{name}: a protocol-relative URL"
        assert not re.search(r"@import|\burl\(|\bsrcset\b", text), name
        assert not re.search(r"""['"`(=]\s*(?:javascript|data|blob|wss?|https?|ftp|file)\s*:""", text, re.I), f"{name}: a URL scheme"
    # the page loads its own three files and nothing else; no inline script, style or handler
    assert re.findall(r"<script\b[^>]*>", HTML) == ['<script src="/console/app.js" defer>']
    assert re.findall(r'<link\b[^>]*href="([^"]+)"', HTML) == ["/console/favicon.svg", "/console/app.css"]
    assert not re.search(r"<style\b|\sstyle=|\son\w+\s*=|<iframe|<object|<embed|<img|<base\b", HTML, re.I)
    assert "<script" not in (DIR / "favicon.svg").read_text(encoding="utf-8").lower()


SINKS = [r"\.innerHTML\b", r"\.outerHTML\b", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"\bnew\s+Function\b",
         r"\bFunction\s*\(", r"setTimeout\s*\(\s*['\"`]", r"setInterval\s*\(", r"createContextualFragment", r"DOMParser",
         r"\.srcdoc\b", r"setAttribute\s*\(\s*['\"]on", r"\bimport\s*\(", r"\bimportScripts\b", r"\.style\b", r"createElementNS",
         r"<\s*script", r"\bwindow\.open\b", r"\bpostMessage\b"]


def test_app_js_has_no_way_to_turn_a_string_into_markup_or_code():
    for sink in SINKS:
        assert not re.search(sink, JS), sink
    # every element is made by `h`: text goes in as text, a listener is a function, a link stays inside the page
    assert JS.count("document.createElement(") == 1 and "el.textContent = String(v)" in JS and "document.createTextNode(String(kid))" in JS
    assert "if (typeof v !== 'function') throw new Error('a listener must be a function')" in JS
    assert "if (!String(v).startsWith('#/')) throw new Error('links stay inside the console')" in JS
    assert re.findall(r"setAttribute\('([\w-]+)'", JS) ==["href", "aria-invalid"]  # the only literal attribute names
    assert re.findall(r"location\.(\w+)", JS).count("href") == 0 and set(re.findall(r"location\.(\w+)", JS)) == {"hash", "origin"}


def test_the_key_lives_in_session_storage_and_only_travels_in_the_authorization_header():
    assert JS.count("fetch(") == 1 and "await fetch(path, init)" in JS  # one way out of the page
    for other in ("XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "localStorage", "document.cookie", "indexedDB"):
        assert other not in JS, other
    assert "credentials: 'omit'" in JS and "referrerPolicy: 'no-referrer'" in JS
    # the key: read from sessionStorage, written there at login, dropped at logout, sent in one header
    uses = re.findall(r"^.*\bstate\.key\b.*$", JS, re.M)
    allowed = (r"Authorization: 'Bearer ' \+ state\.key", r"state\.key = (v\.key|''|store\.get\(KEY\));", r"if \(state\.key\) \{$")
    for line in uses:
        assert any(re.search(a, line) for a in allowed), line
    assert sum("Bearer" in line for line in uses) == 1
    assert JS.count("window.sessionStorage.") == 3 and "store.set(KEY, v.key)" in JS
    logout = re.search(r"function logout\(message\) \{(.*?)\n  \}", JS, re.S).group(1)
    assert "store.drop(KEY)" in logout and "state.key = ''" in logout and "state.me = null" in logout
    # a path is the endpoint template with encoded arguments, a query is made of filters: neither is given the key
    assert "template.replace(/\\{\\}/g, () => encodeURIComponent(String(given[i++])))" in JS
    assert not re.search(r"query\.set\([^)]*key", JS, re.I) and not re.search(r"query: \{[^}]*\b(key|token|authorization)\b", JS, re.I)
    assert "type: 'password'" in JS  # typed into a masked field


def test_a_key_in_the_url_opens_nothing(env):
    for query in ("key=adm-a", "api_key=adm-a", "token=adm-a", "authorization=Bearer%20adm-a", "access_token=adm-a"):
        assert env.http.get(f"/platform/v1/wf/me?{query}").status_code == 401, query
    assert env.http.get("/platform/v1/wf/me", headers={"X-Api-Key": "adm-a"}).status_code == 401
    assert env.http.get("/platform/v1/wf/me", headers={"Cookie": "key=adm-a; Authorization=Bearer adm-a"}).status_code == 401


# ---- the endpoints of the page --------------------------------------------------------------------------------------------
def test_every_endpoint_the_page_calls_exists_in_the_api(env):
    paths = env.app.openapi()["paths"]  # what the app really serves, read from its own description
    have = {(m.upper(), re.sub(r"\{[^}]+\}", "{}", path)) for path, ops in paths.items() for m in ops}
    assert len(EP) > 50 and not any(p.startswith("/console") for p in paths)  # the page itself is not part of the API
    assert ("GET", "/platform/v1/wf/routes/{}/mcp") in have
    for name, (method, path) in EP.items():
        assert (method, path) in have, f"{name}: {method} {path} is not an endpoint of the platform"
        assert path.startswith("/platform/v1/"), name  # the admin API only: never the partner API, never AgentScope's
    assert "const [method, template] = EP[name];" in JS  # a call is made from a line of the table and from nothing else
    assert len(re.findall(r"'/platform/v1/", JS)) == len(EP)  # no path outside the table


def test_no_endpoint_of_the_page_answers_without_a_key(env):
    for name, (method, template) in EP.items():
        path = template.replace("{}", "x")
        for headers in ({}, {"Authorization": "Bearer not-a-key"}, {"Authorization": "Bearer mk_0000000000000000.nothing"},
                        {"Authorization": "Bearer "}):
            r = env.http.request(method, path, headers=headers, json={} if method != "GET" else None)
            assert r.status_code == 401, f"{name} with {headers}: {r.status_code}"
    c = env.client()
    partner = env.key(c["client_id"])["api_key"]
    for headers in (key_headers(partner), {"Authorization": f"Bearer {partner}"}):  # a partner's key is not an operator's
        assert env.http.get("/platform/v1/wf/me", headers=headers).status_code == 401


# ---- who am I --------------------------------------------------------------------------------------------------------------
def test_me_tells_an_admin_and_a_manager_who_their_key_is(env):
    me = Page(env, "adm-a").ok("me")
    assert me == {"tenant": "ta", "role": "admin", "actor": me["actor"], "manager_id": None, "manager_name": None, "client_id": None}
    assert re.fullmatch(r"admin:[0-9a-f]{8}", me["actor"]) and "adm-a" not in str(me)
    assert Page(env, "adm-b").ok("me")["tenant"] == "tb"
    c = env.client()
    m = env.manager(c["client_id"], "Khối B <b>")
    key = env.manager_key(m["manager_id"])["Authorization"].removeprefix("Bearer ")
    assert Page(env, key).ok("me") == {"tenant": "ta", "role": "manager", "actor": f"manager:{m['manager_id']}",
                                       "manager_id": m["manager_id"], "manager_name": "Khối B <b>", "client_id": c["client_id"]}
    env.post(f"/platform/v1/wf/managers/{m['manager_id']}/disable")
    assert Page(env, key).call("me").status_code == 401  # a key of an account that was switched off is nobody


def test_dev_mode_serves_the_console_and_any_typed_key_is_the_dev_tenant(make_env):
    with make_env(dev_open=True, admin_keys={}) as env:
        assert env.http.get("/console").status_code == 200
        assert Page(env, "anything").ok("me")["tenant"] == "dev"


# ---- the gate, read -------------------------------------------------------------------------------------------------------
def test_the_gate_of_a_version_is_read_by_those_who_may_read_the_profile(env):
    ek.draft(env, ek.TECH)
    page = Page(env, "adm-a")
    g = page.ok("gate", "tech", 1)
    assert (g["key"], g["version"], g["status"], g["publishable"]) == ("tech", 1, "draft", False)
    assert g["refusal"]["code"] == "EVAL_REQUIRED" and "not been evaluated" in g["refusal"]["message"] and g["refusal"]["latest_run"] is None
    assert page.call("publish", "tech", 1).json()["detail"] == g["refusal"]  # the same answer the publish gives
    assert env.sql("select status from awp_profiles") == [("draft",)]  # reading the gate changes nothing
    assert page.call("gate", "tech", 2).status_code == 404 and page.call("gate", "nobody", 1).status_code == 404
    assert Page(env, "adm-b").call("gate", "tech", 1).status_code == 404  # another tenant's profile is not there
    c = env.client()
    stranger = env.manager_key(env.manager(c["client_id"])["manager_id"])["Authorization"].removeprefix("Bearer ")
    assert Page(env, stranger).call("gate", "tech", 1).status_code == 404  # no route of this manager uses it
    assert env.http.get("/platform/v1/profiles/tech/versions/1/gate").status_code == 401
    assert env.http.get("/platform/v1/profiles/tech/versions/1/gate", headers=ADM_B).status_code == 404
    assert env.http.get("/platform/v1/profiles/tech/versions/1/gate", headers=ADM).status_code == 200


@pytest.mark.parametrize("gate_on", [True, False])
def test_the_gate_reads_as_open_when_a_deployment_turned_it_off(make_env, gate_on):
    with make_env(eval_gate=gate_on) as env:
        ek.draft(env, ek.TECH)
        assert Page(env, "adm-a").ok("gate", "tech", 1)["publishable"] is (not gate_on)
