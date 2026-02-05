import io
import json
import os
import tempfile

from shuntly import Record, SinkFile, SinkMany, SinkStream


def _make_record(**overrides) -> Record:
    defaults = dict(
        client="test.Client",
        method="do.thing",
        request={"a": 1},
        response={"b": 2},
        duration_ms=5.0,
    )
    defaults.update(overrides)
    return Record.build(**defaults)


class TestSinkStream:
    def test_writes_json_line(self):
        buf = io.StringIO()
        sink = SinkStream(buf)
        rec = _make_record()
        sink.write(rec)
        line = buf.getvalue().strip()
        data = json.loads(line)
        assert data["client"] == "test.Client"

    def test_multiple_writes(self):
        buf = io.StringIO()
        sink = SinkStream(buf)
        sink.write(_make_record())
        sink.write(_make_record())
        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 2


class TestSinkFile:
    def test_writes_and_appends(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            sink = SinkFile(path)
            sink.write(_make_record())
            sink.write(_make_record())
            sink.close()

            with open(path) as f:
                lines = f.read().strip().split("\n")
            assert len(lines) == 2
            assert json.loads(lines[0])["client"] == "test.Client"
        finally:
            os.unlink(path)

    def test_close_is_idempotent(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            sink = SinkFile(path)
            sink.write(_make_record())
            sink.close()
            sink.close()  # should not raise
        finally:
            os.unlink(path)


class TestSinkMulti:
    def test_fans_out(self):
        buf1 = io.StringIO()
        buf2 = io.StringIO()
        sink = SinkMany([SinkStream(buf1), SinkStream(buf2)])
        sink.write(_make_record())

        assert json.loads(buf1.getvalue().strip())["client"] == "test.Client"
        assert json.loads(buf2.getvalue().strip())["client"] == "test.Client"

    def test_close_all(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            file_sink = SinkFile(path)
            buf = io.StringIO()
            multi = SinkMany([SinkStream(buf), file_sink])
            multi.write(_make_record())
            multi.close()
            # file sink should be closed
            assert file_sink._file is None
        finally:
            os.unlink(path)
