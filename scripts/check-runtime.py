"""Dependency-free syntax/import checks for the runtime scaffold (not a type checker)."""

import ast
from pathlib import Path
import sys

runtime_src = Path(__file__).resolve().parents[1] / "agent-runtime" / "src"
errors = []
for source in runtime_src.rglob("*.py"):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    relative = source.relative_to(runtime_src)
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        for module in modules:
            if module.startswith("agentscope") and relative.as_posix() != "runtime/agentscope_adapter.py":
                errors.append(f"{relative}: AgentScope imports belong in runtime/agentscope_adapter.py")
            if relative.parts[0] in {"contracts", "runtime", "supervisor", "agents"} and "domain_adapters" in module.split("."):
                errors.append(f"{relative}: generic runtime must not import concrete domain adapters")

sys.path.insert(0, str(runtime_src))
from runtime.base import RuntimeAdapter  # noqa: E402

if errors:
    raise SystemExit("\n".join(errors))
print("Python runtime syntax/import boundaries: OK")
