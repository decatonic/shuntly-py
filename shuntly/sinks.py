from __future__ import annotations

import errno
import os
import stat
import sys
from abc import ABC, abstractmethod
from typing import IO

from shuntly.record import ShuntlyRecord


class Sink(ABC):
    @abstractmethod
    def write(self, record: ShuntlyRecord) -> None: ...

    def close(self) -> None:
        pass


class SinkStream(Sink):
    def __init__(self, stream: IO[str] | None = None):
        self._stream = stream or sys.stderr

    def write(self, record: ShuntlyRecord) -> None:
        self._stream.write(record.to_json() + '\n')
        self._stream.flush()


class SinkFile(Sink):
    def __init__(self, path: str):
        self._path = path
        self._file: IO[str] | None = None

    def _ensure_open(self) -> IO[str]:
        if self._file is None:
            self._file = open(self._path, 'a')
        return self._file

    def write(self, record: ShuntlyRecord) -> None:
        f = self._ensure_open()
        f.write(record.to_json() + '\n')
        f.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class SinkPipe(Sink):
    """A Sink that writes to a named pipe.

    Opens non-blocking to avoid hanging if no reader is connected, but writes
    in a loop to ensure complete records. Fails gracefully if the reader
    disconnects.
    """

    def __init__(self, path: str):
        self._path = path
        self._fd: int | None = None

    def _ensure_open(self) -> int | None:
        if self._fd is not None:
            return self._fd

        if not os.path.exists(self._path):
            os.mkfifo(self._path)
        elif not stat.S_ISFIFO(os.stat(self._path).st_mode):
            raise ValueError(f'{self._path} exists and is not a FIFO')

        try:
            self._fd = os.open(self._path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as e:
            if e.errno == errno.ENXIO:  # No reader
                return None
            raise

        return self._fd

    def write(self, record: ShuntlyRecord) -> None:
        fd = self._ensure_open()
        if fd is None:
            return

        data = (record.to_json() + '\n').encode()
        offset = 0
        while offset < len(data):
            try:
                written = os.write(fd, data[offset:])
                offset += written
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    # Buffer full — spin until space available
                    continue
                if e.errno == errno.EPIPE:
                    # Reader disconnected
                    self.close()
                    return
                raise

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


class SinkS3(Sink):
    """A Sink that buffers JSONL records and uploads them as objects to any
    S3-compatible store (AWS S3, Cloudflare R2, Backblaze B2, MinIO, etc.).

    Records are buffered in memory and uploaded as a new object when the buffer
    reaches *max_bytes_file* or when :meth:`close` is called.  Objects are
    named with ISO-8601 timestamps (e.g.
    ``prefix/2025-02-15T210530.482371Z.jsonl``).

    Retention / pruning is expected to be handled by the storage provider
    (e.g. S3 lifecycle rules, R2 object lifecycle).

    Requires the ``boto3`` package (not a hard dependency of shuntly).

    Args:
        bucket: Bucket name.
        access_key_id: S3-compatible access key ID.
        secret_access_key: S3-compatible secret access key.
        endpoint_url: Custom endpoint URL for S3-compatible providers
            (e.g. ``https://<account_id>.r2.cloudflarestorage.com`` for
            Cloudflare R2).  Omit for AWS S3.
        region: AWS region (optional, defaults to ``us-east-1``).
        prefix: Key prefix for uploaded objects (e.g. ``"prod/"``).
            Defaults to ``""``.
        max_bytes_file: Maximum buffer size in bytes before uploading a new
            object.  Defaults to 10 MB.
    """

    __slots__ = (
        '_bucket',
        '_prefix',
        '_max_bytes_file',
        '_client',
        '_buffer',
        '_buffer_size',
    )

    _DEFAULT_MAX_BYTES_FILE = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        bucket: str,
        *,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
        region: str = 'us-east-1',
        prefix: str = '',
        max_bytes_file: int = _DEFAULT_MAX_BYTES_FILE,
    ):
        self._bucket = bucket
        self._prefix = prefix
        self._max_bytes_file = max_bytes_file
        self._buffer: list[str] = []
        self._buffer_size: int = 0
        try:
            import boto3 as _boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError('SinkS3 requires boto3: pip install boto3') from exc

        self._client = _boto3.client(
            's3',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            region_name=region,
        )

    @staticmethod
    def _make_key(prefix: str) -> str:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%S.%fZ')
        return f'{prefix}{ts}.jsonl'

    def _flush(self) -> None:
        if not self._buffer:
            return
        key = self._make_key(self._prefix)
        body = ''.join(self._buffer)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body.encode(),
            ContentType='application/x-ndjson',
        )
        self._buffer.clear()
        self._buffer_size = 0

    def write(self, record: ShuntlyRecord) -> None:
        line = record.to_json() + '\n'
        self._buffer.append(line)
        self._buffer_size += len(line.encode())
        if self._buffer_size >= self._max_bytes_file:
            self._flush()

    def close(self) -> None:
        self._flush()


class SinkMany(Sink):
    def __init__(self, sinks: list[Sink]):
        self._sinks = sinks

    def write(self, record: ShuntlyRecord) -> None:
        for sink in self._sinks:
            sink.write(record)

    def close(self) -> None:
        for sink in self._sinks:
            sink.close()
