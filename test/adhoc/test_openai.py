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
