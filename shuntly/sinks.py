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


class SinkRotating(Sink):
    """A Sink that writes JSONL files into a directory with automatic rotation.

    Each file is named with an ISO-8601 timestamp (e.g.
    ``2025-02-15T210530Z.jsonl``).  A new file is started when the current
    file reaches *max_bytes*.  Old files are removed when total directory
    size exceeds *max_total_bytes* (oldest first).

    Args:
        directory: Path to the directory where log files are written.
            Created automatically (including parents) if it does not exist.
        max_bytes: Maximum size in bytes of a single file before rotating.
            Defaults to 10 MB.
        max_total_bytes: Maximum total size in bytes of all files in the
            directory.  When exceeded the oldest files are deleted until
            under the limit.  Defaults to 100 MB.  Set to ``0`` to disable
            pruning.
    """

    _DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    _DEFAULT_MAX_TOTAL_BYTES = 100 * 1024 * 1024  # 100 MB

    def __init__(
        self,
        directory: str,
        *,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
    ):
        self._directory = directory
        self._max_bytes = max_bytes
        self._max_total_bytes = max_total_bytes
        self._file: IO[str] | None = None
        self._file_path: str | None = None
        self._file_size: int = 0
        os.makedirs(directory, exist_ok=True)

    @staticmethod
    def _make_filename() -> str:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%S.%fZ')
        return f'{ts}.jsonl'

    def _open_new_file(self) -> IO[str]:
        if self._file is not None:
            self._file.close()
        name = self._make_filename()
        self._file_path = os.path.join(self._directory, name)
        self._file = open(self._file_path, 'a')
        self._file_size = 0
        return self._file

    def _ensure_open(self) -> IO[str]:
        if self._file is None:
            return self._open_new_file()
        if self._file_size >= self._max_bytes:
            self._prune()
            return self._open_new_file()
        return self._file

    def _prune(self) -> None:
        if self._max_total_bytes <= 0:
            return
        files: list[tuple[str, int]] = []
        for entry in os.scandir(self._directory):
            if entry.is_file() and entry.name.endswith('.jsonl'):
                files.append((entry.path, entry.stat().st_size))
        # Sort oldest first (filenames are ISO timestamps)
        files.sort(key=lambda t: t[0])
        total = sum(s for _, s in files)
        while total > self._max_total_bytes and files:
            path, size = files.pop(0)
            # Don't delete the current file
            if path == self._file_path:
                break
            os.unlink(path)
            total -= size

    def write(self, record: ShuntlyRecord) -> None:
        f = self._ensure_open()
        line = record.to_json() + '\n'
        f.write(line)
        f.flush()
        self._file_size += len(line.encode())

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
            self._file_path = None
            self._file_size = 0


class SinkMany(Sink):
    def __init__(self, sinks: list[Sink]):
        self._sinks = sinks

    def write(self, record: ShuntlyRecord) -> None:
        for sink in self._sinks:
            sink.write(record)

    def close(self) -> None:
        for sink in self._sinks:
            sink.close()
