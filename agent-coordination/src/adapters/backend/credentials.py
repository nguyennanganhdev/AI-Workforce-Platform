"""Service bearer credentials read per request, including secret rotation."""
from __future__ import annotations

import os
from typing import Callable

from .errors import AdapterError


class BearerCredentials:
    def __init__(self, token: Callable[[], str]) -> None:
        self._token = token

    @classmethod
    def from_environment(cls, variable: str) -> BearerCredentials:
        if not variable or not variable.strip():
            raise ValueError("credential variable is required")
        return cls(lambda: os.environ.get(variable, ""))

    async def headers(self) -> dict[str, str]:
        try:
            token = self._token()
            if (not isinstance(token, str) or not token or len(token) > 16384
                    or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in token)):
                raise ValueError()
        except Exception:
            raise AdapterError("credentials_unavailable") from None
        return {"Authorization": "Bearer " + token}
