"""Create a fresh, private Docker sandbox env. Never reads/copies production credentials."""

import argparse
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def create(output, tag=None):
    output = Path(output).resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents:
        raise ValueError("Keep sandbox credentials outside the repository")
    output.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "SANDBOX_DATABASE": "owner_pilot_test_" + uuid4().hex,
        "SANDBOX_OWNER_PASSWORD": secrets.token_hex(24),
        "SANDBOX_RUNTIME_PASSWORD": secrets.token_hex(24),
        "SANDBOX_SIGNING_KEY": secrets.token_hex(32),
        "SANDBOX_MCP_TOKEN": secrets.token_urlsafe(32),
        "SANDBOX_CONFIG_ENCRYPTION_KEY": secrets.token_hex(32),
        "SANDBOX_RECEPTION_TOKEN": secrets.token_urlsafe(32),
        "SANDBOX_DELEGATION_KEY": secrets.token_hex(32),
        "SANDBOX_IMAGE_TAG": tag
        or "business-sandbox-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
    }
    with output.open("x", encoding="utf-8") as stream:
        stream.write("# SYNTHETIC LOCAL SANDBOX ONLY; not deployment.env for VPS\n")
        stream.write("".join(f"{k}={v}\n" for k, v in values.items()))
    os.chmod(output, 0o600)
    return {
        "env_file": str(output),
        "data_mode": "synthetic_test",
        "web_url": "http://localhost:8087",
        "mcp_url": "http://host.docker.internal:8087/mcp",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag")
    args = parser.parse_args()
    import json

    print(json.dumps(create(args.output, args.tag)))
