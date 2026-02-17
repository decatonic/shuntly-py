import io
import json
import os
import tempfile

from unittest.mock import MagicMock

from shuntly import ShuntlyRecord, SinkFile, SinkMany, SinkS3, SinkStream


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


def _make_s3_sink(**kwargs) -> tuple[SinkS3, MagicMock]:
    defaults = dict(
        bucket='test-bucket',
        access_key_id='AKID',
        secret_access_key='SECRET',
    )
    defaults.update(kwargs)
    sink = SinkS3(**defaults)
    mock_client = MagicMock()
    sink._client = mock_client
    return sink, mock_client


class TestSinkS3:
    def test_uploads_on_close(self):
        sink, mock_client = _make_s3_sink()
        sink.write(_make_record())
        sink.write(_make_record())
        mock_client.put_object.assert_not_called()

        sink.close()
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs['Bucket'] == 'test-bucket'
        assert call_kwargs['Key'].endswith('.jsonl')
        assert call_kwargs['ContentType'] == 'application/x-ndjson'
        body = call_kwargs['Body'].decode()
        lines = body.strip().split('\n')
        assert len(lines) == 2

    def test_flushes_on_max_bytes(self):
        sink, mock_client = _make_s3_sink(max_bytes_file=50)
        for _ in range(5):
            sink.write(_make_record())
        assert mock_client.put_object.call_count >= 1
        sink.close()

    def test_prefix_in_key(self):
        sink, mock_client = _make_s3_sink(prefix='prod/logs/')
        sink.write(_make_record())
        sink.close()
        key = mock_client.put_object.call_args[1]['Key']
        assert key.startswith('prod/logs/')

    def test_no_upload_when_empty(self):
        sink, mock_client = _make_s3_sink()
        sink.close()
        mock_client.put_object.assert_not_called()

    def test_close_is_idempotent(self):
        sink, mock_client = _make_s3_sink()
        sink.write(_make_record())
        sink.close()
        sink.close()  # should not upload again
        assert mock_client.put_object.call_count == 1


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
