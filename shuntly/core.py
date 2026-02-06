from __future__ import annotations

import functools
import time
from typing import Any, TypeVar

from shuntly.record import Record
from shuntly.sinks import Sink, SinkStream

TVClient = TypeVar('TVClient')


_METHOD_REGISTRY: dict[str, list[str]] = {
    'anthropic.Anthropic': [
        'messages.create',
        'messages.stream',
    ],
    'openai.OpenAI': ['chat.completions.create'],
    'google.genai.client.Client': ['models.generate_content'],
}


class _StreamProxy:
    """Wraps a streaming context manager to defer recording until the stream is consumed."""

    __slots__ = (
        '_cmanager',
        '_client_name',
        '_method',
        '_request',
        '_sink',
        '_t_start',
        '_stream',
    )

    def __init__(
        self,
        cmanager: Any,  # context manager
        *,
        client_name: str,
        method: str,
        request: dict[str, Any],
        sink: Sink,
        t_start: float,
    ):
        self._cmanager = cmanager
        self._client_name = client_name
        self._method = method
        self._request = request
        self._sink = sink
        self._t_start = t_start

    def __enter__(self) -> Any:
        self._stream = self._cmanager.__enter__()
        return self._stream

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> Any:
        error = None
        response = None
        try:
            if exc_type is not None:
                error = f'{exc_type.__name__}: {exc_val}'
            elif hasattr(self._stream, 'get_final_message'):
                # this is specific to Anthropic
                # https://platform.claude.com/docs/en/build-with-claude/streaming#get-the-final-message-without-handling-events
                response = self._stream.get_final_message()
            return self._cmanager.__exit__(exc_type, exc_val, exc_tb)
        finally:
            duration_ms = (time.perf_counter() - self._t_start) * 1000
            record = Record.build(
                client=self._client_name,
                method=self._method,
                request=self._request,
                response=response,
                duration_ms=duration_ms,
                error=error,
            )
            self._sink.write(record)


class Shuntly:
    @staticmethod
    def _get_client_name(client: object) -> str:
        cls = client.__class__
        return f'{cls.__module__}.{cls.__qualname__}'

    @staticmethod
    def _resolve_qualified(obj: Any, method: str) -> tuple[Any, Any, str]:
        """
        Walk a qualified path like 'messages.create' and return (parent, attr_name). Must return parent and attr for subsequent re-assignment
        """
        parts = method.split('.')
        parent = obj
        for part in parts[:-1]:
            parent = getattr(parent, part)
            if parent is None:
                raise RuntimeError(f'Invalid method path: {method}')
        attr = parts[-1]
        func = getattr(parent, attr)
        # check that this is callable?
        return func, parent, attr

    @staticmethod
    def _get_wrapper(
        func: Any,
        client_name: str,
        method: str,
        sink: Sink,
    ) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t_start = time.perf_counter()
            error = None
            response: Any = None
            deferred = False

            request: dict[str, Any]
            if args:
                request = {'args': list(args), **kwargs}
            else:
                request = kwargs

            try:
                response = func(*args, **kwargs)
                # Streaming context manager — defer recording until stream is consumed
                if hasattr(response, '__enter__') and hasattr(response, '__exit__'):
                    deferred = True
                    return _StreamProxy(
                        response,
                        client_name=client_name,
                        method=method,
                        request=request,
                        sink=sink,
                        t_start=t_start,
                    )
                return response
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
                raise
            finally:
                if not deferred:
                    duration_ms = (time.perf_counter() - t_start) * 1000
                    record = Record.build(
                        client=client_name,
                        method=method,
                        request=request,
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
        if sink is None:  # default stderr output
            sink = SinkStream()

        client_name = cls._get_client_name(client)

        if methods is None:
            if not (methods := _METHOD_REGISTRY.get(client_name)):
                raise ValueError(
                    f'Unknown client {client_name!r}. Pass methods=[...] to specify which methods to patch.'
                )

        for method in methods:
            func, parent, attr = cls._resolve_qualified(client, method)
            wrapper = cls._get_wrapper(func, client_name, method, sink)
            setattr(parent, attr, wrapper)

        return client
