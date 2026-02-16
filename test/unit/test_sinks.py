import io
import json
import os
import tempfile

from shuntly import ShuntlyRecord, SinkFile, SinkMany, SinkRotating, SinkStream


def _make_record(**overrides) -> ShuntlyRecord:
    defaults = dict(
        client='test.Client',
        method='do.thing',
        request={'a': 1},
        response={'b': 2},
        duration_ms=5.0,
    )
    defaults.update(overrides)
    return ShuntlyRecord.build(**defaults)


class TestSinkStream:
    def test_writes_json_line(self):
        buf = io.StringIO()
        sink = SinkStream(buf)
        rec = _make_record()
        sink.write(rec)
        line = buf.getvalue().strip()
        data = json.loads(line)
        assert data['client'] == 'test.Client'

    def test_multiple_writes(self):
        buf = io.StringIO()
        sink = SinkStream(buf)
        sink.write(_make_record())
        sink.write(_make_record())
        lines = buf.getvalue().strip().split('\n')
        assert len(lines) == 2


class TestSinkFile:
    def test_writes_and_appends(self):
        with tempfile.NamedTemporaryFile(mode='r', suffix='.jsonl', delete=False) as f:
            path = f.name
        try:
            sink = SinkFile(path)
            sink.write(_make_record())
            sink.write(_make_record())
            sink.close()

            with open(path) as f:
                lines = f.read().strip().split('\n')
            assert len(lines) == 2
            assert json.loads(lines[0])['client'] == 'test.Client'
        finally:
            os.unlink(path)

    def test_close_is_idempotent(self):
        with tempfile.NamedTemporaryFile(mode='r', suffix='.jsonl', delete=False) as f:
            path = f.name
        try:
            sink = SinkFile(path)
            sink.write(_make_record())
            sink.close()
            sink.close()  # should not raise
        finally:
            os.unlink(path)


class TestSinkRotating:
    def test_writes_to_directory(self):
        with tempfile.TemporaryDirectory() as d:
            sink = SinkRotating(d)
            sink.write(_make_record())
            sink.close()
            files = [f for f in os.listdir(d) if f.endswith('.jsonl')]
            assert len(files) == 1
            with open(os.path.join(d, files[0])) as f:
                data = json.loads(f.read().strip())
            assert data['client'] == 'test.Client'

    def test_rotates_on_max_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            # Use a tiny max_bytes to force rotation
            sink = SinkRotating(d, max_bytes_file=50, max_bytes_dir=0)
            for _ in range(5):
                sink.write(_make_record())
            sink.close()
            files = [f for f in os.listdir(d) if f.endswith('.jsonl')]
            assert len(files) > 1

    def test_prunes_old_files(self):
        with tempfile.TemporaryDirectory() as d:
            # Tiny limits to force both rotation and pruning
            sink = SinkRotating(d, max_bytes_file=50, max_bytes_dir=200)
            for _ in range(20):
                sink.write(_make_record())
            sink.close()
            files = [f for f in os.listdir(d) if f.endswith('.jsonl')]
            # Without pruning, 20 writes at ~230 bytes each with 50-byte
            # rotation would create many files; pruning should reduce them.
            # We also write at least one file with no pruning on the first
            # rotation, so just verify some were removed.
            no_prune_sink = SinkRotating(
                os.path.join(d, 'no_prune'),
                max_bytes_file=50,
                max_bytes_dir=0,
            )
            for _ in range(20):
                no_prune_sink.write(_make_record())
            no_prune_sink.close()
            no_prune_files = [
                f
                for f in os.listdir(os.path.join(d, 'no_prune'))
                if f.endswith('.jsonl')
            ]
            assert len(files) < len(no_prune_files)

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as d:
            nested = os.path.join(d, 'sub', 'dir')
            sink = SinkRotating(nested)
            sink.write(_make_record())
            sink.close()
            assert os.path.isdir(nested)
            files = [f for f in os.listdir(nested) if f.endswith('.jsonl')]
            assert len(files) == 1

    def test_close_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            sink = SinkRotating(d)
            sink.write(_make_record())
            sink.close()
            sink.close()  # should not raise

    def test_no_prune_when_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            sink = SinkRotating(d, max_bytes_file=50, max_bytes_dir=0)
            for _ in range(10):
                sink.write(_make_record())
            sink.close()
            files = [f for f in os.listdir(d) if f.endswith('.jsonl')]
            # All files should remain since pruning is disabled
            assert len(files) > 1


class TestSinkMulti:
    def test_fans_out(self):
        buf1 = io.StringIO()
        buf2 = io.StringIO()
        sink = SinkMany([SinkStream(buf1), SinkStream(buf2)])
        sink.write(_make_record())

        assert json.loads(buf1.getvalue().strip())['client'] == 'test.Client'
        assert json.loads(buf2.getvalue().strip())['client'] == 'test.Client'

    def test_close_all(self):
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
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
