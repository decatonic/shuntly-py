import io
import json
import os

import anthropic
import pytest

from shuntly import Shuntly, SinkStream

_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
_MODEL = 'claude-3-haiku-20240307'

pytestmark = pytest.mark.skipif(not _API_KEY, reason='ANTHROPIC_API_KEY not set')


def test_wrap_captures_record():
    buf = io.StringIO()
    client = shunt(anthropic.Anthropic(api_key=_API_KEY), SinkStream(buf))

    resp = client.messages.create(
        model=_MODEL,
        max_tokens=32,
        messages=[{'role': 'user', 'content': 'Reply with the single word: pong'}],
    )

    valid = 'pong'
    assert resp.id.startswith('msg_')
    assert resp.model.startswith('claude')
    assert resp.stop_reason in ('end_turn', 'max_tokens')
    text = resp.content[0].text.lower()
    assert text == valid

    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'anthropic.Anthropic'
    assert record['method'] == 'messages.create'
    assert record['request']['model'] == _MODEL
    assert record['request']['max_tokens'] == 32
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert record['response']['id'].startswith('msg_')
    assert record['response']['content'][0]['text'] == valid


def test_wrap_captures_stream():
    buf = io.StringIO()
    client = shunt(anthropic.Anthropic(api_key=_API_KEY), SinkStream(buf))

    chunks = []
    with client.messages.stream(
        model=_MODEL,
        max_tokens=32,
        messages=[
            {
                'role': 'user',
                'content': 'Reply with the four words: ping pong ping pong',
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)

    # stream yielded text chunks
    full_text = ''.join(chunks).lower()
    valid = 'ping pong ping pong'
    assert full_text == valid

    # record was captured on stream exit with the final message
    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'anthropic.Anthropic'
    assert record['method'] == 'messages.stream'
    assert record['request']['model'] == _MODEL
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert record['response']['id'].startswith('msg_')
    assert record['response']['stop_reason'] in ('end_turn', 'max_tokens')
    assert record['response']['content'][0]['text'] == valid
