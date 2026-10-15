"""Generate the labelled OP1 technical bundle; compatible deploy entrypoint."""

from vinhomes_api.owner_sandbox_bundle import main
from vinhomes_api.owner_sandbox_bundle import (
    prepare as prepare,  # noqa: PLC0414 -- compatibility entrypoint
)

if __name__ == "__main__":
    main()
