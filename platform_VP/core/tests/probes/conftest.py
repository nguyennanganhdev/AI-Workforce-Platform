"""The P0 probes (not part of the default run: see addopts in pyproject.toml).

Two of them drove the connector API that phase P4 deleted (POST /platform/v1/intake, service keys, a DomainPack) and
cannot run any more: `test_p0_crash.py` (hard kill of a real process; its conclusions are in
docs/research/KIEM_CHUNG_P0_CRASH.md) and `test_p0_mcp_sdk.py`. The crash probe is to be rewritten on the Workforce API
when crash recovery is built (slice S7); until then "a real kill during a wait" is not proven by any test that runs.
The others (offload, ask/park, turn wake) do not use awp's removed code.
"""
collect_ignore = ["test_p0_crash.py", "test_p0_mcp_sdk.py"]
