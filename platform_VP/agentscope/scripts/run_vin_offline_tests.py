"""Run pytest without permitting model/provider calls or loading deployment env.

Only explicitly named loopback fixture ports may connect. This also blocks a
test accidentally using an inherited provider credential or a local model proxy.
Usage: python scripts/run_vin_offline_tests.py [--allow-db-port 15438] -- TESTS...
"""

import argparse
import ipaddress
import os
import socket
import sys
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-db-port", "--allow-loopback-port", type=int, action="append", default=[])
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    for name in list(os.environ):
        upper = name.upper()
        if any(part in upper for part in ("API_KEY", "MODEL_KEY", "PROVIDER_KEY")) or upper.endswith("_PROXY"):
            os.environ.pop(name, None)
    allowed = set(args.allow_db_port)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo
    original_socketpair = socket.socketpair
    internal_pair = threading.local()

    def check(address):
        if not isinstance(address, tuple) or len(address) < 2:
            raise RuntimeError("Offline test: network connection blocked")
        host, port = address[:2]
        try:
            local = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if not local or (port not in allowed and not getattr(internal_pair, "active", False)):
            raise RuntimeError("Offline test: only explicitly allowed loopback DB ports may connect")

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    def getaddrinfo(host, port, *positional, **keywords):
        check((host, port))
        return original_getaddrinfo(host, port, *positional, **keywords)

    def socketpair(*positional, **keywords):
        # Windows implements socketpair with a private loopback connection for
        # asyncio's self-pipe. Permit only this synchronous stdlib operation.
        internal_pair.active = True
        try:
            return original_socketpair(*positional, **keywords)
        finally:
            internal_pair.active = False

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    socket.socketpair = socketpair
    import pytest

    test_args = args.pytest_args
    return pytest.main(test_args[1:] if test_args[:1] == ["--"] else test_args)


if __name__ == "__main__":
    sys.exit(main())
