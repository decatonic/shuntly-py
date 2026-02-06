from __future__ import annotations

import errno
import os
import stat
import sys
from abc import ABC, abstractmethod
from typing import IO

from shuntly.record import Record


class Sink(ABC):
    @abstractmethod
    def write(self, record: Record) -> None: ...

    def close(self) -> None:
        pass


class SinkStream(Sink):
    def __init__(self, stream: IO[str] | None = None):
        self._stream = stream or sys.stderr

    def write(self, record: Record) -> None:
        self._stream.write(record.to_json() + "\n")
        self._stream.flush()


class SinkFile(Sink):
    def __init__(self, path: str):
        self._path = path
        self._file: IO[str] | None = None

    def _ensure_open(self) -> IO[str]:
        if self._file is None:
            self._file = open(self._path, "a")
        return self._file

    def write(self, record: Record) -> None:
        f = self._ensure_open()
        f.write(record.to_json() + "\n")
        f.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class SinkPipe(Sink):
    '''A Sink that writes to a named pipe. Note that this is designed to fail gracefully if the reader does not connect, or disconnects, from the pipe.
    '''
    def __init__(self, path: str):
        self._path = path
        self._fd: int | None = None

    def _ensure_open(self) -> int | None:
        if self._fd is not None:
            return self._fd

        if not os.path.exists(self._path):
            os.mkfifo(self._path)
        elif not stat.S_ISFIFO(os.stat(self._path).st_mode):
            raise ValueError(f"{self._path} exists and is not a FIFO")

        try:
            self._fd = os.open(self._path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as e:
            if e.errno == errno.ENXIO:  # No reader
                return None
            raise

        return self._fd

    def write(self, record: Record) -> None:
        fd = self._ensure_open()
        if fd is not None:
            try:
                os.write(fd, (record.to_json() + "\n").encode())
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EPIPE):
                    # Buffer full or reader disconnected — drop it
                    self.close()
                else:
                    raise

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


class SinkMany(Sink):
    def __init__(self, sinks: list[Sink]):
        self._sinks = sinks

    def write(self, record: Record) -> None:
        for sink in self._sinks:
            sink.write(record)

    def close(self) -> None:
        for sink in self._sinks:
            sink.close()
