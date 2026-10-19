# -*- coding: utf-8 -*-
"""The Telegram REST calls needed by the channel, with safe errors."""
import asyncio
import logging
import re
from typing import Any

import httpx


class _RedactBotToken(logging.Filter):
    """Telegram puts credentials in URLs, including httpx request logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Keep httpx logs while redacting Telegram token paths."""
        message = record.getMessage()
        if "https://api.telegram.org/bot" in message:
            record.msg = re.sub(
                r"https://api\.telegram\.org/bot[^/\s]+",
                "https://api.telegram.org/bot<redacted>",
                message,
            )
            record.args = ()
        return True


logging.getLogger("httpx").addFilter(_RedactBotToken())


class _TelegramAPIError(RuntimeError):
    """A provider failure that never contains an authenticated URL."""

    def __init__(
        self, message: str, code: int = 502, retry_after: float = 0
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


class _TelegramOpenAPI:
    """Share one async HTTP client between polling and outbound calls."""

    def __init__(self, bot_token: str, http: httpx.AsyncClient) -> None:
        self._token = bot_token
        self._http = http

    async def call(self, method: str, **payload: Any) -> Any:
        """Call Bot API; retry explicit rate limits, never ambiguous sends."""
        for attempt in range(3):
            try:
                response = await self._http.post(
                    f"https://api.telegram.org/bot{self._token}/{method}",
                    json=payload,
                )
            except httpx.HTTPError:
                raise _TelegramAPIError(
                    "Telegram connection failed. Check network access.",
                ) from None
            try:
                data = response.json()
            except ValueError:
                raise _TelegramAPIError(
                    "Telegram returned an invalid response.",
                    response.status_code if response.is_error else 502,
                ) from None
            if not isinstance(data, dict):
                raise _TelegramAPIError(
                    "Telegram returned an invalid response."
                )
            if response.is_success and data.get("ok") is True:
                return data.get("result")
            code = data.get("error_code", response.status_code)
            if not isinstance(code, int):
                code = 502
            parameters = data.get("parameters")
            delay = (
                parameters.get("retry_after", 1)
                if isinstance(parameters, dict)
                else 1
            )
            if not isinstance(delay, (int, float)) or delay < 0:
                delay = 1
            if code == 429 and attempt < 2:
                await asyncio.sleep(delay)
                continue
            description = str(data.get("description") or "Request failed")
            description = description.replace(self._token, "<redacted>")
            raise _TelegramAPIError(
                f"Telegram {method}: {description}",
                code,
                retry_after=delay if code == 429 else 0,
            )
