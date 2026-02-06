import json
from datetime import datetime

from shuntly import ShuntlyRecord


def test_build_populates_fields():
    rec = ShuntlyRecord.build(
        client='anthropic.Anthropic',
        method='messages.create',
        request={'model': 'claude-3'},
        response={'id': 'msg_123'},
        duration_ms=42.0,
    )
    assert rec.client == 'anthropic.Anthropic'
    assert rec.method == 'messages.create'
    assert rec.request == {'model': 'claude-3'}
    assert rec.response == {'id': 'msg_123'}
    assert rec.duration_ms == 42.0
    assert rec.error is None
    assert isinstance(rec.timestamp, datetime)
    assert rec.hostname  # non-empty
    assert rec.user  # non-empty
    assert rec.pid > 0


def test_build_with_error():
    rec = ShuntlyRecord.build(
        client='openai.OpenAI',
        method='chat.completions.create',
        request={},
        response=None,
        duration_ms=1.0,
        error='ValueError: bad input',
    )
    assert rec.error == 'ValueError: bad input'
    assert rec.response is None


def test_to_json_roundtrip():
    rec = ShuntlyRecord.build(
        client='test.Client',
        method='do.thing',
        request={'a': 1},
        response={'b': 2},
        duration_ms=10.5,
    )
    data = json.loads(rec.to_json())
    assert data['client'] == 'test.Client'
    assert data['method'] == 'do.thing'
    assert data['request'] == {'a': 1}
    assert data['response'] == {'b': 2}
    assert data['duration_ms'] == 10.5
    assert data['error'] is None
    assert 'timestamp' in data
    assert 'hostname' in data
    assert 'user' in data
    assert 'pid' in data
