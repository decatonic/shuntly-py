import io
import json
import os

import openai
import pytest

from shuntly import Shuntly, SinkStream

_API_KEY = os.environ.get('OPENAI_API_KEY')
_MODEL = 'gpt-5-nano'  # 'gpt-4o-mini'

pytestmark = pytest.mark.skipif(not _API_KEY, reason='OPENAI_API_KEY nxot set')


def test_wrap_captures_record():
    buf = io.StringIO()
    client = Shuntly.shunt(openai.OpenAI(api_key=_API_KEY), SinkStream(buf))

    resp = client.chat.completions.create(
        model=_MODEL,
        messages=[{'role': 'user', 'content': 'Reply with the single word: pong'}],
    )

    valid = 'pong'
    assert resp.id.startswith('chatcmpl-')
    assert resp.model.startswith('gpt-')
    assert resp.choices[0].finish_reason in ('stop', 'length')
    text = resp.choices[0].message.content.lower().strip()
    assert text == valid

    record = json.loads(buf.getvalue().strip())
    assert record['client'] == 'openai.OpenAI'
    assert record['method'] == 'chat.completions.create'
    assert record['request']['model'] == _MODEL
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert record['response']['id'].startswith('chatcmpl-')
    assert record['response']['choices'][0]['message']['content'].lower().strip() == valid


def test_wrap_captures_stream():
    buf = io.StringIO()
    client = Shuntly.shunt(openai.OpenAI(api_key=_API_KEY), SinkStream(buf))

    chunks = []
    with client.chat.completions.create(
        model=_MODEL,
        stream=True,
        messages=[
            {
                'role': 'user',
                'content': 'Reply with the four words: ping pong ping pong',
            }
        ],
    ) as stream:
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)

    # stream yielded text chunks
    full_text = ''.join(chunks).lower().strip()
    valid = 'ping pong ping pong'
    assert full_text == valid

    # record was captured on stream exit with accumulated chunks
    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'openai.OpenAI'
    assert record['method'] == 'chat.completions.create'
    assert record['request']['model'] == _MODEL
    assert record['request']['stream'] is True
    assert record['error'] is None
    assert record['duration_ms'] > 0
    # response is the list of accumulated chunks
    assert isinstance(record['response'], list)
    assert len(record['response']) > 0

    parts = []
    for r in record['response']:
        part = r['choices'][0]['delta']['content']
        if part:
            parts.append(part)

    assert ''.join(parts) == 'ping pong ping pong'
