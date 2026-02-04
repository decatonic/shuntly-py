from __future__ import annotations

import functools
import time
from typing import TypeVar

from shuntly.record import Record
from shuntly.sinks import Sink, SinkStream

T = TypeVar("T")

_METHOD_REGISTRY: dict[str, list[str]] = {
    "anthropic.Anthropic": ["messages.create"],
    "openai.OpenAI": ["chat.completions.create"],
}


class Shuntly:
    @staticmethod
    def _get_client_name(client: object) -> str:
        cls = client.__class__
        return f"{cls.__module__}.{cls.__qualname__}"

    @staticmethod
    def _resolve_qualified(obj: object, method: str) -> tuple[object, str]:
        """
        Walk a qualified path like 'messages.create' and return (parent, attr_name). Must return parent and attr for subsequent re-assignment
        """
        parts = method.split(".")
        parent = obj
        for part in parts[:-1]:
            parent = getattr(parent, part)
            if parent is None:
                raise RuntimeError(f"Invalid method path: {method}")
        attr = parts[-1]
        func = getattr(parent, attr)
        return func, parent, attr

    @classmethod
    def wrap(
        cls,
        client: T,
        sink: Sink | None = None,
        *,
        methods: list[str] | None = None,
    ) -> T:
        if sink is None:
            sink = SinkStream()

        client_name = cls._get_client_name(client)

        if methods is None:
            if not (methods := _METHOD_REGISTRY.get(client_name)):
                raise ValueError(
                    f"Unknown client {client_name!r}. "
                    f"Pass methods=[...] to specify which methods to patch."
                )

        for method in methods:
            func, parent, attr = cls._resolve_qualified(client, method)

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                t = time.perf_counter()
                error = None
                response = None
                try:
                    response = func(*args, **kwargs)
                    return response
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    raise
                finally:
                    duration_ms = (time.perf_counter() - t) * 1000
                    record = Record.build(
                        client=client_name,
                        method=method,
                        request=kwargs,
                        response=response,
                        duration_ms=duration_ms,
                        error=error,
                    )
                    sink.write(record)

            setattr(parent, attr, wrapper)

        return client  # type: ignore[return-value]
