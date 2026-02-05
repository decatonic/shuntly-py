from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar

from shuntly.record import Record
from shuntly.sinks import Sink, SinkStream

TVClient = TypeVar("TVClient")
TVFunc = TypeVar("TVFunc")


_METHOD_REGISTRY: dict[str, list[str]] = {
    "anthropic.Anthropic": [
        "messages.create",
        "messages.stream",
    ],
    "openai.OpenAI": ["chat.completions.create"],
}


class Shuntly:
    @staticmethod
    def _get_client_name(client: object) -> str:
        cls = client.__class__
        return f"{cls.__module__}.{cls.__qualname__}"

    @staticmethod
    def _resolve_qualified(
        obj: Any, method: str
    ) -> tuple[Callable[..., Any], Any, str]:
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

    @staticmethod
    def _get_wrapper(
        func: TVFunc,
        client_name: str,
        method: str,
        sink: Sink,
    ) -> TVFunc:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t = time.perf_counter()
            error = None
            response: Any = None
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

        return wrapper

    @classmethod
    def shunt(
        cls,
        client: TVClient,
        sink: Sink | None = None,
        *,
        methods: list[str] | None = None,
    ) -> TVClient:
        if sink is None:
            sink = SinkStream()

        client_name = cls._get_client_name(client)

        if methods is None:
            if not (methods := _METHOD_REGISTRY.get(client_name)):
                raise ValueError(
                    f"Unknown client {client_name!r}. Pass methods=[...] to specify which methods to patch."
                )

        for method in methods:
            func, parent, attr = cls._resolve_qualified(client, method)
            wrapper = cls._get_wrapper(func, client_name, method, sink)
            setattr(parent, attr, wrapper)

        return client
