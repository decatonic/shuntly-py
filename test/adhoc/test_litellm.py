import io
import json
import os

import litellm
import pytest

from shuntly import SinkStream, shunt

_API_KEY = os.environ.get('OPENAI_API_KEY')
_MODEL = 'openai/gpt-4o-mini'

pytestmark = pytest.mark.skipif(not _API_KEY, reason='OPENAI_API_KEY not set')


@pytest.fixture(autouse=True)
def _restore_completion():
    original = litellm.completion
    yield
    litellm.completion = original


def test_wrap_captures_record():
    buf = io.StringIO()
    shunt(litellm, SinkStream(buf))

    resp = litellm.completion(
        model=_MODEL,
        messages=[{'role': 'user', 'content': 'Reply with the single word: pong'}],
    )
    text = resp.choices[0].message.content.lower().strip()
    assert text == 'pong'

    record = json.loads(buf.getvalue().strip())
    assert record['client'] == 'litellm'
    assert record['method'] == 'completion'
    assert record['request']['model'] == _MODEL
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert record['response']['choices'][0]['message']['content'].lower() == 'pong'


def test_wrap_captures_stream():
    buf = io.StringIO()
    shunt(litellm, SinkStream(buf))

    chunks = []
    for chunk in litellm.completion(
        model=_MODEL,
        stream=True,
        messages=[
            {
                'role': 'user',
                'content': 'Reply with the four words: ping pong ping pong',
            }
        ],
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)

    full_text = ''.join(chunks).lower().strip()
    assert full_text == 'ping pong ping pong'

    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'litellm'
    assert record['method'] == 'completion'
    assert record['request']['model'] == _MODEL
    assert record['request']['stream'] is True
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert isinstance(record['response'], list)
    assert len(record['response']) > 0

    msg = []
    for m in record['response']:
        c = m['choices'][0]['delta']['content']
        if c:
            msg.append(c)
    assert ''.join(msg).lower() == 'ping pong ping pong'
