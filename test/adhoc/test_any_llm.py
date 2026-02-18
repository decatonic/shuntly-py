import io
import json
import os

import any_llm
import pytest

from shuntly import SinkStream, shunt

_OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
_MODEL = 'gpt-4o-mini'

pytestmark = pytest.mark.skipif(not _OPENAI_API_KEY, reason='OPENAI_API_KEY not set')


def test_wrap_captures_record():
    buf = io.StringIO()
    client = shunt(any_llm, SinkStream(buf))

    response = client.completion(
        model=_MODEL,
        provider='openai',
        messages=[{'role': 'user', 'content': 'Reply with the single word: pong'}],
    )

    assert response.choices[0].message.content.lower().strip() == 'pong'

    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'any_llm'
    assert record['method'] == 'completion'
    assert record['request']['model'] == _MODEL
    assert record['request']['provider'] == 'openai'
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert (
        record['response']['choices'][0]['message']['content'].lower().strip() == 'pong'
    )


def test_wrap_captures_alternative_syntax():
    """Test the provider:model syntax supported by any-llm."""
    buf = io.StringIO()
    client = shunt(any_llm, SinkStream(buf))

    response = client.completion(
        model=f'openai:{_MODEL}',
        messages=[{'role': 'user', 'content': 'Reply with the single word: red'}],
    )

    assert response.choices[0].message.content.lower().strip() == 'red'

    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'any_llm'
    assert record['method'] == 'completion'
    assert record['request']['model'] == f'openai:{_MODEL}'
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert (
        record['response']['choices'][0]['message']['content'].lower().strip() == 'red'
    )
