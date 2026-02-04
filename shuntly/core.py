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


def _client_key(client: object) -> str:
    cls = type(client)
    return f"{cls.__module__}.{cls.__qualname__}"


def _resolve_dotted(obj: object, dotted: str) -> tuple[object, str]:
    """Walk a dotted path like 'messages.create' and return (parent, attr_name)."""
    parts = dotted.split(".")
    parent = obj
    for part in parts[:-1]:
        parent = getattr(parent, part)
    return parent, parts[-1]


class Shuntly:
    @staticmethod
    def wrap(client: T, sink: Sink | None = None, *, methods: list[str] | None = None) -> T:
        if sink is None:
            sink = SinkStream()

        client_name = _client_key(client)

        if methods is None:
            methods = _METHOD_REGISTRY.get(client_name)
            if methods is None:
                raise ValueError(
                    f"Unknown client {client_name!r}. "
                    f"Pass methods=[...] to specify which methods to patch."
                )

        for dotted in methods:
            parent, attr = _resolve_dotted(client, dotted)
            original = getattr(parent, attr)

            @functools.wraps(original)
            def wrapper(*args, _orig=original, _dotted=dotted, **kwargs):
                t0 = time.perf_counter()
                error = None
                response = None
                try:
                    response = _orig(*args, **kwargs)
                    return response
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    raise
                finally:
                    duration_ms = (time.perf_counter() - t0) * 1000
                    record = Record.build(
                        client=client_name,
                        method=_dotted,
                        request=kwargs,
                        response=response,
                        duration_ms=duration_ms,
                        error=error,
                    )
                    sink.write(record)

            setattr(parent, attr, wrapper)

        return client  # type: ignore[return-value]
