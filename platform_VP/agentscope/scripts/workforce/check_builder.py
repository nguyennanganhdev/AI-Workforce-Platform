"""Run Builder checks without credentials or external connections."""

import argparse
import json
import os
import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--storage", action="store_true", help="Also run SQL storage regressions"
    )
    parser.add_argument(
        "--runtime", action="store_true", help="Also run private chat/team and Leader regressions"
    )
    parser.add_argument(
        "--automation", action="store_true", help="Also run schedule and private Discord regressions"
    )
    parser.add_argument(
        "--contracts-only", action="store_true", help="Run shared N1/N2 contracts; any skip fails this gate"
    )
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    for path in (root, root / "tests", root / "src"):
        sys.path.insert(0, str(path))
    for name in list(os.environ):
        if name == "TIKTOKEN_CACHE_DIR":
            # Local tokenizer assets contain no credential; retain offline cache.
            continue
        if any(
            marker in name for marker in ("API_KEY", "TOKEN", "SECRET")
        ) or name.endswith("_DATABASE_URL"):
            os.environ.pop(name, None)
    sys.dont_write_bytecode = True
    network_attempts = []
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def deny_network(*args, **kwargs):
        network_attempts.append(1)
        raise RuntimeError(
            "OFFLINE_TEST: application network connections are forbidden"
        )

    def local_addresses_only(host, *args, **kwargs):
        if host not in ("localhost", "127.0.0.1", "::1", None):
            return deny_network()
        return original_getaddrinfo(host, *args, **kwargs)

    if sys.platform == "win32":

        def local_socketpair(*args, **kwargs):
            # Windows asyncio's wakeup pipe is a local socketpair. Only this
            # construction uses the saved connect method; app calls are denied.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                original_connect(client, listener.getsockname())
                server, _ = listener.accept()
            return server, client

        socket.socketpair = local_socketpair
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    socket.create_connection = deny_network
    socket.getaddrinfo = local_addresses_only
    socket.socket.sendto = deny_network

    import pytest

    folder = root / ".artifacts" / "builder-check"
    folder.mkdir(parents=True, exist_ok=True)
    suite = ["tests/workforce/console", "tests/audit_publish_atomicity_test.py"]
    if options.storage:
        suite.append("tests/storage_sql_test.py")
    if options.automation:
        suite.extend([
            "tests/service_scheduler_test.py", "tests/schedule_router_test.py",
            "tests/channel_discord_workforce_test.py",
            "tests/channel_clients_test.py", "tests/channel_gateway_test.py",
        ])
    if options.runtime:
        suite.extend([
            "tests/personal_chat_test.py", "tests/personal_chat_challenge_test.py",
            "tests/team_collaboration_test.py", "tests/team_say_shared_context_test.py",
            "tests/team_shared_context_test.py", "tests/leader_evidence_middleware_test.py",
            "tests/leader_runtime_gaps_test.py", "tests/room_realtime_test.py",
            "tests/service_toolkit_test.py", "tests/service_workspace_files_test.py",
            "tests/service_workspace_status_test.py",
        ])
    started = perf_counter()
    if options.contracts_only:
        suite = [
            "tests/workforce/console/test_vin_customer_eval.py",
            "tests/workforce/console/test_vin_publish_batch.py",
            "tests/workforce/console/test_vin_personal_automation.py",
            "tests/workforce/console/test_vin_discord_identity.py",
            "tests/vin_personal_jobs_test.py",
            "tests/workforce/console/test_vin_customer_cases.py",
            "tests/workforce/console/test_vin_model_resolver_contract.py",
            "tests/workforce/console/test_shared_catalog_consumer.py",
            "tests/workforce/console/test_vin_runtime_attribution.py",
            "tests/vin_shared_fixture_test.py", "tests/vin_catalog_knowledge_test.py",
            "tests/vin_workspace_test.py",
        ]
    result = pytest.main(
        [
            "-q",
            "-p",
            "no:cacheprovider",
            "--asyncio-mode=auto",
            "--tb=short",
            f"--junitxml={folder / 'pytest.xml'}",
            *suite,
        ]
    )
    totals = ET.parse(folder / "pytest.xml").getroot().find("testsuite")
    summary = {
        key: int(totals.get(key, "0"))
        for key in ("tests", "failures", "errors", "skipped")
    }
    summary.update(
        test_runtime_seconds=round(perf_counter() - started, 3),
        external_network_attempts=len(network_attempts),
        paid_model_calls=0,
        model_mode="scripted",
        real_model_quality="not_measured",
        real_model_latency_ms=None,
        real_model_cost_usd=None,
    )
    (folder / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))
    return result or int(bool(network_attempts) or (options.contracts_only and summary["skipped"] > 0))


if __name__ == "__main__":
    raise SystemExit(main())
