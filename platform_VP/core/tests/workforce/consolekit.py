"""The console as a test sees it without a browser: the endpoint table of app.js, and a `Page` that calls the API the
way the page does (only endpoints of that table, the key in the Authorization header, bodies shaped like the forms').

The table is read out of app.js itself, so a flow test below drives what the page calls, not what a test author
remembers: an endpoint the page loses, or one a test would like but the page lacks, fails here.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

import awp.console

DIR = Path(awp.console.__file__).parent
JS = (DIR / "app.js").read_text(encoding="utf-8")
_TABLE = re.search(r"const EP = \{\n(.*?)\n  \};", JS, re.S).group(1)
EP = {name: (method, path) for name, method, path in
      re.findall(r"^\s+(\w+): \['(GET|POST|PUT|PATCH|DELETE)', '([^']+)'\],$", _TABLE, re.M)}
assert len(EP) == len([x for x in _TABLE.splitlines() if x.strip()]), "a line of app.js's endpoint table was not understood"


class Page:
    """One logged-in console: `key` is what the operator typed."""

    def __init__(self, env, key: str) -> None:
        self.env, self.key = env, key
        self.urls: list[str] = []  # every URL asked for, to show that the key is in none

    def call(self, name: str, *args, body=None, query=None):
        method, template = EP[name]
        assert template.count("{}") == len(args), f"{name} takes {template.count('{}')} path arguments"
        path = template
        for a in args:
            path = path.replace("{}", quote(str(a), safe=""), 1)
        params = {k: v for k, v in (query or {}).items() if v not in (None, "")}  # as app.js: empty filters are left out
        r = self.env.http.request(method, path, headers={"Authorization": f"Bearer {self.key}"}, json=body, params=params or None)
        self.urls.append(str(r.request.url))
        assert self.key not in str(r.request.url)
        return r

    def ok(self, name: str, *args, body=None, query=None):
        """The JSON of a call that must succeed."""
        r = self.call(name, *args, body=body, query=query)
        assert 200 <= r.status_code < 300, f"{name}: {r.status_code} {r.text}"
        return r.json()


# ---- the bodies the forms of app.js send (the same fields, in the same shape) ---------------------------------------
def tool_action(tracking="none", ask=True, waiver=None, summary=None, reference=None, idempotency=None, status_tool=None,
                integration=None, activate=True) -> dict:
    """`toolBody` of app.js for an action."""
    body = {"read_only": False, "tracking": tracking, "requires_consent": ask, "consent_waiver": None if ask else waiver,
            "consent_summary": summary if ask else None, "client_reference_arg": reference, "idempotency_arg": idempotency,
            "status_tool": status_tool, "integration_id": integration}
    return {**({"status": "active"} if activate else {}), "kind": "action", **body}


def tool_lookup(waiver=None, activate=True) -> dict:
    """`toolBody` of app.js for a look-up."""
    body = {"read_only": True, "requires_consent": False, "tracking": "none", "client_reference_arg": None, "idempotency_arg": None,
            "status_tool": None, "integration_id": None, "consent_summary": None, "consent_waiver": waiver}
    return {**({"status": "active"} if activate else {}), "kind": "lookup", **body}


def eval_case(name: str, text: str, fixtures=None, **checks) -> dict:
    """`caseBody` of app.js: every check the form shows is sent."""
    full = {"must_call": [], "must_not_call": [], "must_contain": [], "must_not_contain": [], "grounded": False,
            "must_record_gap": False, "expected_state": []}
    return {"name": name, "input": text, "fixtures": fixtures or {}, "checks": {**full, **checks}}
