"""Puts vinhomes-declaration.json into a Workforce v1 platform through its admin API. For the platform's operator.

    python deploy/platform/apply.py --platform URL --admin-key-env NAME --mcp-url URL --mcp-token-env NAME \
        --management-refs CODE[,CODE...] [--environment sandbox] [--new-keys]

Safe to run again: the ids of what was created are kept in .applied.json (next to this file, no secret in it), so a
second run creates no second client, key, integration or route; it only writes the MCP server and the tool table
again. Secrets are shown once by the platform and go to platform.env only, never to the screen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
STATE, SECRETS = HERE / ".applied.json", HERE / "platform.env"
WF = "/platform/v1/wf"


class Admin:
    def __init__(self, base: str, key: str) -> None:
        self.http = httpx.Client(base_url=base.rstrip("/"), headers={"Authorization": f"Bearer {key}"}, timeout=30)

    def call(self, method: str, path: str, body: dict | None = None, missing_ok: bool = False) -> dict | None:
        res = self.http.request(method, path, json=body)
        if missing_ok and res.status_code == 404:
            return None
        if res.status_code >= 400:
            # The admin API answers {"detail": ...}: what was wrong with the request, never a secret.
            raise SystemExit(f"{method} {path} -> {res.status_code}: {res.text[:2000]}")
        return res.json()


def covers(stored, declared) -> bool:
    """The platform stores what was declared plus its own defaults: every declared value must be there unchanged."""
    if isinstance(declared, dict):
        return isinstance(stored, dict) and all(k in stored and covers(stored[k], v) for k, v in declared.items())
    if isinstance(declared, list):
        return isinstance(stored, list) and len(stored) == len(declared) and all(map(covers, stored, declared))
    return stored == declared


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_secrets(values: dict[str, str]) -> None:
    """Merges into platform.env: a run that issues only one new key keeps the other lines."""
    lines: dict[str, str] = {}
    if SECRETS.exists():
        lines = dict(line.split("=", 1) for line in SECRETS.read_text(encoding="utf-8").splitlines() if "=" in line)
    lines.update(values)
    SECRETS.write_text("".join(f"{k}={v}\n" for k, v in lines.items()), encoding="utf-8")
    try:
        SECRETS.chmod(0o600)
    except OSError:
        pass


def profiles(api: Admin, declared: list[dict], state: dict) -> None:
    stored = api.call("GET", "/platform/v1/profiles?status=published")["profiles"]
    for profile in declared:
        live = next((p for p in stored if p["key"] == profile["key"]), None)
        if live and covers(live["profile"], profile):
            version = live["version"]
        else:
            version = api.call("POST", "/platform/v1/profiles", profile)["version"]
            api.call("POST", f"/platform/v1/profiles/{profile['key']}/versions/{version}/publish")
        state.setdefault("profiles", {})[profile["key"]] = version
        print(f"profile {profile['key']}: version {version} published")


def client(api: Admin, decl: dict, environment: str, state: dict) -> str:
    if state.get("client_id"):
        if api.call("GET", f"{WF}/clients/{state['client_id']}", missing_ok=True) is None:
            raise SystemExit(f"{STATE.name} names a client this platform does not have; it belongs to another platform "
                             "or tenant. Move the file away to start again.")
    else:
        state["client_id"] = api.call("POST", f"{WF}/clients", {**decl["client"], "environment": environment})["client_id"]
        save_state(state)
    print(f"client: {state['client_id']} ({environment})")
    return state["client_id"]


def customer_key(api: Admin, decl: dict, state: dict, new: bool) -> None:
    old = state.get("customer_key_id")
    if old and not new:
        return
    made = (api.call("POST", f"{WF}/keys/{old}/rotate") if old
            else api.call("POST", f"{WF}/clients/{state['client_id']}/keys", decl["customer_key"]))
    save_secrets({"VINHOMES_API_PLATFORM_CUSTOMER_KEY": made["api_key"]})
    state["customer_key_id"] = made["key_id"]
    save_state(state)
    print(f"customer key: {made['key_id']} issued" + (f" (replaces {old})" if old else ""))


def integration(api: Admin, decl: dict, state: dict) -> str:
    if state.get("integration_id"):
        live = api.call("GET", f"{WF}/integrations/{state['integration_id']}")
        if not covers(live["event_schema"], decl["integration"]["event_schema"]):
            raise SystemExit("The event schema in the declaration differs from the one the platform stores, and the platform "
                             "has no way to change a stored schema. To create a new integration (with new provider and "
                             f"signing keys), remove integration_id, provider_key_id and signing_key_id from {STATE.name}.")
    else:
        state["integration_id"] = api.call("POST", f"{WF}/clients/{state['client_id']}/integrations",
                                           decl["integration"])["integration_id"]
        save_state(state)
    print(f"integration: {state['integration_id']}")
    return state["integration_id"]


def provider_key(api: Admin, decl: dict, state: dict, new: bool) -> None:
    old_key, old_signing = state.get("provider_key_id"), state.get("signing_key_id")
    if old_key and not new:
        return
    intg = state["integration_id"]
    made = api.call("POST", f"{WF}/integrations/{intg}/keys", decl["provider_key"])
    save_secrets({"VINHOMES_API_PLATFORM_PROVIDER_KEY": made["api_key"],
                  "VINHOMES_API_PLATFORM_SIGNING_KEY_ID": made["signing_key"]["key_id"],
                  "VINHOMES_API_PLATFORM_SIGNING_SECRET": made["signing_key"]["secret"]})
    state["provider_key_id"], state["signing_key_id"] = made["key_id"], made["signing_key"]["key_id"]
    save_state(state)
    if old_key:  # the new pair is on disk: the old one can go
        api.call("POST", f"{WF}/keys/{old_key}/revoke")
        api.call("POST", f"{WF}/integrations/{intg}/signing-keys/{old_signing}/revoke")
    print(f"provider key: {made['key_id']}, signing key: {made['signing_key']['key_id']} issued"
          + (f" (replace {old_key} and {old_signing}, now revoked)" if old_key else ""))


def route(api: Admin, decl: dict, state: dict, ref: str) -> dict:
    routes = state.setdefault("routes", {})
    if ref in routes:
        live = api.call("GET", f"{WF}/routes/{routes[ref]}")
        if live["status"] == "replaced":
            raise SystemExit(f"route {routes[ref]} of {ref} was replaced on the platform; put the id of the route that "
                             f"replaced it in {STATE.name}.")
        if live["leader_profile"] != decl["route"]["leader_profile"] or not covers(live["config"], decl["route"]["config"]):
            # Only a replace changes a route, and it blocks the workflows that are open: a person decides that.
            print(f"WARNING route {live['route_id']} ({ref}): its stored leader or config differs from the declaration; not changed")
        return live
    live = api.call("POST", f"{WF}/clients/{state['client_id']}/routes", {"external_management_ref": ref, **decl["route"]})
    routes[ref] = live["route_id"]
    save_state(state)
    return live


def tools(api: Admin, decl: dict, state: dict, route_id: str, mcp_url: str, token: str) -> None:
    server = {**decl["mcp_server"], "url": mcp_url, "headers": {"Authorization": f"Bearer {token}"}}
    api.call("PUT", f"{WF}/routes/{route_id}/mcp", {"servers": [server]})
    # A tool followed by events names who sends them, so a second integration of the client could not be mistaken for it.
    rows = [{**t, "integration_id": state["integration_id"]} if t["tracking"] == "events" else t for t in decl["tools"]]
    api.call("PUT", f"{WF}/routes/{route_id}/tools", {"tools": rows})
    stored = api.call("GET", f"{WF}/routes/{route_id}/tools")["tools"]
    servers = api.call("GET", f"{WF}/routes/{route_id}/mcp")["servers"]
    print(f"  mcp: {', '.join(s['name'] + ' ' + s['url'] + ' headers ' + str(s['header_names']) for s in servers)}")
    print(f"  tools ({len(stored)}): " + ", ".join(
        f"{t['name']}[{t['kind']}{'/' + t['tracking'] if t['tracking'] != 'none' else ''}]" for t in stored))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--platform", required=True, help="root of the platform, e.g. http://127.0.0.1:8800")
    ap.add_argument("--admin-key-env", required=True, help="name of the variable that holds the platform admin key")
    ap.add_argument("--mcp-url", required=True, help="Vinhomes MCP endpoint as the platform reaches it, e.g. https://.../mcp")
    ap.add_argument("--mcp-token-env", required=True, help="name of the variable that holds VINHOMES_API_PLATFORM_MCP_TOKEN")
    ap.add_argument("--management-refs", required=True, help="management_units.code values, comma separated: one route each")
    ap.add_argument("--environment", default="sandbox", choices=("sandbox", "production"))
    ap.add_argument("--new-keys", action="store_true", help="issue new customer, provider and signing keys and revoke the old ones")
    args = ap.parse_args()
    admin_key, token = os.environ.get(args.admin_key_env, ""), os.environ.get(args.mcp_token_env, "")
    if not admin_key:
        raise SystemExit(f"{args.admin_key_env} is not set")
    if len(token) < 32:
        raise SystemExit(f"{args.mcp_token_env} must hold the MCP token (32 characters or more)")
    refs = [r.strip() for r in args.management_refs.split(",") if r.strip()]
    if not refs:
        raise SystemExit("--management-refs names no management unit")

    decl = json.loads((HERE / "vinhomes-declaration.json").read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    here = {"platform": args.platform.rstrip("/"), "environment": args.environment}
    if state and {k: state.get(k) for k in here} != here:
        raise SystemExit(f"{STATE.name} was written for {state.get('platform')} ({state.get('environment')}). "
                         "Move it and platform.env away to apply to another platform or environment.")
    state.update(here)
    api = Admin(args.platform, admin_key)

    profiles(api, decl["profiles"], state)
    client(api, decl, args.environment, state)
    customer_key(api, decl, state, args.new_keys)
    integration(api, decl, state)
    provider_key(api, decl, state, args.new_keys)
    live = []
    for ref in refs:
        row = route(api, decl, state, ref)
        print(f"route {ref}: {row['route_id']} revision {row['revision']} {row['status']}")
        tools(api, decl, state, row["route_id"], args.mcp_url, token)
        live.append(row)
    save_state(state)
    save_secrets({"VINHOMES_API_PLATFORM_URL": state["platform"]})

    schema = api.call("GET", f"{WF}/integrations/{state['integration_id']}")
    print(f"events ({schema['event_schema']['version_mode']}): " + ", ".join(schema["event_schema"]["events"]))
    print(f"\nKeys are in {SECRETS} (shown once by the platform; this file is the only copy).")
    print("Vinhomes: paste its lines into deploy/deployment.env. VINHOMES_API_PLATFORM_URL must be the address the "
          "Vinhomes containers reach the platform at; change it if that is not the one used here.")
    pending = [r for r in live if r["status"] == "pending"]
    if pending:
        print("Then restart api and platform-sync and confirm the routes with the customer key:")
        print("  python -m vinhomes_api.platform confirm-routes "
              + " ".join(f"--route {r['external_management_ref']}={r['route_id']}:{r['revision']}" for r in pending))
    else:
        print("Every route is already confirmed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
