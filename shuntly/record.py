from __future__ import annotations

import getpass
import json
import os
import socket
from datetime import UTC, datetime
from typing import Any


class Record:
    __slots__ = (
        "timestamp",
        "hostname",
        "user",
        "pid",
        "client",
        "method",
        "request",
        "response",
        "duration_ms",
        "error",
    )

    def __init__(
        self,
        *,
        timestamp: datetime,
        hostname: str,
        user: str,
        pid: int,
        client: str,
        method: str,
        request: dict,
        response: Any,
        duration_ms: float,
        error: str | None = None,
    ):
        self.timestamp = timestamp
        self.hostname = hostname
        self.user = user
        self.pid = pid
        self.client = client
        self.method = method
        self.request = request
        self.response = response
        self.duration_ms = duration_ms
        self.error = error

    @staticmethod
    def build(
        *,
        client: str,
        method: str,
        request: dict,
        response: Any,
        duration_ms: float,
        error: str | None = None,
    ) -> Record:
        return Record(
            timestamp=datetime.now(UTC),
            hostname=socket.gethostname(),
            user=getpass.getuser(),
            pid=os.getpid(),
            client=client,
            method=method,
            request=request,
            response=response,
            duration_ms=duration_ms,
            error=error,
        )

    def to_json(self) -> str:
        return json.dumps(
            {slot: getattr(self, slot) for slot in self.__slots__},
            default=str,
        )
