from __future__ import annotations

import dataclasses
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

    @staticmethod
    def _json_default(obj: Any) -> Any:
        # Pydantic v2 models (anthropic, openai SDKs): model_dump
        # Pydantic v1 / other dict-able objects: dict
        for attr in ("model_dump", "dict", "to_dict"):
            if func := getattr(obj, attr, None):
                return func()

        if isinstance(obj, datetime):
            return obj.isoformat()
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return str(obj)

    def to_json(self) -> str:
        return json.dumps(
            {slot: getattr(self, slot) for slot in self.__slots__},
            default=self._json_default,
        )
